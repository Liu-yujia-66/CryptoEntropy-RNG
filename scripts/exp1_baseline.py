from __future__ import annotations

"""
Experiment 1 baseline randomness analysis for Binance spot aggTrades data.

Recommended first validation run:
    python scripts/exp1_baseline.py --max-rows 100000
"""

import argparse
import math
import os
from pathlib import Path
from typing import Literal
from itertools import groupby

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))

import matplotlib
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


AGGTRADE_COLUMNS = [
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "is_buyer_maker",
    "is_best_match",
]

TimeUnit = Literal["ms", "us"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 1 baseline randomness analysis on Binance aggTrades data."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/raw/binance/spot/aggTrades"),
        help="Root directory containing asset subdirectories with aggTrades CSV files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/processed/experiment1"),
        help="Root directory for summary tables, bitstreams, and plots.",
    )
    parser.add_argument(
        "--assets",
        nargs="*",
        default=["BTCUSDT", "ETHUSDT"],
        help="Asset directories to process.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap per file for debugging.",
    )
    parser.add_argument(
        "--aggregation-k",
        type=int,
        default=1,
        help="Non-overlapping aggregation window size for price changes.",
    )
    parser.add_argument(
        "--plot-sample-size",
        type=int,
        default=500,
        help="Number of leading bits to show in the bitstream preview plot.",
    )
    parser.add_argument(
        "--acf-max-lag",
        type=int,
        default=50,
        help="Maximum lag used in the autocorrelation plot.",
    )
    return parser.parse_args()


def detect_time_unit(series: pd.Series) -> TimeUnit:
    digits = len(str(int(series.iloc[0])))
    if digits >= 16:
        return "us"
    if digits >= 13:
        return "ms"
    raise ValueError(f"Unsupported timestamp width: {digits} digits")


def load_aggtrades(path: Path, max_rows: int | None) -> pd.DataFrame:
    df = pd.read_csv(path, names=AGGTRADE_COLUMNS, nrows=max_rows)
    df["price"] = pd.to_numeric(df["price"], errors="raise")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="raise")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="raise").astype("int64")
    df["aggregate_trade_id"] = pd.to_numeric(
        df["aggregate_trade_id"], errors="raise"
    ).astype("int64")
    return df


def convert_timestamps(timestamp_series: pd.Series, time_unit: TimeUnit) -> pd.Series:
    timestamp_array = timestamp_series.to_numpy(dtype="int64")
    converted = pd.to_datetime(timestamp_array, unit=time_unit, utc=True)
    return pd.Series(converted, index=timestamp_series.index)


def shannon_entropy_from_bits(bits: np.ndarray) -> float:
    if bits.size == 0:
        return float("nan")
    p1 = bits.mean()
    p0 = 1.0 - p1
    entropy = 0.0
    for p in (p0, p1):
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def longest_run(bits: np.ndarray, value: int) -> int:
    max_run = 0
    current = 0
    for bit in bits:
        if bit == value:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def count_runs(bits: np.ndarray) -> int:
    if bits.size == 0:
        return 0
    return 1 + int(np.sum(bits[1:] != bits[:-1]))


def run_lengths(bits: np.ndarray) -> list[int]:
    return [sum(1 for _ in group) for _, group in groupby(bits)]


def runs_test(bits: np.ndarray) -> tuple[float, float]:
    n = bits.size
    if n < 2:
        return float("nan"), float("nan")
    n1 = int(bits.sum())
    n0 = n - n1
    if n0 == 0 or n1 == 0:
        return float("nan"), float("nan")

    runs = count_runs(bits)
    expected = float(1 + (2 * n1 * n0) / n)
    variance = float(2 * n1 * n0 * (2 * n1 * n0 - n) / (n**2 * (n - 1)))
    if variance <= 0:
        return float("nan"), float("nan")

    z_score = float((runs - expected) / math.sqrt(variance))
    p_value = float(math.erfc(abs(z_score) / math.sqrt(2)))
    return float(z_score), float(p_value)


def monobit_test(bits: np.ndarray) -> tuple[float, float]:
    n = bits.size
    if n == 0:
        return float("nan"), float("nan")
    s = int(2 * bits.sum() - n)
    z_score = float(abs(s) / math.sqrt(n))
    p_value = float(math.erfc(z_score / math.sqrt(2)))
    return float(z_score), float(p_value)


def lag_autocorrelation(bits: np.ndarray, lag: int) -> float:
    if lag <= 0 or lag >= bits.size:
        return float("nan")
    x = bits[:-lag].astype(float)
    y = bits[lag:].astype(float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


# 对 price delta 做非重叠窗口聚合，k=1 时保持实验 1 原始基线逻辑
def aggregate_price_deltas(price_deltas: pd.Series, aggregation_k: int) -> pd.Series:
    if aggregation_k < 1:
        raise ValueError("aggregation_k must be >= 1")

    clean = price_deltas.dropna().reset_index(drop=True)
    if aggregation_k == 1:
        return clean

    usable_length = (len(clean) // aggregation_k) * aggregation_k
    trimmed = clean.iloc[:usable_length]
    if trimmed.empty:
        return pd.Series(dtype="float64")

    aggregated = trimmed.groupby(np.arange(len(trimmed)) // aggregation_k).sum()
    return aggregated.astype(float).reset_index(drop=True)


def build_bitstream(
    df: pd.DataFrame, aggregation_k: int
) -> tuple[pd.DataFrame, dict[str, float]]:
    ordered = df.sort_values("aggregate_trade_id").copy()
    ordered["raw_price_delta"] = ordered["price"].diff()
    zero_delta_count = int((ordered["raw_price_delta"] == 0).sum())

    if aggregation_k == 1:
        bit_df = ordered.loc[
            ordered["raw_price_delta"] != 0,
            [
                "aggregate_trade_id",
                "timestamp",
                "price",
                "raw_price_delta",
            ],
        ].copy()
        bit_df = bit_df.dropna(subset=["raw_price_delta"])
        bit_df = bit_df.rename(columns={"raw_price_delta": "price_delta"})
    else:
        aggregated_deltas = aggregate_price_deltas(
            ordered["raw_price_delta"], aggregation_k
        )
        bit_df = pd.DataFrame({"price_delta": aggregated_deltas})
        bit_df = bit_df.loc[bit_df["price_delta"] != 0].copy()
        bit_df["aggregate_trade_id"] = np.arange(1, len(bit_df) + 1, dtype=int)
        bit_df["timestamp"] = pd.NA
        bit_df["price"] = pd.NA

    bit_df["bit"] = (bit_df["price_delta"] > 0).astype(int)

    stats = {
        "aggregation_k": int(aggregation_k),
        "input_rows": int(len(df)),
        "retained_rows": int(len(bit_df)),
        "zero_delta_count": zero_delta_count,
        "zero_delta_ratio": zero_delta_count / len(df) if len(df) else float("nan"),
        "duplicate_timestamp_count": int(df["timestamp"].duplicated().sum()),
    }
    return bit_df, stats


def plot_results(
    bit_df: pd.DataFrame,
    output_dir: Path,
    label: str,
    plot_sample_size: int,
    acf_max_lag: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(14, 14))
    grid = GridSpec(3, 2, figure=fig, height_ratios=[1, 1, 1.1])
    ax_price = fig.add_subplot(grid[0, 0])
    ax_delta = fig.add_subplot(grid[0, 1])
    ax_preview = fig.add_subplot(grid[1, 0])
    ax_acf = fig.add_subplot(grid[1, 1])
    ax_runs = fig.add_subplot(grid[2, :])
    fig.suptitle(f"Experiment 1 Baseline Analysis: {label}")

    ax_price.plot(bit_df["event_time"], bit_df["price"], linewidth=0.6)
    ax_price.set_title("Price Time Series")
    ax_price.set_xlabel("Time")
    ax_price.set_ylabel("Price")

    ax_delta.hist(bit_df["price_delta"], bins=100)
    ax_delta.set_title("Price Delta Distribution")
    ax_delta.set_xlabel("Delta")
    ax_delta.set_ylabel("Frequency")

    preview = bit_df["bit"].to_numpy()[:plot_sample_size]
    ax_preview.step(np.arange(preview.size), preview, where="post")
    ax_preview.set_title(f"Bitstream Preview (first {preview.size} bits)")
    ax_preview.set_xlabel("Index")
    ax_preview.set_ylabel("Bit")
    ax_preview.set_ylim(-0.1, 1.1)

    bits = bit_df["bit"].to_numpy()
    max_lag = min(acf_max_lag, max(1, bits.size - 1))
    plot_acf(bits, lags=max_lag, ax=ax_acf, title="Bitstream ACF")

    runs = run_lengths(bits)
    ax_runs.hist(runs, bins=50, log=True)
    ax_runs.set_title("Run Length Distribution")
    ax_runs.set_xlabel("Run Length")
    ax_runs.set_ylabel("Frequency (Log Scale)")

    fig.tight_layout()
    fig.savefig(output_dir / f"{label}_plots.png", dpi=150)
    plt.close(fig)


def process_file(
    path: Path,
    asset: str,
    output_root: Path,
    max_rows: int | None,
    aggregation_k: int,
    plot_sample_size: int,
    acf_max_lag: int,
) -> dict[str, float | str]:
    df = load_aggtrades(path, max_rows=max_rows)
    preview = df.head(5).copy()
    time_unit = detect_time_unit(df["timestamp"])
    duplicate_preview_timestamps = int(preview["timestamp"].duplicated().sum())

    df["event_time"] = convert_timestamps(df["timestamp"], time_unit)
    start_time = df["event_time"].iloc[0]
    end_time = df["event_time"].iloc[-1]
    duration_seconds = float((end_time - start_time).total_seconds())

    bit_df, build_stats = build_bitstream(df, aggregation_k=aggregation_k)
    if aggregation_k == 1:
        bit_df["event_time"] = convert_timestamps(bit_df["timestamp"], time_unit)
    else:
        bit_df["event_time"] = pd.NaT

    bits = bit_df["bit"].to_numpy()
    p1 = float(bits.mean()) if bits.size else float("nan")
    p0 = 1.0 - p1 if bits.size else float("nan")
    entropy = shannon_entropy_from_bits(bits)
    lag1 = lag_autocorrelation(bits, 1)
    monobit_z, monobit_p = monobit_test(bits)
    runs_z, runs_p = runs_test(bits)
    bits_per_second = (
        float(bits.size / duration_seconds) if duration_seconds > 0 else float("nan")
    )

    date_label = path.stem.split("-")[-3:]
    day = "-".join(date_label)
    label = f"{asset}_{day}"

    standardized = bit_df[["event_time", "price", "price_delta", "bit"]].copy()
    if aggregation_k == 1:
        standardized["event_time"] = standardized["event_time"].dt.strftime(
            "%Y-%m-%d %H:%M:%S.%f%z"
        )

    bit_output_dir = output_root / "bitstreams" / asset
    bit_output_dir.mkdir(parents=True, exist_ok=True)
    standardized.to_csv(bit_output_dir / f"{label}_bitstream.csv", index=False)

    plot_output_dir = output_root / "plots" / asset
    plot_results(
        bit_df=bit_df,
        output_dir=plot_output_dir,
        label=label,
        plot_sample_size=plot_sample_size,
        acf_max_lag=acf_max_lag,
    )

    return {
        "asset": asset,
        "date": day,
        "source_file": str(path),
        "timestamp_unit": time_unit,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "preview_duplicate_timestamps": duplicate_preview_timestamps,
        **build_stats,
        "bit_count": int(bits.size),
        "bits_per_second": bits_per_second,
        "p0": p0,
        "p1": p1,
        "shannon_entropy": entropy,
        "lag1_autocorrelation": lag1,
        "monobit_z": monobit_z,
        "monobit_pvalue": monobit_p,
        "runs_count": count_runs(bits),
        "runs_z": runs_z,
        "runs_pvalue": runs_p,
        "longest_run_0": longest_run(bits, 0),
        "longest_run_1": longest_run(bits, 1),
    }


def main() -> None:
    args = parse_args()
    summary_rows: list[dict[str, float | str]] = []

    for asset in args.assets:
        asset_dir = args.input_root / asset
        if not asset_dir.exists():
            print(f"[skip] asset directory not found: {asset_dir}")
            continue

        files = sorted(asset_dir.glob("*.csv"))
        if not files:
            print(f"[skip] no csv files found under: {asset_dir}")
            continue

        for path in files:
            print(f"[processing] {path}")
            summary = process_file(
                path=path,
                asset=asset,
                output_root=args.output_root,
                max_rows=args.max_rows,
                aggregation_k=args.aggregation_k,
                plot_sample_size=args.plot_sample_size,
                acf_max_lag=args.acf_max_lag,
            )
            summary_rows.append(summary)

    if not summary_rows:
        print("No files processed.")
        return

    summary_df = pd.DataFrame(summary_rows).sort_values(["asset", "date"])
    args.output_root.mkdir(parents=True, exist_ok=True)
    summary_name = (
        f"summary_exp1_baseline_k{args.aggregation_k}_{args.max_rows}rows.csv"
        if args.max_rows is not None
        else f"summary_exp1_baseline_k{args.aggregation_k}_full.csv"
    )
    summary_path = args.output_root / summary_name
    summary_df.to_csv(summary_path, index=False)

    print(f"[done] saved summary to {summary_path}")


if __name__ == "__main__":
    main()
