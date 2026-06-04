"""
Experiment 4 — pairwise 1-bit mutual information pool matrix.

Builds a 5x5 pairwise 1-bit MI matrix on per-second sign bits over the 9-month
calibration window, using PAIR-specific drop-any-zero (kept positions are where
both assets have non-zero Delta-p). MI is pooled by per-pair joint-count
accumulation across months; per-month rows are also written to check stability.

Run from the project root (use --months / --assets to subset):
    python scripts/runner_exp4_mi_matrix.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mutual_info import (
    compute_pairwise_mi_matrix,
    recommend_subsets_by_max_mi,
    recommend_subsets_by_sum_mi,
)


DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

# Calibration window = 2025-01 .. 2025-09 (9 months).
DEFAULT_MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05",
    "2025-06", "2025-07", "2025-08", "2025-09",
]

NEAR_INDEPENDENT_THRESHOLD_BITS = 1e-3

DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)

# Outputs land beside the rest of Experiment 4 calibration artefacts.
OUTPUT_ROOT = Path("data/processed/experiment4/calibration/mi")


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument(
        "--assets",
        default=",".join(DEFAULT_ASSETS),
        help=f"comma-separated asset list (default: {','.join(DEFAULT_ASSETS)})",
    )
    parser.add_argument(
        "--months",
        default=",".join(DEFAULT_MONTHS),
        help=f"comma-separated YYYY-MM months (default: calibration window {DEFAULT_MONTHS[0]}..{DEFAULT_MONTHS[-1]})",
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help=f"aggTrades root (default: {DEFAULT_INPUT_ROOT})",
    )
    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_ROOT),
        help=f"output directory (default: {OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="optional per-file row cap for smoke runs (default: full month)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-(pair, month) progress lines",
    )
    args = parser.parse_args()

    assets = _parse_csv_list(args.assets)
    months = _parse_csv_list(args.months)
    if len(assets) < 2:
        print(f"[fatal] need at least 2 assets, got {assets}")
        return 1
    if not months:
        print("[fatal] no months given")
        return 1

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"[fatal] input root does not exist: {input_root}")
        print(
            "        set CRYPTOENTROPY_INPUT_ROOT or pass --input-root to override"
        )
        return 1
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    n_pairs = len(assets) * (len(assets) - 1) // 2
    print(f"=== exp4 MI matrix ===")
    print(f"assets        : {assets}")
    print(f"months        : {months[0]} .. {months[-1]}  ({len(months)} months)")
    print(f"pairs         : {n_pairs}")
    print(f"input_root    : {input_root}")
    print(f"output_root   : {output_root}")
    print(f"threshold     : I < {NEAR_INDEPENDENT_THRESHOLD_BITS} bits = near-independent (plan v3.2 §2.4)")
    print()

    started = time.time()
    result = compute_pairwise_mi_matrix(
        assets=assets,
        months=months,
        input_root=input_root,
        max_rows=args.max_rows,
        verbose=not args.quiet,
    )
    elapsed = time.time() - started

    mi_path = output_root / "mi_pool_matrix.csv"
    rho_path = output_root / "rho_pool_matrix.csv"
    per_month_path = output_root / "mi_per_month_long.csv"
    pool_long_path = output_root / "mi_pool_summary_long.csv"
    summary_path = output_root / "mi_pool_summary.json"

    result.mi_matrix.to_csv(mi_path)
    result.rho_matrix.to_csv(rho_path)
    result.per_month_long.to_csv(per_month_path, index=False)
    result.pool_summary_long.to_csv(pool_long_path, index=False)

    pool_long = result.pool_summary_long
    n_below_threshold = int(
        (pool_long["pool_mi_bits"] < NEAR_INDEPENDENT_THRESHOLD_BITS).sum()
    )
    n_above_threshold = int(
        (pool_long["pool_mi_bits"] >= NEAR_INDEPENDENT_THRESHOLD_BITS).sum()
    )

    subsets_max = recommend_subsets_by_max_mi(result.mi_matrix)
    subsets_sum = recommend_subsets_by_sum_mi(result.mi_matrix)

    summary = {
        "assets": list(assets),
        "months": list(months),
        "n_months": len(months),
        "n_pairs": n_pairs,
        "near_independent_threshold_bits": NEAR_INDEPENDENT_THRESHOLD_BITS,
        "pool_max_mi_bits": float(pool_long["pool_mi_bits"].max()),
        "pool_min_mi_bits": float(pool_long["pool_mi_bits"].min()),
        "pool_mean_mi_bits": float(pool_long["pool_mi_bits"].mean()),
        "pool_max_abs_rho": float(pool_long["pool_rho_pearson"].abs().max()),
        "pool_min_abs_rho": float(pool_long["pool_rho_pearson"].abs().min()),
        "pool_mean_abs_rho": float(pool_long["pool_rho_pearson"].abs().mean()),
        "n_pairs_near_independent": n_below_threshold,
        "n_pairs_above_threshold": n_above_threshold,
        "subset_recommendations_by_max_pairwise_mi": {
            str(n): rec for n, rec in subsets_max.items()
        },
        "subset_recommendations_by_sum_pairwise_mi": {
            str(n): rec for n, rec in subsets_sum.items()
        },
        "elapsed_seconds": round(elapsed, 1),
    }
    with summary_path.open("w") as fp:
        json.dump(summary, fp, indent=2)

    print()
    print(f"=== outputs ===")
    print(f"  {mi_path}")
    print(f"  {rho_path}")
    print(f"  {per_month_path}    ({len(result.per_month_long):,} rows)")
    print(f"  {pool_long_path}    ({len(pool_long):,} rows)")
    print(f"  {summary_path}")
    print()
    print(f"=== pool MI matrix (bits) ===")
    print(result.mi_matrix.round(5).to_string(na_rep="  --  "))
    print()
    print(f"=== pool Pearson matrix ===")
    print(result.rho_matrix.round(4).to_string(na_rep="  --  "))
    print()
    print(f"=== subset recommendations (plan v3.2 §2.2 alternative ordering) ===")
    print(f"  by min(max_pairwise_MI):")
    for n in sorted(subsets_max):
        rec = subsets_max[n]
        print(
            f"    n={n}: {rec['subset']}  "
            f"max_MI={rec['max_pairwise_mi_bits']:.5f}  "
            f"sum_MI={rec['sum_pairwise_mi_bits']:.5f}"
        )
    print(f"  by min(sum_pairwise_MI):")
    for n in sorted(subsets_sum):
        rec = subsets_sum[n]
        print(
            f"    n={n}: {rec['subset']}  "
            f"sum_MI={rec['sum_pairwise_mi_bits']:.5f}  "
            f"max_MI={rec['max_pairwise_mi_bits']:.5f}"
        )
    print()
    print(
        f"=== thresholds ===\n"
        f"  pairs below {NEAR_INDEPENDENT_THRESHOLD_BITS} bits  (near-independent): "
        f"{n_below_threshold} / {n_pairs}\n"
        f"  pairs at or above threshold:                       "
        f"{n_above_threshold} / {n_pairs}\n"
        f"  pool max MI: {summary['pool_max_mi_bits']:.5f} bits "
        f"(|rho| up to {summary['pool_max_abs_rho']:.4f})"
    )
    print()
    print(f"elapsed: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
