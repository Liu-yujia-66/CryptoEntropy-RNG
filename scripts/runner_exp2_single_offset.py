from __future__ import annotations

"""
Experiment 2 single-offset runner (offset=0).

Sweeps the same k grid as runner_exp2_all_offset.py but uses only offset=0,
producing a per-(asset, k) summary CSV used to plot -log(p-value) vs k curves.

Edit the configuration block below, then run:
    python scripts/runner_exp2_single_offset.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from src.bitstream import build_offset_bitstream_from_arrays, save_bitstream
from src.data_io import filter_month_files, prepare_month_data
from src.stats import summarize_bits_full
from src.utils import fmt_elapsed


# Configuration

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

PERIODS: list[list[str]] = [
    # Quarterly
    ["2025-01", "2025-02", "2025-03"],
    ["2025-04", "2025-05", "2025-06"],
    ["2025-07", "2025-08", "2025-09"],
    ["2025-10", "2025-11", "2025-12"],
    ["2026-01", "2026-02", "2026-03"],
    # Half-year
    ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"],
    ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"],
    # Full year
    [
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
    ],
]

K_START = 250
K_STOP = 5000
K_STEP = 250
SAMPLING_K_VALUES: list[int] = [50, 100] + list(range(K_START, K_STOP + 1, K_STEP))

OFFSET = 0  # fixed single offset

MAX_ROWS: int | None = None
MIN_BIT_COUNT = 2000
HISTORY_LENGTH = 1
SAVE_BITSTREAMS = False
MAX_WORKERS = 3

INPUT_ROOT = Path("data/raw/binance/spot/aggTrades")
OUTPUT_ROOT = Path("data/processed/experiment2/single-offset")


# Directory naming (shared convention with exp2_runner.py)


def _period_dir_name(months: list[str]) -> str:
    parsed = sorted((int(m[:4]), int(m[5:])) for m in months)
    first_year, first_month = parsed[0]
    last_year, last_month = parsed[-1]
    n = len(parsed)

    if n == 12 and first_year == last_year:
        return f"full-12month-{first_year}"
    if n == 1:
        return f"full-1month-{first_year}.{first_month:02d}"
    return f"full-{n}month-{first_year}.{first_month:02d}-{last_month:02d}"


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

    for sampling_k in sorted(set(SAMPLING_K_VALUES)):
        print(f"[processing] asset={asset}  k={sampling_k}  offset={OFFSET}")

        bits_chunks: list[np.ndarray] = []
        combined_duration_seconds = 0.0

        for prepared in prepared_months:
            combined_duration_seconds += prepared.context.duration_seconds
            bitstream = build_offset_bitstream_from_arrays(
                aggregate_trade_id=prepared.aggregate_trade_id,
                timestamp=prepared.timestamp,
                price=prepared.price,
                sampling_k=sampling_k,
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
            "sampling_k": sampling_k,
            "offset": OFFSET,
            "source_file": ",".join(str(p) for p in files),
            "duration_seconds": combined_duration_seconds,
            "bits_per_second": bits_per_second,
            "analysis_scope": "single_offset",
        }

        row = summarize_bits_full(
            bits=combined_bits,
            history_length=HISTORY_LENGTH,
            metadata=metadata,
        )
        row["bits_per_second"] = bits_per_second
        row["valid"] = bool(combined_bits.size >= MIN_BIT_COUNT)
        rows.append(row)

        if SAVE_BITSTREAMS and combined_bits.size > 0:
            bitstream_path = (
                output_dir
                / "bitstreams"
                / f"k_{sampling_k}"
                / asset
                / f"{asset}_combined_offset{OFFSET}_k{sampling_k}.csv"
            )
            save_bitstream(combined_bits, bitstream_path)

    return rows


# Output helpers


def _save_outputs(output_dir: Path, summary_df: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # All-assets combined
    all_path = output_dir / "summary_exp2_single_offset.csv"
    summary_df.to_csv(all_path, index=False)
    print(f"[saved] {all_path}")

    # Per-asset
    by_asset_dir = output_dir / "by_asset"
    by_asset_dir.mkdir(parents=True, exist_ok=True)
    for asset in sorted(summary_df["asset"].unique()):
        asset_path = by_asset_dir / f"{asset}_summary_exp2_single_offset.csv"
        summary_df[summary_df["asset"] == asset].to_csv(asset_path, index=False)
        print(f"[saved] {asset_path}")


def _run_plot(project_root: Path, output_dir: Path) -> None:
    cmd = [
        str(project_root / ".venv" / "bin" / "python"),
        "scripts/plot_exp2_single_offset.py",
        "--summary-dir",
        str(output_dir),
    ]
    print(f"[plot] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, check=False)
    if result.returncode != 0:
        print(f"[warn] plot script exited with code {result.returncode}")


# Main


def main() -> None:
    import time

    project_root = Path(__file__).resolve().parent.parent
    total_start = time.perf_counter()

    for months in PERIODS:
        period_name = _period_dir_name(months)
        output_dir = project_root / OUTPUT_ROOT / period_name

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

        summary_df = pd.DataFrame(all_rows).sort_values(["asset", "sampling_k"])
        _save_outputs(output_dir, summary_df)
        _run_plot(project_root, output_dir)

        period_elapsed = time.perf_counter() - period_start
        print(f"[time] {period_name}: {fmt_elapsed(period_elapsed)}")

        if failures:
            print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[done] all periods complete  total: {fmt_elapsed(total_elapsed)}")


if __name__ == "__main__":
    main()
