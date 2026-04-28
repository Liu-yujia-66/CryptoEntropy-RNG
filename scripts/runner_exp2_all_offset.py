from __future__ import annotations

"""
Experiment 2 all-offset runner — in-process version.

Uses src.data_io, src.stats, and src.bitstream directly instead of spawning
subprocesses. Produces identical output structure to the combination of
exp2_all_offsets_optimized.py + run_exp2_all_offsets_parallel_optimized.py.

Edit the configuration block below, then run:
    python scripts/runner_exp2_all_offset.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from src.bitstream import build_all_offset_bitstreams, save_bitstream
from src.data_io import filter_month_files, prepare_month_data
from src.exp2_summary import build_combined_row, format_selection_table
from src.utils import fmt_elapsed, period_dir_name, run_plot_subprocess


# Configuration


ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

# Periods to process — each entry is a list of "YYYY-MM" month strings.
PERIODS: list[list[str]] = [
    # Monthly
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
    # Quarterly
    # ["2025-01", "2025-02", "2025-03"],
    # ["2025-04", "2025-05", "2025-06"],
    # ["2025-07", "2025-08", "2025-09"],
    # ["2025-10", "2025-11", "2025-12"],
    # ["2026-01", "2026-02", "2026-03"],
    # Half-year
    # ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"],
    # ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"],
    # Full year
    # [
    #     "2025-01",
    #     "2025-02",
    #     "2025-03",
    #     "2025-04",
    #     "2025-05",
    #     "2025-06",
    #     "2025-07",
    #     "2025-08",
    #     "2025-09",
    #     "2025-10",
    #     "2025-11",
    #     "2025-12",
    # ],
]

AGG_START = 50
AGG_STOP = 2000
AGG_STEP = 25
AGG_LEVELS: list[int] = list(range(AGG_START, AGG_STOP + 1, AGG_STEP))

MAX_ROWS: int | None = None
MIN_BIT_COUNT = 2000
ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
VALID_OFFSET_RATIO_THRESHOLD = 0.80

SAVE_BITSTREAMS = False
# per-(asset, ell, offset) raw stats CSV (~200MB); off by default
SAVE_OFFSET_STATS = False

MAX_WORKERS = 3

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
# OUTPUT_ROOT = Path("data/processed/experiment2/all-offset")
OUTPUT_ROOT = Path(
    f"data/processed/experiment2/all-offset-per-month({AGG_START},{AGG_STOP},{AGG_STEP})"
)


# Per-asset processing


def process_asset(
    asset: str,
    months: list[str],
    output_dir: Path,
) -> list[dict[str, object]]:
    """Load all month files for an asset and run all-offset analysis for every k."""
    asset_dir = INPUT_ROOT / asset
    if not asset_dir.exists():
        print(f"[skip] asset directory not found: {asset_dir}")
        return []

    files = filter_month_files(sorted(asset_dir.glob("*.csv")), months)
    if not files:
        print(f"[skip] no matching csv files under: {asset_dir}")
        return []

    prepared_months = [prepare_month_data(path, max_rows=MAX_ROWS) for path in files]

    rows: list[dict[str, object]] = []

    for agg_level in sorted(set(AGG_LEVELS)):
        print(f"[processing] asset={asset}  ell={agg_level}")

        combined_bits_by_offset: dict[int, list[np.ndarray]] = {
            offset: [] for offset in range(agg_level)
        }
        combined_duration_seconds = 0.0

        for prepared in prepared_months:
            combined_duration_seconds += prepared.context.duration_seconds
            for bitstream in build_all_offset_bitstreams(prepared, agg_level):
                combined_bits_by_offset[bitstream.offset].append(bitstream.bits)

        for offset in range(agg_level):
            chunks = combined_bits_by_offset[offset]
            if not chunks:
                continue
            combined_bits = np.concatenate(chunks)
            rows.append(
                build_combined_row(
                    asset=asset,
                    agg_level=agg_level,
                    offset=offset,
                    combined_bits=combined_bits,
                    combined_duration_seconds=combined_duration_seconds,
                    source_files=files,
                    timestamp_unit="mixed",
                    analysis_scope="combined_offset",
                )
            )
            if SAVE_BITSTREAMS:
                bitstream_path = (
                    output_dir
                    / "bitstreams"
                    / f"agg_{agg_level}"
                    / asset
                    / f"{asset}_combined_offset{offset}_agg{agg_level}.csv"
                )
                save_bitstream(combined_bits, bitstream_path)

    return rows


# Acceptance summary


def _summarize_acceptance(
    combined_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []

    grouped = combined_df.groupby(["asset", "agg_level"], sort=True)
    for key, group in grouped:
        asset, agg_level = cast(tuple[str, int], key)
        valid = group[group["bit_count"] >= MIN_BIT_COUNT].copy()
        valid_offset_count = int(len(valid))
        total_offset_count = int(len(group))

        if valid.empty:
            selection_rows.append(
                {
                    "asset": asset,
                    "agg_level": agg_level,
                    "total_offset_count": total_offset_count,
                    "valid_offset_count": 0,
                    "valid_offset_ratio": 0.0,
                    "predictability_pass_rate": float("nan"),
                    "predictability_k2_pass_rate": float("nan"),
                    "monobit_pass_rate": float("nan"),
                    "runs_pass_rate": float("nan"),
                    "approximate_entropy_pass_rate": float("nan"),
                    "shannon_bias_pass_rate": float("nan"),
                    "avg_bits_per_second": float("nan"),
                    "min_bit_count_required": MIN_BIT_COUNT,
                    "alpha": ALPHA,
                    "pass_rate_threshold": PASS_RATE_THRESHOLD,
                    "is_acceptable": False,
                }
            )
            continue

        predictability_pass_rate = float(
            (valid["predictability_pvalue"] >= ALPHA).mean()
        )
        # Fixed-k=2 "pairs of signs" diagnostic (Shternshis & Marmi 2025 §4.4);
        # reported alongside Runs for cross-check but not part of is_acceptable.
        predictability_k2_pass_rate = float(
            (valid["predictability_k2_pvalue"] >= ALPHA).mean()
        )
        monobit_pass_rate = float((valid["monobit_pvalue"] >= ALPHA).mean())
        runs_pass_rate = float((valid["runs_pvalue"] >= ALPHA).mean())
        approximate_entropy_pass_rate = float(
            (valid["approximate_entropy_pvalue"] >= ALPHA).mean()
        )
        shannon_bias_pass_rate = float((valid["shannon_bias_pvalue"] >= ALPHA).mean())
        avg_bits_per_second = float(valid["bits_per_second"].mean())
        valid_offset_ratio = valid_offset_count / total_offset_count
        # Acceptance gate: adaptive-k D + Monobit only. Runs is demoted to
        # reference because the adaptive-k D (~6-7) dilutes 1st-order signal
        # across 2^(k-1) contexts, producing systematic D/Runs disagreement
        # matching Shternshis & Marmi (2025) §4.4's SNAP/F/CCL bid-ask-bounce
        # stylized fact. predictability_k2 is the principled 1st-order
        # diagnostic for post-hoc interpretation.
        is_acceptable = bool(
            valid_offset_ratio >= VALID_OFFSET_RATIO_THRESHOLD
            and predictability_pass_rate >= PASS_RATE_THRESHOLD
            and monobit_pass_rate >= PASS_RATE_THRESHOLD
        )

        selection_rows.append(
            {
                "asset": asset,
                "agg_level": agg_level,
                "total_offset_count": total_offset_count,
                "valid_offset_count": valid_offset_count,
                "valid_offset_ratio": valid_offset_ratio,
                "predictability_pass_rate": predictability_pass_rate,
                "predictability_k2_pass_rate": predictability_k2_pass_rate,
                "monobit_pass_rate": monobit_pass_rate,
                "runs_pass_rate": runs_pass_rate,
                "approximate_entropy_pass_rate": approximate_entropy_pass_rate,
                "shannon_bias_pass_rate": shannon_bias_pass_rate,
                "avg_bits_per_second": avg_bits_per_second,
                "min_bit_count_required": MIN_BIT_COUNT,
                "alpha": ALPHA,
                "pass_rate_threshold": PASS_RATE_THRESHOLD,
                "is_acceptable": is_acceptable,
            }
        )

    selection_df = pd.DataFrame(selection_rows).sort_values(["asset", "agg_level"])

    for asset, group in selection_df.groupby("asset", sort=True):
        acceptable = group[group["is_acceptable"]].sort_values("agg_level")
        if acceptable.empty:
            selected_rows.append(
                {
                    "asset": asset,
                    "selected_agg_level": float("nan"),
                    "selection_status": "no_acceptable_ell",
                }
            )
            continue
        chosen = acceptable.iloc[0]
        selected_rows.append(
            {
                "asset": asset,
                "selected_agg_level": int(chosen["agg_level"]),
                "selection_status": "selected_smallest_acceptable_ell",
                "predictability_pass_rate": chosen["predictability_pass_rate"],
                "predictability_k2_pass_rate": chosen["predictability_k2_pass_rate"],
                "monobit_pass_rate": chosen["monobit_pass_rate"],
                "runs_pass_rate": chosen["runs_pass_rate"],
                "avg_bits_per_second": chosen["avg_bits_per_second"],
            }
        )

    selected_df = pd.DataFrame(selected_rows).sort_values("asset")
    return selection_df, selected_df


# Output helpers


def _save_asset_outputs(
    output_dir: Path,
    combined_df: pd.DataFrame,
    selection_df: pd.DataFrame,
    selected_df: pd.DataFrame,
) -> None:
    for asset in sorted(combined_df["asset"].unique()):
        asset_dir = output_dir / "by_asset" / asset
        asset_dir.mkdir(parents=True, exist_ok=True)

        if SAVE_OFFSET_STATS:
            combined_df[combined_df["asset"] == asset].to_csv(
                asset_dir / f"{asset}_summary_exp2_offset_stats.csv", index=False
            )
        selection_df[selection_df["asset"] == asset].to_csv(
            asset_dir / f"{asset}_summary_exp2_k_acceptance.csv", index=False
        )
        selected_df[selected_df["asset"] == asset].to_csv(
            asset_dir / f"{asset}_summary_exp2_selected_k.csv", index=False
        )
        print(f"[saved] {asset} → {asset_dir}")


def _merge_all_assets(output_dir: Path) -> None:
    by_asset_dir = output_dir / "by_asset"
    suffixes = ["k_acceptance", "selected_k"]
    if SAVE_OFFSET_STATS:
        suffixes = ["offset_stats", *suffixes]
    for suffix in suffixes:
        frames = []
        for asset in sorted(ASSETS):
            candidate = by_asset_dir / asset / f"{asset}_summary_exp2_{suffix}.csv"
            if candidate.exists():
                frames.append(pd.read_csv(candidate))
            else:
                print(f"[warn] missing {candidate}")
        if not frames:
            print(f"[warn] no data for suffix '{suffix}', skipping merge")
            continue
        out_path = output_dir / f"all_assets_summary_exp2_{suffix}.csv"
        pd.concat(frames, ignore_index=True).to_csv(out_path, index=False)
        print(f"[merge] {out_path}")


# Cross-period summary txt


def _write_selected_ell_summary_txt(
    summary_root: Path,
    period_selected_frames: list[tuple[list[str], pd.DataFrame]],
) -> None:
    if not period_selected_frames:
        return

    intro = [
        "Strict gate (80% pass-rate). Selected ell per window:",
        "",
        f"PASS_RATE_THRESHOLD = {PASS_RATE_THRESHOLD}",
        f"VALID_OFFSET_RATIO_THRESHOLD = {VALID_OFFSET_RATIO_THRESHOLD}",
        f"ALPHA = {ALPHA}",
        "",
        f"AGG_START = {AGG_START}",
        f"AGG_STOP = {AGG_STOP}",
        f"AGG_STEP = {AGG_STEP}",
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
        print(f"[period] {period_name}  months={months}")
        print(f"{'='*60}")

        period_start = time.perf_counter()
        all_rows: list[dict[str, object]] = []
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(process_asset, asset, months, output_dir): asset
                for asset in ASSETS
            }
            for future in as_completed(future_map):
                asset = future_map[future]
                try:
                    rows = future.result()
                    all_rows.extend(rows)
                    print(f"[done] {asset}")
                except Exception as exc:
                    print(f"[error] {asset}: {exc}")
                    failures.append(asset)

        if not all_rows:
            print(f"[warn] no rows produced for period {period_name}, skipping outputs")
            continue

        combined_df = pd.DataFrame(all_rows).sort_values(
            ["asset", "agg_level", "offset"]
        )
        selection_df, selected_df = _summarize_acceptance(combined_df)

        _save_asset_outputs(output_dir, combined_df, selection_df, selected_df)
        _merge_all_assets(output_dir)
        period_selected_frames.append((months, selected_df.copy()))
        run_plot_subprocess(
            project_root,
            "scripts/plot_exp2_all_offsets_optimized.py",
            output_dir,
        )

        period_elapsed = time.perf_counter() - period_start
        print(f"[time] {period_name}: {fmt_elapsed(period_elapsed)}")

        if failures:
            print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    _write_selected_ell_summary_txt(summary_root, period_selected_frames)

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[done] all periods complete  total: {fmt_elapsed(total_elapsed)}")


if __name__ == "__main__":
    main()
