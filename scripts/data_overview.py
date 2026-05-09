from __future__ import annotations

"""
Data overview for the asset universe used by Experiments 1 and 2.

Scans the monthly aggTrades archives and reports the trades/s rate for each
(asset, month), at two granularities:

    * agg_trades_per_second  -- one row per same-timestamp same-price taker
                                 fill cluster (Binance aggTrades convention).
    * raw_trades_per_second  -- one count per individual maker fill, recovered
                                 from the [first_trade_id, last_trade_id]
                                 interval that Binance preserves on every
                                 aggTrades row. Each aggTrades row contributes
                                 (last_trade_id - first_trade_id + 1) raw
                                 trades. No re-download from the trades
                                 endpoint is needed.

The raw figure is what the cross-market comparison with Onofri et al. (2025)
Table 2 and Shternshis & Marmi (2025) Table 1 needs, since both papers report
per-execution counts from LOBSTER message files (one row = one fill).

Outputs (under data/processed/data_overview/):
    by_asset_month.csv    -- one row per (asset, year_month).
    by_asset_summary.csv  -- one row per asset: median + [p5, p95] across
                              months, sorted by raw_tps_median descending.
                              This is the data source for thesis Table 4.1.

Run:
    python scripts/data_overview.py

The INPUT_ROOT default and the env-var override match
scripts/runner_exp2_all_offset.py so this script reads the same archive layout
as Experiment 2.
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.data_io import detect_time_unit, filter_month_files


# ---------------------------------------------------------------------------
# Configuration -- mirrors runner_exp2_all_offset.py defaults.
# ---------------------------------------------------------------------------

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

MONTHS: list[str] = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03",
]

DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
DEFAULT_OUTPUT_ROOT = Path("data/processed/data_overview")

# Percentile pair used for the per-asset summary (Table 4.1 source).
PERCENTILE_LO = 5
PERCENTILE_HI = 95

# Slim load: only the three columns needed for the trades/s computation.
# Indices refer to the 8-column aggTrades schema in src.data_io.AGGTRADE_COLUMNS.
USECOLS_NAMES = ["first_trade_id", "last_trade_id", "timestamp"]
USECOLS_INDICES = [3, 4, 5]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute per-(asset, month) trades/s for thesis Table 4.1."
    )
    parser.add_argument(
        "--input-root", type=Path, default=DEFAULT_INPUT_ROOT,
        help=("Root containing <ASSET>/...-YYYY-MM.csv monthly aggTrades "
              "archives. Defaults to $CRYPTOENTROPY_INPUT_ROOT or "
              "data/raw/binance/spot/aggTrades."),
    )
    parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
        help="Where to write by_asset_month.csv and by_asset_summary.csv.",
    )
    parser.add_argument(
        "--assets", nargs="*", default=ASSETS,
        help="Assets to scan. Defaults to the ASSETS config constant.",
    )
    parser.add_argument(
        "--months", nargs="*", default=MONTHS,
        help="Months in 'YYYY-MM' form. Defaults to the MONTHS config constant.",
    )
    return parser.parse_args()


def scan_one_file(path: Path) -> dict[str, float | int | str]:
    """Read a monthly aggTrades CSV with only the columns trades/s needs."""
    df = pd.read_csv(
        path,
        header=None,
        usecols=USECOLS_INDICES,
        names=USECOLS_NAMES,
        dtype={
            "first_trade_id": "int64",
            "last_trade_id": "int64",
            "timestamp": "int64",
        },
    )
    if df.empty:
        raise ValueError(f"empty file: {path}")

    # Detect ms vs us using the same logic as src.data_io.detect_time_unit so
    # the duration_seconds reported here is comparable to Exp 2's.
    time_unit = detect_time_unit(df["timestamp"])
    divisor = 1_000.0 if time_unit == "ms" else 1_000_000.0

    # Use min/max for robustness (Binance archives are sorted, but min/max is
    # equivalent and tolerates any ordering).
    first_ts = int(df["timestamp"].min())
    last_ts = int(df["timestamp"].max())
    duration_seconds = float(last_ts - first_ts) / divisor

    agg_trades_count = int(len(df))
    raw_trades_count = int(
        (df["last_trade_id"] - df["first_trade_id"] + 1).sum()
    )

    return {
        # "source_file": str(path),
        "timestamp_unit": time_unit,
        "agg_trades_count": agg_trades_count,
        "raw_trades_count": raw_trades_count,
        "duration_seconds": duration_seconds,
        "first_timestamp_int": first_ts,
        "last_timestamp_int": last_ts,
    }


def derive_rates(stats: dict[str, float | int | str]) -> dict[str, float]:
    duration = float(stats["duration_seconds"])
    agg_count = int(stats["agg_trades_count"])
    raw_count = int(stats["raw_trades_count"])
    if duration <= 0 or agg_count <= 0:
        return {
            "agg_trades_per_second": float("nan"),
            "raw_trades_per_second": float("nan"),
            "raw_to_agg_ratio": float("nan"),
        }
    return {
        "agg_trades_per_second": agg_count / duration,
        "raw_trades_per_second": raw_count / duration,
        "raw_to_agg_ratio": raw_count / agg_count,
    }


def build_summary(by_month_df: pd.DataFrame) -> pd.DataFrame:
    """Per-asset (median, [p_lo, p_hi]) across months. Source for Table 4.1."""
    summary_rows: list[dict[str, object]] = []
    for asset, grp in by_month_df.groupby("asset", sort=True):
        raw_tps = grp["raw_trades_per_second"].to_numpy()
        agg_tps = grp["agg_trades_per_second"].to_numpy()
        ratio = grp["raw_to_agg_ratio"].to_numpy()
        summary_rows.append({
            "asset": asset,
            "n_months": int(len(grp)),
            "raw_tps_median": float(np.median(raw_tps)),
            f"raw_tps_p{PERCENTILE_LO}": float(np.percentile(raw_tps, PERCENTILE_LO)),
            f"raw_tps_p{PERCENTILE_HI}": float(np.percentile(raw_tps, PERCENTILE_HI)),
            "agg_tps_median": float(np.median(agg_tps)),
            f"agg_tps_p{PERCENTILE_LO}": float(np.percentile(agg_tps, PERCENTILE_LO)),
            f"agg_tps_p{PERCENTILE_HI}": float(np.percentile(agg_tps, PERCENTILE_HI)),
            "raw_to_agg_ratio_median": float(np.median(ratio)),
        })
    summary_df = pd.DataFrame(summary_rows)
    return summary_df.sort_values("raw_tps_median", ascending=False).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    total_start = time.perf_counter()

    rows: list[dict[str, object]] = []
    for asset in args.assets:
        asset_dir = args.input_root / asset
        if not asset_dir.exists():
            print(f"[skip] asset directory not found: {asset_dir}")
            continue

        files = filter_month_files(sorted(asset_dir.glob("*.csv")), args.months)
        if not files:
            print(f"[skip] no matching monthly files under: {asset_dir}")
            continue

        for path in files:
            year_month = "-".join(path.stem.split("-")[-2:])
            t0 = time.perf_counter()
            stats = scan_one_file(path)
            rates = derive_rates(stats)
            elapsed = time.perf_counter() - t0
            rows.append({
                "asset": asset,
                "year_month": year_month,
                **stats,
                **rates,
            })
            print(
                f"[scan] {asset} {year_month}  "
                f"agg/s={rates['agg_trades_per_second']:7.2f}  "
                f"raw/s={rates['raw_trades_per_second']:7.2f}  "
                f"ratio={rates['raw_to_agg_ratio']:5.2f}  "
                f"({elapsed:.1f}s)"
            )

    if not rows:
        print("[error] no rows produced -- check INPUT_ROOT and ASSETS/MONTHS configuration")
        return

    by_month_df = pd.DataFrame(rows).sort_values(["asset", "year_month"]).reset_index(drop=True)
    args.output_root.mkdir(parents=True, exist_ok=True)
    by_month_path = args.output_root / "by_asset_month.csv"
    by_month_df.to_csv(by_month_path, index=False)
    print(f"\n[saved] {by_month_path}  ({len(by_month_df)} rows)")

    summary_df = build_summary(by_month_df)
    summary_path = args.output_root / "by_asset_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"[saved] {summary_path}  ({len(summary_df)} rows)")

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[done] total elapsed: {total_elapsed:.1f}s")
    print()
    print("Per-asset trades/s (sorted by raw_tps_median, descending):")
    print(summary_df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
