from __future__ import annotations

"""
Parallel runner for exp2_all_offsets.py — one subprocess per asset.

After all assets complete, per-asset CSVs are merged into all_assets_*.csv.

Edit the configuration block below, then run:
    python scripts/run_exp2_all_offsets_parallel.py
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration — mirror exp2_all_offsets.py defaults
# ---------------------------------------------------------------------------

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
# ASSETS = ["BTCUSDT", "ETHUSDT"]

MONTHS = ["2026-01", "2026-02", "2026-03"]

SAMPLING_K_VALUES = [50, 100, 200, 500, 1000, 2000, 5000]

# None = full data; set an int for debugging (e.g. 100_000)
# MAX_ROWS: int | None = 100_000
MAX_ROWS: int | None = None

MIN_BIT_COUNT = 2000
ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80

# Number of assets to process in parallel
MAX_WORKERS = 3

# Limit internal numpy/scipy thread count per subprocess
PER_PROCESS_NUM_THREADS = "1"

OUTPUT_ROOT = Path("data/processed/experiment2/all-offset")
SUMMARY_SUFFIXES = ["monthly", "combined", "k_acceptance", "selected_k"]

# ---------------------------------------------------------------------------


def _summary_dir_name(max_rows: int | None) -> str:
    return f"rows{max_rows}" if max_rows is not None else "full"


def _build_command(project_root: Path, asset: str) -> list[str]:
    cmd = [
        str(project_root / ".venv" / "bin" / "python"),
        "scripts/exp2_all_offsets.py",
        "--assets",
        asset,
        "--months",
        *MONTHS,
        "--sampling-k-values",
        *[str(k) for k in SAMPLING_K_VALUES],
        "--min-bit-count",
        str(MIN_BIT_COUNT),
        "--alpha",
        str(ALPHA),
        "--pass-rate-threshold",
        str(PASS_RATE_THRESHOLD),
    ]
    if MAX_ROWS is not None:
        cmd.extend(["--max-rows", str(MAX_ROWS)])
    return cmd


def _run_asset(project_root: Path, asset: str) -> tuple[str, int]:
    cmd = _build_command(project_root, asset)
    env = os.environ.copy()
    for var in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ]:
        env[var] = PER_PROCESS_NUM_THREADS

    print(f"[start] {asset}  cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, env=env, check=False)
    return asset, result.returncode


def _merge_all_assets(output_dir: Path) -> None:
    """Concatenate per-asset CSVs into all_assets_*.csv at output_dir root."""
    by_asset_dir = output_dir / "by_asset"

    for suffix in SUMMARY_SUFFIXES:
        frames: list[pd.DataFrame] = []
        for asset in sorted(ASSETS):
            candidate = (
                by_asset_dir / asset / f"{asset}_summary_exp2_all_offsets_{suffix}.csv"
            )
            if candidate.exists():
                frames.append(pd.read_csv(candidate))
            else:
                print(f"[warn] missing {candidate}")

        if not frames:
            print(f"[warn] no data for suffix '{suffix}', skipping merge")
            continue

        merged = pd.concat(frames, ignore_index=True)
        out_path = output_dir / f"all_assets_summary_exp2_all_offsets_{suffix}.csv"
        merged.to_csv(out_path, index=False)
        print(f"[merge] {out_path}")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / OUTPUT_ROOT / _summary_dir_name(MAX_ROWS)
    failures: list[tuple[str, int]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_run_asset, project_root, asset): asset for asset in ASSETS
        }
        for future in as_completed(futures):
            asset = futures[future]
            try:
                _, return_code = future.result()
            except Exception as exc:
                print(f"[error] {asset}: {exc}")
                failures.append((asset, -1))
                continue

            if return_code == 0:
                print(f"[done] {asset}")
            else:
                print(f"[failed] {asset} exit_code={return_code}")
                failures.append((asset, return_code))

    if failures:
        print("\n[summary] failed assets:")
        for asset, code in failures:
            print(f"  {asset}  exit_code={code}")
        sys.exit(1)

    print("\n[merging] combining per-asset summaries ...")
    _merge_all_assets(output_dir)
    print("[done] all assets complete")


if __name__ == "__main__":
    main()
