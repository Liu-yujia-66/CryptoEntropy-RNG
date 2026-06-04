from __future__ import annotations

"""
Experiment 1 baseline runner — per-(asset, month) granularity, ell=1, offset=0.

Mirrors the exp2 runner layout: a top-of-file configuration block, a parallel
ThreadPoolExecutor across assets, and a downstream plot subprocess. One
(asset, month) cell -> one bit stream -> one summary row.

Edit the configuration block below, then run:
    python scripts/runner_exp1_baseline.py
"""

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))

import numpy as np
import pandas as pd

from src.data_io import filter_month_files, prepare_month_data
from src.stats import (
    _adaptive_k,
    approximate_entropy_test,
    count_runs,
    entropy_predictability_test,
    lag_autocorrelation,
    longest_run,
    monobit_test,
    runs_test,
    shannon_entropy_from_bits,
)
from src.utils import fmt_elapsed, run_plot_subprocess

# Configuration


ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

MONTHS: list[str] = [
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
]

MAX_ROWS: int | None = None
# MAX_ROWS = 100000

MAX_WORKERS = 5

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
OUTPUT_ROOT = Path("data/processed/experiment1")


# Per-asset processing


_PRINT_LOCK = threading.Lock()


def _log(msg: str) -> None:
    with _PRINT_LOCK:
        print(msg, flush=True)


def process_asset(asset: str) -> list[dict[str, object]]:
    """Load all matching monthly files for one asset and produce summary rows."""
    asset_dir = INPUT_ROOT / asset
    if not asset_dir.exists():
        _log(f"[skip] asset directory not found: {asset_dir}")
        return []

    files = filter_month_files(sorted(asset_dir.glob("*.csv")), MONTHS)
    if not files:
        _log(f"[skip] no matching csv files under: {asset_dir}")
        return []

    rows: list[dict[str, object]] = []
    for path in files:
        t0 = time.perf_counter()
        prepared = prepare_month_data(path, max_rows=MAX_ROWS)

        # ell=1, offset=0: sort -> diff -> drop zero -> sign -> bit.
        price = prepared.price
        input_rows = int(price.size)
        delta = np.diff(price)
        nonzero = delta != 0
        bits = (delta[nonzero] > 0).astype(np.uint8)
        zero_delta_count = int(input_rows - 1 - bits.size) if input_rows else 0
        duplicate_timestamp_count = int(
            pd.Series(prepared.timestamp).duplicated().sum()
        )

        duration_seconds = prepared.context.duration_seconds
        bits_per_second = (
            float(bits.size / duration_seconds)
            if duration_seconds > 0
            else float("nan")
        )
        p1 = float(bits.mean()) if bits.size else float("nan")
        p0 = 1.0 - p1 if bits.size else float("nan")
        entropy = shannon_entropy_from_bits(bits)
        shannon_bias = abs(entropy - 1.0) if bits.size else float("nan")
        lag1 = lag_autocorrelation(bits, 1)
        monobit_z, monobit_p = monobit_test(bits)
        runs_z, runs_p = runs_test(bits)

        # Conditional-predictability battery: NIST Approximate Entropy plus the
        # entropy-predictability test D at the adaptive block length
        # k = floor(0.5 log2 n) and at the fixed k = 2 ("pairs of signs")
        # diagnostic. Same battery as Experiment 2's gate.
        k_adaptive = _adaptive_k(int(bits.size))
        approx_entropy, approx_entropy_p = approximate_entropy_test(bits)
        _, _, predictability_p = entropy_predictability_test(
            bits, history_length=k_adaptive - 1
        )
        _, _, predictability_k2_p = entropy_predictability_test(
            bits, history_length=1
        )

        rows.append(
            {
                "asset": asset,
                "month": prepared.context.month_label,
                "timestamp_unit": prepared.context.timestamp_unit,
                "start_time": prepared.context.start_time_iso,
                "end_time": prepared.context.end_time_iso,
                "duration_seconds": duration_seconds,
                "input_rows": input_rows,
                "retained_rows": int(bits.size),
                "zero_delta_count": zero_delta_count,
                "zero_delta_ratio": (
                    zero_delta_count / input_rows if input_rows else float("nan")
                ),
                "duplicate_timestamp_count": duplicate_timestamp_count,
                "bit_count": int(bits.size),
                "bits_per_second": bits_per_second,
                "p0": p0,
                "p1": p1,
                "shannon_entropy": entropy,
                "shannon_bias": shannon_bias,
                "lag1_autocorrelation": lag1,
                "monobit_z": monobit_z,
                "monobit_pvalue": monobit_p,
                "runs_count": count_runs(bits),
                "runs_z": runs_z,
                "runs_pvalue": runs_p,
                "longest_run_0": longest_run(bits, 0),
                "longest_run_1": longest_run(bits, 1),
                "approximate_entropy": approx_entropy,
                "approximate_entropy_pvalue": approx_entropy_p,
                "predictability_k": k_adaptive,
                "predictability_pvalue": predictability_p,
                "predictability_k2_pvalue": predictability_k2_p,
            }
        )
        _log(
            f"[done] {asset:<8}  {prepared.context.month_label}  "
            f"bits={bits.size:>10,}  {fmt_elapsed(time.perf_counter() - t0)}"
        )
    return rows


# Main


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    output_root = project_root / OUTPUT_ROOT
    output_root.mkdir(parents=True, exist_ok=True)

    total_start = time.perf_counter()
    all_rows: list[dict[str, object]] = []
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(process_asset, asset): asset for asset in ASSETS}
        for future in as_completed(future_map):
            asset = future_map[future]
            try:
                all_rows.extend(future.result())
                _log(f"[asset done] {asset}")
            except Exception as exc:
                _log(f"[error] {asset}: {exc}")
                failures.append(asset)

    if not all_rows:
        print("No files processed.")
        return

    summary_df = pd.DataFrame(all_rows).sort_values(["asset", "month"])

    by_asset_dir = output_root / "by_asset"
    by_asset_dir.mkdir(parents=True, exist_ok=True)
    for asset in sorted(summary_df["asset"].unique()):
        asset_dir = by_asset_dir / asset
        asset_dir.mkdir(parents=True, exist_ok=True)
        summary_df[summary_df["asset"] == asset].to_csv(
            asset_dir / f"{asset}_summary_exp1_baseline.csv", index=False
        )

    summary_path = output_root / "all_assets_summary_exp1_baseline.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"[saved] {summary_path}  ({len(summary_df)} rows)")

    if failures:
        print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    run_plot_subprocess(
        project_root,
        "scripts/plot_exp1_baseline.py",
        output_root,
    )

    print(f"[time] total: {fmt_elapsed(time.perf_counter() - total_start)}")


if __name__ == "__main__":
    main()
