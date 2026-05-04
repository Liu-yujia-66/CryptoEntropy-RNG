from __future__ import annotations

"""
Experiment 2 all-offset runner — relaxed (heuristic) gate.

Plan A from advisor (2026-04). Accepts an aggregation level ell when at least
    max(RELAXED_MIN_PASS_ABSOLUTE, ceil(RELAXED_MIN_PASS_FRACTION * ell))
offsets simultaneously pass Predictability (adaptive k) and Monobit at an
uncorrected alpha. This is a heuristic supplementary analysis, NOT a formal
multiple-testing correction. See `Exp2 Plan A - Relaxed Gate.md`.

Double early termination:
  - Within (asset, ell): break the offset loop as soon as num_pass >= threshold.
  - Across ell: break the outer loop as soon as an acceptable ell is found,
    and record it as the asset's selected ell.

Assumes N_valid == ell (MIN_BIT_COUNT=2000 always satisfied for our data).

Output dir is isolated from the strict runner.

Run:
    python scripts/runner_exp2_all_offset_relaxed.py
"""

import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bitstream import build_offset_bitstream_from_arrays
from src.data_io import filter_month_files, prepare_month_data
from src.stats import (
    _adaptive_k,
    entropy_predictability_test,
    monobit_test,
    summarize_bits_full,
)
from src.exp2_summary import format_selection_table
from src.utils import fmt_elapsed, period_dir_name


# Configuration


ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

PERIODS: list[list[str]] = [
    ["2025-01"],
    ["2025-02"],
    ["2025-03"],
    ["2025-04"],
    ["2025-05"],
    ["2025-06"],
    ["2025-07"],
    ["2025-08"],
    ["2025-09"],
    ["2025-10"],
    ["2025-11"],
    ["2025-12"],
    ["2026-01"],
    ["2026-02"],
    ["2026-03"],
]

RELAXED_MIN_PASS_ABSOLUTE = 3
RELAXED_MIN_PASS_FRACTION = 0.03

# Gate mode switch:
#   "heuristic"  — require num_pass >= max(F, ceil(f * N_valid)) at per-offset alpha=ALPHA  (default, Plan A)
#   "bonferroni" — require num_pass >= 1 at per-offset alpha = ALPHA / N_valid
#   "sidak"      — require num_pass >= 1 at per-offset alpha = 1 - (1-ALPHA)^(1/N_valid)
# Bonferroni/Sidak are reported as sensitivity only — they loosen the per-offset
# pass threshold, which is the wrong direction for the "random by chance"
# concern the correction is intended to guard against.
GATE_MODE: str = "heuristic"

AGG_START = 10
AGG_STOP = 2000
AGG_STEP = 2

# per - month
ASSET_AGG_CONFIG: dict[str, tuple[int, int, int]] = {
    "ETHUSDT": (200, AGG_STOP, AGG_STEP),
    "BTCUSDT": (700, 3000, AGG_STEP),
}

# heuristic keeps the legacy naming (no "heuristic-" prefix) so existing
# results are not orphaned; other modes add a "-{mode}" suffix
if GATE_MODE == "heuristic":
    _mode_suffix = f"({RELAXED_MIN_PASS_ABSOLUTE},{RELAXED_MIN_PASS_FRACTION})"
else:
    _mode_suffix = f"-{GATE_MODE}"

OUTPUT_ROOT = Path(
    "data/processed/experiment2/"
    f"relaxed-all-offset-per-month{_mode_suffix}"
    f"-({AGG_START},{AGG_STOP},{AGG_STEP})"
)

# per - Quarter
# ASSET_AGG_CONFIG: dict[str, tuple[int, int, int]] = {
#     "ETHUSDT": (700, AGG_STOP, AGG_STEP),
#     "BTCUSDT": (1000, 3000, AGG_STEP),
# }

# OUTPUT_ROOT = Path(
#     "data/processed/experiment2/"
#     f"relaxed-all-offset({RELAXED_MIN_PASS_ABSOLUTE},{RELAXED_MIN_PASS_FRACTION})"
#     f"-({AGG_START},{AGG_STOP},{AGG_STEP})"
# )

AGG_LEVELS: list[int] = list(range(AGG_START, AGG_STOP + 1, AGG_STEP))

MIN_BIT_COUNT = 2000
ALPHA = 0.01

MAX_WORKERS = 3
MAX_ROWS: int | None = None

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)


# Core: scan one (asset, period) with double early termination


WITNESS_FIELDS = (
    "witness_offset",
    "witness_min_pvalue",
    "witness_predictability_pvalue",
    "witness_monobit_pvalue",
    "witness_predictability_k2_pvalue",
    "witness_runs_pvalue",
    "witness_bits_per_second",
)


def _nan_witness() -> dict[str, object]:
    return {
        field: (-1 if field == "witness_offset" else float("nan"))
        for field in WITNESS_FIELDS
    }


def _gate_params(agg_level: int) -> tuple[float, int]:
    """Return (alpha_effective, num_pass_threshold) for the active GATE_MODE.

    Assumes N_valid == agg_level (MIN_BIT_COUNT always satisfied for our data).
    """
    if GATE_MODE == "heuristic":
        threshold = max(
            RELAXED_MIN_PASS_ABSOLUTE,
            math.ceil(RELAXED_MIN_PASS_FRACTION * agg_level),
        )
        return ALPHA, threshold
    if GATE_MODE == "bonferroni":
        return ALPHA / agg_level, 1
    if GATE_MODE == "sidak":
        return 1.0 - (1.0 - ALPHA) ** (1.0 / agg_level), 1
    raise ValueError(f"Unknown GATE_MODE: {GATE_MODE!r}")


def _asset_agg_config(asset: str) -> tuple[int, int, int]:
    return ASSET_AGG_CONFIG.get(asset, (AGG_START, AGG_STOP, AGG_STEP))


def _asset_agg_levels(asset: str) -> list[int]:
    start, stop, step = _asset_agg_config(asset)
    return list(range(start, stop + 1, step))


def _build_offset_bits(
    agg_level: int,
    offset: int,
    prepared_months: list,
) -> np.ndarray:
    """Construct and concatenate one offset's bitstream across all months."""
    chunks = [
        build_offset_bitstream_from_arrays(
            price=prepared.price, agg_level=agg_level, offset=offset
        ).bits
        for prepared in prepared_months
    ]
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.uint8)


def _light_test(bits: np.ndarray) -> tuple[float, float]:
    """Run only Monobit and Predictability D (adaptive k) on a bitstream.

    Returns (p_D, p_monobit). ~3-5x faster than summarize_bits_full because it
    skips ApproxEntropy, D(k=2), Shannon-bias, Runs, autocorrelation, etc.
    These are all unused for the accept/reject decision. The final witness
    offset gets the full battery in a single follow-up call.
    """
    _, p_mono = monobit_test(bits)
    history_length = _adaptive_k(int(bits.size)) - 1
    _, _, p_d = entropy_predictability_test(bits, history_length=history_length)
    return float(p_d), float(p_mono)


def _witness_from_full_battery(
    asset: str,
    agg_level: int,
    offset: int,
    bits: np.ndarray,
    combined_duration: float,
) -> dict[str, object]:
    """Run the full test battery on the chosen witness offset to populate the
    diagnostic fields (D(k=2), Runs, bits/s, etc.) reported in CSV."""
    bits_per_second = (
        float(bits.size / combined_duration) if combined_duration > 0 else float("nan")
    )
    metadata: dict[str, object] = {
        "asset": asset,
        "agg_level": agg_level,
        "offset": offset,
        "duration_seconds": combined_duration,
        "bits_per_second": bits_per_second,
        "analysis_scope": "combined_offset_relaxed_witness",
    }
    row = summarize_bits_full(bits=bits, metadata=metadata)
    p_d = float(cast(float, row["predictability_pvalue"]))
    p_mono = float(cast(float, row["monobit_pvalue"]))
    return {
        "witness_offset": int(offset),
        "witness_min_pvalue": float(min(p_d, p_mono)),
        "witness_predictability_pvalue": p_d,
        "witness_monobit_pvalue": p_mono,
        "witness_predictability_k2_pvalue": float(
            cast(float, row["predictability_k2_pvalue"])
        ),
        "witness_runs_pvalue": float(cast(float, row["runs_pvalue"])),
        "witness_bits_per_second": bits_per_second,
    }


def _scan_one_agg_level(
    asset: str,
    agg_level: int,
    prepared_months: list,
    combined_duration: float,
) -> dict[str, object]:
    """
    Scan offsets for one (asset, ell) with two-stage testing:
      1. Light scan: compute only D + Monobit per offset, count passes, track
         the best (highest min(p_D, p_mono)) passing offset. Early-terminate
         once num_pass reaches the threshold.
      2. Witness finalize: if any offset passed, re-run the full test battery
         on the best passing offset so the diagnostic CSV has D(k=2)/Runs p's.

    Returns a per-ell diagnostic row.
    """
    alpha_eff, threshold = _gate_params(agg_level)

    num_pass = 0
    scanned = 0
    best_min_p = -1.0
    best_offset = -1

    for offset in range(agg_level):
        bits = _build_offset_bits(agg_level, offset, prepared_months)
        if bits.size < MIN_BIT_COUNT:
            continue
        scanned += 1

        p_d, p_mono = _light_test(bits)
        if p_d >= alpha_eff and p_mono >= alpha_eff:
            num_pass += 1
            min_p = min(p_d, p_mono)
            if min_p > best_min_p:
                best_min_p = min_p
                best_offset = offset

        if num_pass >= threshold:
            break

    is_acceptable = num_pass >= threshold

    if best_offset >= 0:
        witness_bits = _build_offset_bits(agg_level, best_offset, prepared_months)
        witness = _witness_from_full_battery(
            asset, agg_level, best_offset, witness_bits, combined_duration
        )
    else:
        witness = _nan_witness()

    return {
        "asset": asset,
        "agg_level": agg_level,
        "total_offset_count": agg_level,
        "scanned_offset_count": scanned,
        "gate_mode": GATE_MODE,
        "alpha": ALPHA,
        "alpha_effective": alpha_eff,
        "relaxed_threshold": threshold,
        "num_offsets_passing_both": num_pass,
        "is_acceptable_relaxed": is_acceptable,
        **witness,
    }


def process_asset(
    asset: str,
    months: list[str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """
    Scan ell grid from smallest; stop at the first acceptable ell.

    Returns (per_ell_rows, selected_row). per_ell_rows covers every ell
    scanned (all rejected ells + at most one accepted ell).
    """
    asset_dir = INPUT_ROOT / asset
    if not asset_dir.exists():
        return [], _selected_na(asset, status="asset_dir_missing")

    files = filter_month_files(sorted(asset_dir.glob("*.csv")), months)
    if not files:
        return [], _selected_na(asset, status="no_month_files")

    prepared_months = [prepare_month_data(path, max_rows=MAX_ROWS) for path in files]
    combined_duration = float(sum(p.context.duration_seconds for p in prepared_months))

    per_ell_rows: list[dict[str, object]] = []

    agg_levels = _asset_agg_levels(asset)
    for agg_level in agg_levels:
        ell_row = _scan_one_agg_level(
            asset, agg_level, prepared_months, combined_duration
        )
        per_ell_rows.append(ell_row)

        verdict = "ACCEPT" if ell_row["is_acceptable_relaxed"] else "REJECT"
        scanned_int = int(cast(int, ell_row["scanned_offset_count"]))
        num_pass_int = int(cast(int, ell_row["num_offsets_passing_both"]))
        threshold_int = int(cast(int, ell_row["relaxed_threshold"]))
        scanned_str = f"{scanned_int}/{agg_level}"
        print(
            f"[scan] {asset:<8}  ell={agg_level:<4d}  "
            f"scanned={scanned_str:<9}  "
            f"num_pass={num_pass_int:<4d}  "
            f"threshold={threshold_int:<4d}  {verdict}"
        )

        if ell_row["is_acceptable_relaxed"]:
            selected = {
                "asset": asset,
                "selected_agg_level": int(agg_level),
                "selection_status": "selected_smallest_relaxed_ell",
                "relaxed_threshold": int(cast(int, ell_row["relaxed_threshold"])),
                "num_offsets_passing_both": int(
                    cast(int, ell_row["num_offsets_passing_both"])
                ),
                "scanned_offset_count": int(cast(int, ell_row["scanned_offset_count"])),
                **{f: ell_row[f] for f in WITNESS_FIELDS},
            }
            return per_ell_rows, selected

    return per_ell_rows, _selected_na(asset, status="no_acceptable_ell_relaxed")


def _selected_na(asset: str, status: str) -> dict[str, object]:
    return {
        "asset": asset,
        "selected_agg_level": float("nan"),
        "selection_status": status,
        "relaxed_threshold": float("nan"),
        "num_offsets_passing_both": 0,
        "scanned_offset_count": 0,
        **_nan_witness(),
    }


# Output


def _save(
    output_dir: Path,
    per_ell_df: pd.DataFrame,
    selected_df: pd.DataFrame,
) -> None:
    selected_df = selected_df.copy()
    selected_df["selected_agg_level"] = selected_df["selected_agg_level"].astype(
        "Int64"
    )

    per_ell_df.to_csv(
        output_dir / "relaxed_all_assets_summary_exp2_k_acceptance.csv", index=False
    )
    selected_df.to_csv(
        output_dir / "relaxed_all_assets_summary_exp2_selected_k.csv", index=False
    )
    print(f"[saved] {output_dir}/relaxed_all_assets_summary_exp2_*.csv")


def _write_selected_ell_summary_txt(
    summary_root: Path,
    period_selected_frames: list[tuple[list[str], pd.DataFrame]],
) -> None:
    if not period_selected_frames:
        return

    intro = [
        "Results. Selected ell per window:",
        "",
        f"RELAXED_MIN_PASS_ABSOLUTE = {RELAXED_MIN_PASS_ABSOLUTE}",
        f"RELAXED_MIN_PASS_FRACTION = {RELAXED_MIN_PASS_FRACTION}",
        "",
        f"DEFAULT_AGG_START = {AGG_START}",
        f"DEFAULT_AGG_STOP = {AGG_STOP}",
        f"DEFAULT_AGG_STEP = {AGG_STEP}",
        "",
        *[
            f"{asset} = ({start}, {stop}, {step})"
            for asset, (start, stop, step) in ASSET_AGG_CONFIG.items()
        ],
    ]
    text = format_selection_table(period_selected_frames, intro)
    if not text:
        return

    output_path = summary_root / "selected_ell_by_window.txt"
    output_path.write_text(text, encoding="utf-8")
    print(f"[saved] {output_path}")


# Main


def main() -> None:
    import time

    project_root = Path(__file__).resolve().parent.parent
    total_start = time.perf_counter()
    summary_root = project_root / OUTPUT_ROOT
    summary_root.mkdir(parents=True, exist_ok=True)
    period_selected_frames: list[tuple[list[str], pd.DataFrame]] = []

    for months in PERIODS:
        period_name = period_dir_name(months)
        output_dir = summary_root / period_name
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"[period] {period_name}  months={months}  (relaxed)")
        print(f"{'='*60}")

        period_start = time.perf_counter()
        per_ell_all: list[dict[str, object]] = []
        selected_all: list[dict[str, object]] = []
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(process_asset, asset, months): asset for asset in ASSETS
            }
            for future in as_completed(future_map):
                asset = future_map[future]
                try:
                    per_ell_rows, selected_row = future.result()
                    per_ell_all.extend(per_ell_rows)
                    selected_all.append(selected_row)
                    print(f"[done] {asset}")
                except Exception as exc:
                    print(f"[error] {asset}: {exc}")
                    failures.append(asset)

        if not per_ell_all:
            print(f"[warn] no rows for period {period_name}, skipping")
            continue

        per_ell_df = pd.DataFrame(per_ell_all).sort_values(["asset", "agg_level"])
        selected_df = pd.DataFrame(selected_all).sort_values("asset")
        _save(output_dir, per_ell_df, selected_df)
        period_selected_frames.append((months, selected_df.copy()))

        print(
            f"[time] {period_name}: {fmt_elapsed(time.perf_counter() - period_start)}"
        )
        if failures:
            print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    _write_selected_ell_summary_txt(summary_root, period_selected_frames)

    print(
        f"\n[done] all periods  total: {fmt_elapsed(time.perf_counter() - total_start)}"
    )


if __name__ == "__main__":
    main()
