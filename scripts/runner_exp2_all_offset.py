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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from src.bitstream import build_all_offset_bitstreams, save_bitstream
from src.data_io import filter_month_files, prepare_month_data
from src.stats import summarize_bits_full
from src.utils import fmt_elapsed


# Configuration


ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

# Periods to process — each entry is a list of "YYYY-MM" month strings.
PERIODS: list[list[str]] = [
    # ["2026-01"],
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

MAX_ROWS: int | None = None
MIN_BIT_COUNT = 2000
ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
HISTORY_LENGTH = 1
SAVE_BITSTREAMS = False
MAX_WORKERS = 3

INPUT_ROOT = Path("data/raw/binance/spot/aggTrades")
OUTPUT_ROOT = Path("data/processed/experiment2/all-offset-optimized")


# Directory naming


def _period_dir_name(months: list[str]) -> str:
    """
    Auto-generate a directory name from a list of 'YYYY-MM' strings.

    Examples:
        ["2025-01","2025-02","2025-03"]  → full-2025.01-03
        ["2025-07",..."2025-12"]         → full-2025.07-12
        ["2025-01",..."2025-12"]         → full-2025-12month
    """
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


def _build_combined_row(
    asset: str,
    sampling_k: int,
    offset: int,
    combined_bits: np.ndarray,
    combined_duration_seconds: float,
    source_files: list[Path],
) -> dict[str, object]:
    bits_per_second = (
        float(combined_bits.size / combined_duration_seconds)
        if combined_duration_seconds > 0
        else float("nan")
    )
    metadata: dict[str, object] = {
        "asset": asset,
        "date": "combined",
        "source_file": ",".join(str(p) for p in source_files),
        "timestamp_unit": "mixed",
        "start_time": "",
        "end_time": "",
        "duration_seconds": combined_duration_seconds,
        "preview_duplicate_timestamps": float("nan"),
        "sampling_k": sampling_k,
        "offset": offset,
        "input_rows": float("nan"),
        "sampled_rows": float("nan"),
        "retained_rows": int(combined_bits.size),
        "zero_delta_count": float("nan"),
        "zero_delta_ratio": float("nan"),
        "duplicate_timestamp_count": float("nan"),
        "analysis_scope": "combined_offset",
        "bits_per_second": bits_per_second,
    }
    row = summarize_bits_full(
        bits=combined_bits,
        history_length=HISTORY_LENGTH,
        metadata=metadata,
    )
    row["bits_per_second"] = bits_per_second
    return row


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

    for sampling_k in sorted(set(SAMPLING_K_VALUES)):
        print(f"[processing] asset={asset}  k={sampling_k}")

        combined_bits_by_offset: dict[int, list[np.ndarray]] = {
            offset: [] for offset in range(sampling_k)
        }
        combined_duration_seconds = 0.0

        for prepared in prepared_months:
            combined_duration_seconds += prepared.context.duration_seconds
            for bitstream in build_all_offset_bitstreams(prepared, sampling_k):
                combined_bits_by_offset[bitstream.offset].append(bitstream.bits)

        for offset in range(sampling_k):
            chunks = combined_bits_by_offset[offset]
            if not chunks:
                continue
            combined_bits = np.concatenate(chunks)
            rows.append(
                _build_combined_row(
                    asset=asset,
                    sampling_k=sampling_k,
                    offset=offset,
                    combined_bits=combined_bits,
                    combined_duration_seconds=combined_duration_seconds,
                    source_files=files,
                )
            )
            if SAVE_BITSTREAMS:
                bitstream_path = (
                    output_dir
                    / "bitstreams"
                    / f"k_{sampling_k}"
                    / asset
                    / f"{asset}_combined_offset{offset}_k{sampling_k}.csv"
                )
                save_bitstream(combined_bits, bitstream_path)

    return rows


# Acceptance summary


def _summarize_acceptance(
    combined_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []

    grouped = combined_df.groupby(["asset", "sampling_k"], sort=True)
    for key, group in grouped:
        asset, sampling_k = cast(tuple[str, int], key)
        valid = group[group["bit_count"] >= MIN_BIT_COUNT].copy()
        valid_offset_count = int(len(valid))
        total_offset_count = int(len(group))

        if valid.empty:
            selection_rows.append(
                {
                    "asset": asset,
                    "sampling_k": sampling_k,
                    "total_offset_count": total_offset_count,
                    "valid_offset_count": 0,
                    "valid_offset_ratio": 0.0,
                    "predictability_pass_rate": float("nan"),
                    "monobit_pass_rate": float("nan"),
                    "runs_pass_rate": float("nan"),
                    "approximate_entropy_pass_rate": float("nan"),
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
        monobit_pass_rate = float((valid["monobit_pvalue"] >= ALPHA).mean())
        runs_pass_rate = float((valid["runs_pvalue"] >= ALPHA).mean())
        approximate_entropy_pass_rate = float(
            (valid["approximate_entropy_pvalue"] >= ALPHA).mean()
        )
        avg_bits_per_second = float(valid["bits_per_second"].mean())
        is_acceptable = bool(
            predictability_pass_rate >= PASS_RATE_THRESHOLD
            and monobit_pass_rate >= PASS_RATE_THRESHOLD
            and runs_pass_rate >= PASS_RATE_THRESHOLD
        )

        selection_rows.append(
            {
                "asset": asset,
                "sampling_k": sampling_k,
                "total_offset_count": total_offset_count,
                "valid_offset_count": valid_offset_count,
                "valid_offset_ratio": valid_offset_count / total_offset_count,
                "predictability_pass_rate": predictability_pass_rate,
                "monobit_pass_rate": monobit_pass_rate,
                "runs_pass_rate": runs_pass_rate,
                "approximate_entropy_pass_rate": approximate_entropy_pass_rate,
                "avg_bits_per_second": avg_bits_per_second,
                "min_bit_count_required": MIN_BIT_COUNT,
                "alpha": ALPHA,
                "pass_rate_threshold": PASS_RATE_THRESHOLD,
                "is_acceptable": is_acceptable,
            }
        )

    selection_df = pd.DataFrame(selection_rows).sort_values(["asset", "sampling_k"])

    for asset, group in selection_df.groupby("asset", sort=True):
        acceptable = group[group["is_acceptable"]].sort_values("sampling_k")
        if acceptable.empty:
            selected_rows.append(
                {
                    "asset": asset,
                    "selected_k": float("nan"),
                    "selection_status": "no_acceptable_k",
                }
            )
            continue
        chosen = acceptable.iloc[0]
        selected_rows.append(
            {
                "asset": asset,
                "selected_k": int(chosen["sampling_k"]),
                "selection_status": "selected_smallest_acceptable_k",
                "predictability_pass_rate": chosen["predictability_pass_rate"],
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
    for suffix in ["offset_stats", "k_acceptance", "selected_k"]:
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


def _run_plot(project_root: Path, output_dir: Path) -> None:
    cmd = [
        str(project_root / ".venv" / "bin" / "python"),
        "scripts/plot_exp2_all_offsets_optimized.py",
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
            ["asset", "sampling_k", "offset"]
        )
        selection_df, selected_df = _summarize_acceptance(combined_df)

        _save_asset_outputs(output_dir, combined_df, selection_df, selected_df)
        _merge_all_assets(output_dir)
        _run_plot(project_root, output_dir)

        period_elapsed = time.perf_counter() - period_start
        print(f"[time] {period_name}: {fmt_elapsed(period_elapsed)}")

        if failures:
            print(f"[warn] {len(failures)} asset(s) failed: {failures}")

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[done] all periods complete  total: {fmt_elapsed(total_elapsed)}")


if __name__ == "__main__":
    main()
