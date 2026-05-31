"""
Experiment 4 — all-subsets calibration runner.

Sweeps every C(5, n) asset subset for n in {2, 3, 4, 5}, total 26
subsets x 9 calibration months = 234 cells. For each (subset, month):
build the XOR-fused stream, sweep ell on the +Runs all-offset gate,
record ell_star (or None if no ell passes). Per-subset outputs land in
their own directory; an additional top-level all_subsets_summary.csv
aggregates the 26 subsets so the comparison figure can be drawn
directly.

Output structure:

    data/processed/experiment4/calibration_all_subsets/
    |-- all_subsets_summary.csv          # one row per (n, subset)
    |-- all_subsets_summary.json         # parameter summary
    |-- n2_BNBUSDT-BTCUSDT/
    |       |-- subset.json
    |       |-- ell_n_choice.json
    |       |-- witness_offset.json
    |       |-- per_month_ell_star.csv
    |       |-- stream_utilization.json
    |-- n2_BNBUSDT-DOGEUSDT/...
    |-- ... (26 directories total)

Witness offset selection is per-subset on the witness month
(default 2025-09).

Run from the project root:
    python scripts/runner_exp4_calibration_all_subsets.py

Override examples:
    # smoke test: only n=2
    python scripts/runner_exp4_calibration_all_subsets.py --n-values 2

    # restrict assets for a quicker sanity check
    python scripts/runner_exp4_calibration_all_subsets.py \\
        --assets BTCUSDT,BNBUSDT,SOLUSDT --n-values 2,3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.calibration import (
    p80,
    select_ell_star_from_grid,
    select_witness_offset,
)
from src.fusion import build_fused_stream_from_signs, build_per_asset_signs


DEFAULT_CALIBRATION_MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05",
    "2025-06", "2025-07", "2025-08", "2025-09",
]
DEFAULT_WITNESS_MONTH = "2025-09"
DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
DEFAULT_N_VALUES = [2, 3, 4, 5]

# ell grid: piling-up convergence (see src/calibration.py unit tests) means
# real fused streams should hit a passing ell well before 400.
ELL_MIN = 1
ELL_MAX = 400
ELL_STEP = 1

ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
VALID_OFFSET_RATIO_THRESHOLD = 0.80
MIN_BIT_COUNT = 2000

DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
DEFAULT_OUTPUT_ROOT = Path("data/processed/experiment4/calibration_all_subsets")

# Short labels for log output (full names still used for filesystem / data).
_ASSET_SHORT = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}


def _short_subset(subset: list[str] | tuple[str, ...]) -> str:
    return ",".join(_ASSET_SHORT.get(a, a) for a in subset)


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _subset_dir_name(n: int, subset: list[str]) -> str:
    """Stable filesystem-safe name for a subset directory."""
    return f"n{n}_" + "-".join(sorted(subset))


def _calibrate_one_cell(
    subset: list[str],
    month: str,
    signs_cache: dict,
    ell_grid: list[int],
) -> dict:
    """Build fused, sweep ell, return diagnostic dict for one (n, month) cell."""
    per_asset = [signs_cache[a] for a in subset]
    fused = build_fused_stream_from_signs(subset, month, per_asset)

    if fused.kept_seconds < MIN_BIT_COUNT:
        return {
            "month": month,
            "ell_star": None,
            "ell_star_reason": "fused_stream_below_min_bit_count",
            "raw_seconds": fused.raw_seconds,
            "kept_seconds": fused.kept_seconds,
            "survival_rate": fused.survival_rate,
            "naive_baseline": fused.naive_baseline,
            "empirical_independent_baseline": fused.empirical_independent_baseline,
            "survival_vs_naive_ratio": fused.survival_vs_naive_ratio,
            "survival_vs_empirical_ratio": fused.survival_vs_empirical_ratio,
            "fused_p1": float(fused.fused_bits.mean()) if fused.kept_seconds > 0 else 0.0,
            "swept_ell_count": 0,
        }

    swept_count = 0

    def progress(_ev) -> None:
        nonlocal swept_count
        swept_count += 1

    ell_star, history = select_ell_star_from_grid(
        fused_bits=fused.fused_bits,
        ell_grid=ell_grid,
        alpha=ALPHA,
        pass_rate_threshold=PASS_RATE_THRESHOLD,
        valid_offset_ratio_threshold=VALID_OFFSET_RATIO_THRESHOLD,
        min_bit_count=MIN_BIT_COUNT,
        on_progress=progress,
    )

    return {
        "month": month,
        "ell_star": ell_star,
        "ell_star_reason": "passed_gate" if ell_star is not None else "no_ell_passed",
        "raw_seconds": fused.raw_seconds,
        "kept_seconds": fused.kept_seconds,
        "survival_rate": fused.survival_rate,
        "naive_baseline": fused.naive_baseline,
        "empirical_independent_baseline": fused.empirical_independent_baseline,
        "survival_vs_naive_ratio": fused.survival_vs_naive_ratio,
        "survival_vs_empirical_ratio": fused.survival_vs_empirical_ratio,
        "fused_p1": float(fused.fused_bits.mean()),
        "swept_ell_count": swept_count,
        "final_ell_d_pass_rate": history[-1].d_pass_rate if history else float("nan"),
        "final_ell_monobit_pass_rate": history[-1].monobit_pass_rate if history else float("nan"),
        "final_ell_runs_pass_rate": history[-1].runs_pass_rate if history else float("nan"),
    }


def _write_outputs_for_subset(
    n: int,
    subset: list[str],
    cell_results: list[dict],
    ell_star_n: int | None,
    witness_info: dict | None,
    output_root: Path,
    subdir_name: str,
) -> None:
    """Write one (n, subset) calibration result tree."""
    n_dir = output_root / subdir_name
    n_dir.mkdir(parents=True, exist_ok=True)

    (n_dir / "subset.json").write_text(
        json.dumps(
            {
                "n": n,
                "subset": subset,
                "source": "all_subsets_enumeration",
            },
            indent=2,
        )
    )

    per_month_df = pd.DataFrame(cell_results)
    per_month_df.to_csv(n_dir / "per_month_ell_star.csv", index=False)

    passed_months = [r["month"] for r in cell_results if r["ell_star"] is not None]
    passed_ells = [r["ell_star"] for r in cell_results if r["ell_star"] is not None]
    (n_dir / "ell_n_choice.json").write_text(
        json.dumps(
            {
                "n": n,
                "ell_star_n": ell_star_n,
                "method": "P80(per_month_ell_star, ignoring None)",
                "n_calibration_months": len(cell_results),
                "n_months_passed": len(passed_months),
                "passed_months": passed_months,
                "passed_ell_stars": passed_ells,
                "ell_stars_raw_per_month": [
                    {"month": r["month"], "ell_star": r["ell_star"]}
                    for r in cell_results
                ],
                "gate_config": {
                    "alpha": ALPHA,
                    "pass_rate_threshold": PASS_RATE_THRESHOLD,
                    "valid_offset_ratio_threshold": VALID_OFFSET_RATIO_THRESHOLD,
                    "min_bit_count": MIN_BIT_COUNT,
                    "ell_grid": f"[{ELL_MIN}, {ELL_MAX}] step {ELL_STEP}",
                    "aggregation_operator": "XOR-aggregation (see src/calibration.py)",
                },
            },
            indent=2,
        )
    )

    if witness_info is None:
        (n_dir / "witness_offset.json").write_text(
            json.dumps(
                {
                    "n": n,
                    "witness_offset": None,
                    "reason": "no ell_star_n (gate failed on too many months)",
                },
                indent=2,
            )
        )
    else:
        (n_dir / "witness_offset.json").write_text(
            json.dumps(witness_info, indent=2)
        )

    survival_rows = [
        {
            "month": r["month"],
            "raw_seconds": r["raw_seconds"],
            "kept_seconds": r["kept_seconds"],
            "survival_rate": r["survival_rate"],
            "naive_baseline_0p85_pow_n": r["naive_baseline"],
            "empirical_independent_baseline": r["empirical_independent_baseline"],
            "survival_vs_naive_ratio": r["survival_vs_naive_ratio"],
            "survival_vs_empirical_ratio": r["survival_vs_empirical_ratio"],
            "fused_p1": r["fused_p1"],
        }
        for r in cell_results
    ]
    (n_dir / "stream_utilization.json").write_text(
        json.dumps(
            {
                "n": n,
                "per_month": survival_rows,
                "summary": {
                    "survival_rate_median": float(
                        pd.Series([r["survival_rate"] for r in cell_results]).median()
                    ),
                    "survival_vs_empirical_median": float(
                        pd.Series(
                            [r["survival_vs_empirical_ratio"] for r in cell_results]
                        ).median()
                    ),
                    "fused_p1_median": float(
                        pd.Series([r["fused_p1"] for r in cell_results]).median()
                    ),
                },
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experiment 4 all-subsets calibration runner."
    )
    parser.add_argument(
        "--assets",
        default=",".join(DEFAULT_ASSETS),
        help=f"asset universe (default: {DEFAULT_ASSETS})",
    )
    parser.add_argument(
        "--n-values",
        default=",".join(str(n) for n in DEFAULT_N_VALUES),
        help=f"fusion sizes to enumerate (default: {DEFAULT_N_VALUES})",
    )
    parser.add_argument(
        "--months",
        default=",".join(DEFAULT_CALIBRATION_MONTHS),
        help=f"calibration months (default: {DEFAULT_CALIBRATION_MONTHS[0]}..{DEFAULT_CALIBRATION_MONTHS[-1]})",
    )
    parser.add_argument(
        "--witness-month",
        default=DEFAULT_WITNESS_MONTH,
        help=f"witness offset selection month (default: {DEFAULT_WITNESS_MONTH})",
    )
    parser.add_argument(
        "--ell-min", type=int, default=ELL_MIN, help=f"(default: {ELL_MIN})"
    )
    parser.add_argument(
        "--ell-max", type=int, default=ELL_MAX, help=f"(default: {ELL_MAX})"
    )
    parser.add_argument(
        "--ell-step", type=int, default=ELL_STEP, help=f"(default: {ELL_STEP})"
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help=f"aggTrades root (default: {DEFAULT_INPUT_ROOT})",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=f"output root (default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="optional per-file row cap (default: full month)",
    )
    args = parser.parse_args()

    assets = _parse_csv_list(args.assets)
    n_values = [int(s) for s in _parse_csv_list(args.n_values)]
    months = _parse_csv_list(args.months)
    witness_month = args.witness_month

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"[fatal] input root does not exist: {input_root}")
        return 1
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    ell_grid = list(range(args.ell_min, args.ell_max + 1, args.ell_step))

    # Enumerate every C(|assets|, n) subset for each n.
    subset_groups: list[tuple[int, list[str]]] = []
    for n in n_values:
        for subset in combinations(assets, n):
            subset_groups.append((n, list(subset)))

    n_subsets = len(subset_groups)
    n_total_cells = n_subsets * len(months)

    print(f"=== exp4 all-subsets calibration ===")
    print(f"assets         : {assets}")
    print(f"n values       : {n_values}")
    print(f"months         : {months[0]}..{months[-1]} ({len(months)} months)")
    print(f"witness month  : {witness_month}")
    print(f"ell grid       : [{args.ell_min}, {args.ell_max}] step {args.ell_step}")
    print(f"subsets to scan: {n_subsets}")
    print(
        f"total cells    : {n_total_cells} = {n_subsets} subsets x {len(months)} months"
    )
    print(f"input_root     : {input_root}")
    print(f"output_root    : {output_root}")
    print()
    print(f"  subsets per n:")
    by_n: dict[int, list[list[str]]] = {n: [] for n in n_values}
    for n, subset in subset_groups:
        by_n[n].append(subset)
    for n in n_values:
        labels = [", ".join(s) for s in by_n[n]]
        print(f"    n={n} ({len(by_n[n])}): " + " | ".join(labels))
    print()

    started = time.time()

    # Outer loop: month (cache all asset signs once per month, reuse for
    # every subset that touches them).
    per_subset_cell_results: dict[tuple[int, tuple[str, ...]], list[dict]] = {
        (n, tuple(subset)): [] for n, subset in subset_groups
    }

    for month_idx, month in enumerate(months, start=1):
        month_start = time.time()
        print(f"--- month {month} ({month_idx}/{len(months)}) ---")
        signs_cache = {}
        for asset in assets:
            t0 = time.time()
            signs_cache[asset] = build_per_asset_signs(
                asset, month, input_root, max_rows=args.max_rows
            )
            print(
                f"  loaded {asset}: signs.size={signs_cache[asset].signs.size:,}  "
                f"({time.time() - t0:.1f}s)"
            )

        for n, subset in subset_groups:
            t0 = time.time()
            result = _calibrate_one_cell(subset, month, signs_cache, ell_grid)
            elapsed_cell = time.time() - t0
            per_subset_cell_results[(n, tuple(subset))].append(result)
            ell_str = (
                str(result["ell_star"]) if result["ell_star"] is not None else "none"
            )
            print(
                f"  n={n} {_short_subset(subset):<20} ell={ell_str:>4}  "
                f"surv={result['survival_rate']:.3f}  "
                f"p1={result['fused_p1']:.3f}  "
                f"swept={result['swept_ell_count']:>3}  ({elapsed_cell:.1f}s)"
            )
        del signs_cache
        print(f"  month elapsed: {time.time() - month_start:.1f}s")
    print()

    # ---- per-subset P80 + witness + write outputs ----
    witness_signs_cache = None
    summary_rows: list[dict] = []

    for n, subset in subset_groups:
        cell_results = per_subset_cell_results[(n, tuple(subset))]
        ell_stars_raw = [r["ell_star"] for r in cell_results]
        ell_star_n = p80(ell_stars_raw)

        witness_info: dict | None = None
        witness_offset: int | None = None
        if ell_star_n is not None:
            if witness_signs_cache is None:
                print(f"--- loading witness month {witness_month} ---")
                witness_signs_cache = {
                    asset: build_per_asset_signs(
                        asset, witness_month, input_root, max_rows=args.max_rows
                    )
                    for asset in assets
                }
            per_asset = [witness_signs_cache[a] for a in subset]
            fused_witness = build_fused_stream_from_signs(
                subset, witness_month, per_asset
            )
            try:
                witness_offset, witness_eval = select_witness_offset(
                    fused_witness.fused_bits,
                    ell_star_n,
                    alpha=ALPHA,
                    valid_offset_ratio_threshold=VALID_OFFSET_RATIO_THRESHOLD,
                    min_bit_count=MIN_BIT_COUNT,
                )
                witness_info = {
                    "n": n,
                    "subset": list(subset),
                    "witness_month": witness_month,
                    "ell_star_n": ell_star_n,
                    "witness_offset": int(witness_offset),
                    "witness_diagnostics": {
                        "bit_count": int(witness_eval.bit_count),
                        "d_pvalue": witness_eval.d_pvalue,
                        "monobit_pvalue": witness_eval.monobit_pvalue,
                        "runs_pvalue": witness_eval.runs_pvalue,
                    },
                    "criterion": "max geometric mean of (D, Monobit, Runs) p-values",
                }
            except ValueError as exc:
                witness_info = {
                    "n": n,
                    "subset": list(subset),
                    "witness_month": witness_month,
                    "ell_star_n": ell_star_n,
                    "witness_offset": None,
                    "reason": str(exc),
                }

        subset_dir_name = _subset_dir_name(n, list(subset))
        _write_outputs_for_subset(
            n=n,
            subset=list(subset),
            cell_results=cell_results,
            ell_star_n=ell_star_n,
            witness_info=witness_info,
            output_root=output_root,
            subdir_name=subset_dir_name,
        )

        # Build the per-subset summary row for the top-level CSV.
        passed_count = sum(1 for v in ell_stars_raw if v is not None)
        survival_median = float(
            pd.Series([r["survival_rate"] for r in cell_results]).median()
        )
        fused_p1_median = float(
            pd.Series([r["fused_p1"] for r in cell_results]).median()
        )
        # Throughput estimate at ell_star_n on the median month: kept_seconds / ell.
        if ell_star_n is not None:
            kept_median = float(
                pd.Series([r["kept_seconds"] for r in cell_results]).median()
            )
            estimated_bits_per_month = kept_median / ell_star_n
        else:
            estimated_bits_per_month = float("nan")

        summary_rows.append(
            dict(
                n=n,
                subset="-".join(subset),
                ell_star_n=ell_star_n,
                n_months_passed=passed_count,
                survival_median=survival_median,
                fused_p1_median=fused_p1_median,
                kept_seconds_median=float(
                    pd.Series([r["kept_seconds"] for r in cell_results]).median()
                ),
                estimated_bits_per_month=estimated_bits_per_month,
                witness_offset=witness_offset,
            )
        )

    summary_df = pd.DataFrame(summary_rows).sort_values(
        ["n", "ell_star_n", "estimated_bits_per_month"],
        ascending=[True, True, False],
        na_position="last",
    )
    summary_csv = output_root / "all_subsets_summary.csv"
    summary_df.to_csv(summary_csv, index=False)

    summary_meta = {
        "n_subsets_total": n_subsets,
        "n_calibration_months": len(months),
        "n_total_cells": n_total_cells,
        "calibration_months": months,
        "witness_month": witness_month,
        "n_values": n_values,
        "assets": assets,
        "gate_config": {
            "alpha": ALPHA,
            "pass_rate_threshold": PASS_RATE_THRESHOLD,
            "valid_offset_ratio_threshold": VALID_OFFSET_RATIO_THRESHOLD,
            "min_bit_count": MIN_BIT_COUNT,
            "ell_grid": f"[{args.ell_min}, {args.ell_max}] step {args.ell_step}",
            "aggregation_operator": "XOR-aggregation (see src/calibration.py)",
        },
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (output_root / "all_subsets_summary.json").write_text(
        json.dumps(summary_meta, indent=2)
    )

    # ---- print top-line summary table ----
    print()
    print(f"=== all-subsets calibration summary ({n_subsets} subsets) ===")
    print(
        f"  {'n':>2}  {'subset':<35}  {'ell_n':>5}  "
        f"{'pass':>4}  {'surv_med':>8}  {'p1_med':>6}  "
        f"{'bits/mo':>10}  {'witness':>7}"
    )
    print("  " + "-" * 92)
    for row in summary_df.itertuples(index=False):
        ell_str = "none" if pd.isna(row.ell_star_n) else f"{int(row.ell_star_n):>5}"
        bits_str = (
            "none"
            if pd.isna(row.estimated_bits_per_month)
            else f"{row.estimated_bits_per_month:>10,.0f}"
        )
        witness_str = (
            "—" if pd.isna(row.witness_offset) else str(int(row.witness_offset))
        )
        print(
            f"  {row.n:>2}  {row.subset:<35}  {ell_str}  "
            f"{row.n_months_passed:>4}  {row.survival_median:>8.3f}  "
            f"{row.fused_p1_median:>6.3f}  {bits_str}  {witness_str:>7}"
        )
    print()
    print(f"summary CSV : {summary_csv}")
    print(f"elapsed     : {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
