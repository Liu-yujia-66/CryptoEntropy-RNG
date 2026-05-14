from __future__ import annotations

"""
Experiment 2 single-offset runner (offset=0).

Sweeps the same k grid as runner_exp2_all_offset.py but uses only offset=0,
producing a per-(asset, k) summary CSV used to plot -log(p-value) vs k curves.

Edit the configuration block below, then run:
    python scripts/runner_exp2_single_offset.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from src.bitstream import build_offset_bitstream_from_arrays, save_bitstream
from src.data_io import filter_month_files, prepare_month_data
from src.exp2_summary import format_selection_table
from src.stats import summarize_bits_full
from src.utils import fmt_elapsed, period_dir_name, run_plot_subprocess

# Configuration

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

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
]

AGG_START = 50
AGG_STOP = 2000
AGG_STEP = 25
AGG_LEVELS: list[int] = list(range(AGG_START, AGG_STOP + 1, AGG_STEP))

OFFSET = 0  # fixed single offset

MAX_ROWS: int | None = None
MIN_BIT_COUNT = 2000
ALPHA = 0.01
SAVE_BITSTREAMS = False
MAX_WORKERS = 3

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
# OUTPUT_ROOT = Path("data/processed/experiment2/single-offset")
OUTPUT_ROOT = Path(
    f"data/processed/experiment2/single-offset-per-month({AGG_START},{AGG_STOP},{AGG_STEP})"
)


# Per-asset processing


def process_asset(
    asset: str,
    months: list[str],
    output_dir: Path,
) -> list[dict[str, object]]:
    """Load all month files for an asset and run single-offset analysis for every k."""
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
        print(f"[processing] asset={asset}  ell={agg_level}  offset={OFFSET}")

        bits_chunks: list[np.ndarray] = []
        combined_duration_seconds = 0.0

        for prepared in prepared_months:
            combined_duration_seconds += prepared.context.duration_seconds
            bitstream = build_offset_bitstream_from_arrays(
                price=prepared.price,
                agg_level=agg_level,
                offset=OFFSET,
            )
            bits_chunks.append(bitstream.bits)

        combined_bits = (
            np.concatenate(bits_chunks) if bits_chunks else np.array([], dtype=np.uint8)
        )

        bits_per_second = (
            float(combined_bits.size / combined_duration_seconds)
            if combined_duration_seconds > 0
            else float("nan")
        )

        metadata: dict[str, object] = {
            "asset": asset,
            "agg_level": agg_level,
            "offset": OFFSET,
            "source_file": ",".join(str(p) for p in files),
            "duration_seconds": combined_duration_seconds,
            "bits_per_second": bits_per_second,
            "analysis_scope": "single_offset",
        }

        row = summarize_bits_full(
            bits=combined_bits,
            metadata=metadata,
        )
        row["bits_per_second"] = bits_per_second
        row["valid"] = bool(combined_bits.size >= MIN_BIT_COUNT)
        rows.append(row)

        if SAVE_BITSTREAMS and combined_bits.size > 0:
            bitstream_path = (
                output_dir
                / "bitstreams"
                / f"agg_{agg_level}"
                / asset
                / f"{asset}_combined_offset{OFFSET}_agg{agg_level}.csv"
            )
            save_bitstream(combined_bits, bitstream_path)

    return rows


# Output helpers


def _select_ell_per_asset(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Pick smallest ell where the single-offset bitstream passes
    predictability and monobit at alpha, with sufficient bits."""
    selected_rows: list[dict[str, object]] = []
    for asset, group in summary_df.groupby("asset", sort=True):
        valid = group[group["bit_count"] >= MIN_BIT_COUNT]
        accepted = valid[
            (valid["predictability_pvalue"] >= ALPHA)
            & (valid["monobit_pvalue"] >= ALPHA)
        ].sort_values("agg_level")
        if accepted.empty:
            selected_rows.append(
                {
                    "asset": asset,
                    "selected_agg_level": float("nan"),
                    "selection_status": "no_acceptable_ell",
                }
            )
            continue
        chosen = accepted.iloc[0]
        selected_rows.append(
            {
                "asset": asset,
                "selected_agg_level": int(chosen["agg_level"]),
                "selection_status": "selected_smallest_acceptable_ell",
                "predictability_pvalue": chosen["predictability_pvalue"],
                "monobit_pvalue": chosen["monobit_pvalue"],
                "runs_pvalue": chosen.get("runs_pvalue", float("nan")),
                "bits_per_second": chosen["bits_per_second"],
            }
        )
    return pd.DataFrame(selected_rows).sort_values("asset")


def _save_outputs(
    output_dir: Path, summary_df: pd.DataFrame, selected_df: pd.DataFrame
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # All-assets combined
    all_path = output_dir / "summary_exp2_single_offset.csv"
    summary_df.to_csv(all_path, index=False)
    print(f"[saved] {all_path}")

    selected_path = output_dir / "all_assets_summary_exp2_selected_k.csv"
    selected_df.to_csv(selected_path, index=False)
    print(f"[saved] {selected_path}")

    # Per-asset
    by_asset_dir = output_dir / "by_asset"
    by_asset_dir.mkdir(parents=True, exist_ok=True)
    for asset in sorted(summary_df["asset"].unique()):
        asset_path = by_asset_dir / f"{asset}_summary_exp2_single_offset.csv"
        summary_df[summary_df["asset"] == asset].to_csv(asset_path, index=False)
        print(f"[saved] {asset_path}")


def _write_selected_ell_summary_txt(
    summary_root: Path,
    period_selected_frames: list[tuple[list[str], pd.DataFrame]],
) -> None:
    if not period_selected_frames:
        return

    intro = [
        "Single-offset gate (offset=0). Smallest ell with predictability and",
        "monobit p-values >= alpha and bit_count >= MIN_BIT_COUNT.",
        "",
        f"OFFSET = {OFFSET}",
        f"ALPHA = {ALPHA}",
        f"MIN_BIT_COUNT = {MIN_BIT_COUNT}",
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
            print(f"[warn] no rows produced for period {period_name}, skipping")
            continue

        summary_df = pd.DataFrame(all_rows).sort_values(["asset", "agg_level"])
        selected_df = _select_ell_per_asset(summary_df)
        _save_outputs(output_dir, summary_df, selected_df)
        period_selected_frames.append((months, selected_df.copy()))
        run_plot_subprocess(
            project_root,
            "scripts/plot_exp2_single_offset.py",
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
