from __future__ import annotations

"""
Experiment 2 all-offset runner — 1-second bars (time-based aggregation).

Mirrors `runner_exp2_all_offset.py` exactly, except `prepared.price` now
comes from per-second close prices via `src.bars.prepare_month_bars`. The
gate (strict 80% pass-rate on adaptive-k D + Monobit), test battery, and
output schema are unchanged so results sit beside the transaction-time
strict outputs and can be compared directly.

ell semantic: ell=1 -> one bit per 1-second bar; ell=k -> one bit per k seconds.

Edit the configuration block below, then run:
    python scripts/runner_exp2_all_offset_1sbars.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

import numpy as np
import pandas as pd

from src.bars import BarsCoverage, prepare_month_bars
from src.bitstream import build_all_offset_bitstreams, save_bitstream
from src.data_io import filter_month_files
from src.exp2_summary import build_combined_row
from src.utils import ASSET_ORDER, fmt_elapsed, period_dir_name, run_plot_subprocess


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

# 1s-bar grid: ell counts in seconds, not trades. Smaller range than the
# transaction-time runner because each bar already aggregates ~trades/s.
AGG_START = 10
AGG_STOP = 700
AGG_STEP = 2
AGG_LEVELS: list[int] = list(range(AGG_START, AGG_STOP + 1, AGG_STEP))

MAX_ROWS: int | None = None
MIN_BIT_COUNT = 2000

# MAX_ROWS = 100000
# MIN_BIT_COUNT = 50

ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
VALID_OFFSET_RATIO_THRESHOLD = 0.80

SAVE_BITSTREAMS = False
SAVE_OFFSET_STATS = False

MAX_WORKERS = 3

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)

_rows_prefix = f"rows{MAX_ROWS // 10000}w/" if MAX_ROWS is not None else ""
OUTPUT_ROOT = Path(
    f"data/processed/experiment2/{_rows_prefix}all-offset-per-month-1sbars({AGG_START},{AGG_STOP},{AGG_STEP})"
)


# Per-asset processing


def process_asset(
    asset: str,
    months: list[str],
    output_dir: Path,
) -> tuple[list[dict[str, object]], list[BarsCoverage]]:
    """Load all month files for an asset and run all-offset analysis on 1s bars."""
    asset_dir = INPUT_ROOT / asset
    if not asset_dir.exists():
        print(f"[skip] asset directory not found: {asset_dir}")
        return [], []

    files = filter_month_files(sorted(asset_dir.glob("*.csv")), months)
    if not files:
        print(f"[skip] no matching csv files under: {asset_dir}")
        return [], []

    pairs = [prepare_month_bars(path, max_rows=MAX_ROWS) for path in files]
    prepared_months = [p for p, _ in pairs]
    coverages = [c for _, c in pairs]

    rows: list[dict[str, object]] = []

    for agg_level in sorted(set(AGG_LEVELS)):
        print(f"[processing] asset={asset:<8}  ell={agg_level}")

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
                    timestamp_unit="1s_bars",
                    analysis_scope="combined_offset_1sbars",
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

    return rows, coverages


# Acceptance summary


def _summarize_acceptance(
    combined_df: pd.DataFrame,
) -> pd.DataFrame:
    selection_rows: list[dict[str, object]] = []

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
                    "is_acceptable_with_runs": False,
                }
            )
            continue

        predictability_pass_rate = float(
            (valid["predictability_pvalue"] >= ALPHA).mean()
        )
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
        is_acceptable = bool(
            valid_offset_ratio >= VALID_OFFSET_RATIO_THRESHOLD
            and predictability_pass_rate >= PASS_RATE_THRESHOLD
            and monobit_pass_rate >= PASS_RATE_THRESHOLD
        )
        is_acceptable_with_runs = bool(
            is_acceptable and runs_pass_rate >= PASS_RATE_THRESHOLD
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
                "is_acceptable_with_runs": is_acceptable_with_runs,
            }
        )

    selection_df = pd.DataFrame(selection_rows).sort_values(["asset", "agg_level"])
    return selection_df


# Output helpers


def _save_asset_outputs(
    output_dir: Path,
    combined_df: pd.DataFrame,
    selection_df: pd.DataFrame,
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
        print(f"[saved] {asset} → {asset_dir}")


def _merge_all_assets(output_dir: Path) -> None:
    by_asset_dir = output_dir / "by_asset"
    suffixes = ["k_acceptance"]
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


def _format_coverage_section(
    period_coverage: list[tuple[list[str], dict[str, list[BarsCoverage]]]],
    header_assets: list[str],
    display_names: dict[str, str],
) -> list[str]:
    """Format the bars-coverage section grouped by month.

    seconds_total is a property of the calendar month (asset-independent), so
    it's emitted once per month-header rather than repeated per asset row.
    Multi-month windows produce multiple month-headers in sequence.
    """
    if not period_coverage:
        return []

    lines: list[str] = [
        "",
        "Bars coverage (per month):",
        "  seconds_total = calendar seconds in the month (shown in header)",
        "  with_trades   = seconds containing >=1 trade",
        "  coverage      = with_trades / seconds_total",
        "  empty seconds are forward-filled and produce zero deltas (filtered out)",
        "",
    ]
    for _, coverage_by_asset in period_coverage:
        per_month: dict[str, dict[str, BarsCoverage]] = {}
        month_seconds: dict[str, int] = {}
        for asset, coverages in coverage_by_asset.items():
            for cov in coverages:
                per_month.setdefault(cov.month_label, {})[asset] = cov
                month_seconds.setdefault(cov.month_label, cov.seconds_total)

        for month_label in sorted(per_month.keys()):
            sec_total = month_seconds[month_label]
            lines.append(f"== {month_label} ==  seconds_total = {sec_total:,}")
            for asset in header_assets:
                display = display_names[asset]
                cov = per_month[month_label].get(asset)
                if cov is None:
                    lines.append(f"  {display:<5}  (no data)")
                else:
                    lines.append(
                        f"  {display:<5}  "
                        f"with_trades = {cov.seconds_with_trades:<10,}  "
                        f"coverage = {cov.coverage:.3f}"
                    )
            lines.append("")
    return lines


def _write_coverage_summary_txt(
    summary_root: Path,
    period_coverage: list[tuple[list[str], dict[str, list[BarsCoverage]]]],
) -> None:
    if not period_coverage:
        return

    display_names = {
        "BNBUSDT": "BNB",
        "BTCUSDT": "BTC",
        "DOGEUSDT": "DOGE",
        "ETHUSDT": "ETH",
        "SOLUSDT": "SOL",
    }
    header_assets = [asset for asset in ASSET_ORDER if asset in display_names]

    coverage_section = _format_coverage_section(
        period_coverage, header_assets, display_names
    )

    output_path = summary_root / "selected_ell_by_window.txt"
    text = "\n".join(
        [
            "1-second bars coverage summary.",
            "",
            f"AGG_START = {AGG_START}",
            f"AGG_STOP = {AGG_STOP}",
            f"AGG_STEP = {AGG_STEP}",
            *coverage_section,
        ]
    )
    output_path.write_text(text, encoding="utf-8")
    print(f"[saved] {output_path}")


# Main


def main() -> None:
    import time

    project_root = Path(__file__).resolve().parent.parent
    total_start = time.perf_counter()
    summary_root = project_root / OUTPUT_ROOT
    summary_root.mkdir(parents=True, exist_ok=True)
    period_coverage: list[tuple[list[str], dict[str, list[BarsCoverage]]]] = []

    for months in PERIODS:
        period_name = period_dir_name(months)
        output_dir = summary_root / period_name
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"[period] {period_name}  months={months}  (1s bars)")
        print(f"{'='*60}")

        period_start = time.perf_counter()
        all_rows: list[dict[str, object]] = []
        coverage_by_asset: dict[str, list[BarsCoverage]] = {}
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(process_asset, asset, months, output_dir): asset
                for asset in ASSETS
            }
            for future in as_completed(future_map):
                asset = future_map[future]
                try:
                    rows, coverages = future.result()
                    all_rows.extend(rows)
                    coverage_by_asset[asset] = coverages
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
        selection_df = _summarize_acceptance(combined_df)

        _save_asset_outputs(output_dir, combined_df, selection_df)
        _merge_all_assets(output_dir)
        period_coverage.append((months, coverage_by_asset))
        run_plot_subprocess(
            project_root,
            "scripts/plot_exp2_all_offset_1sbars.py",
            output_dir,
        )

        period_elapsed = time.perf_counter() - period_start
        print(f"[time] {period_name}: {fmt_elapsed(period_elapsed)}")

        if failures:
            print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    _write_coverage_summary_txt(summary_root, period_coverage)

    run_plot_subprocess(
        project_root,
        "scripts/select_ell_exp2_1sbars.py",
        summary_root,
    )

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[done] all periods complete  total: {fmt_elapsed(total_elapsed)}")


if __name__ == "__main__":
    main()
