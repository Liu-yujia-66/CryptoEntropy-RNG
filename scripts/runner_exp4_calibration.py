"""
Experiment 4 — calibration runner.

For each fusion size n in {2, 3, 4, 5}:

  1. Read the best n-asset subset from the MI matrix output
     (mi_pool_summary.json, ``subset_recommendations_by_max_pairwise_mi``).
     v3.2 §2.2 best-per-n framing.
  2. For each calibration month (default 2025-01..2025-09):
       - load the per-asset signs (cached across n, sharing the same
         month's loads)
       - XOR-fuse over the subset (drop-any-zero on the joint mask)
       - sweep ell over ELL_GRID; pick the smallest ell that passes
         the +Runs all-offset gate (>=80% of valid offsets pass D
         adaptive-k, Monobit, Runs at alpha=0.01); None if no ell
         passes
  3. ell_star_n = P80({ell_star_{n, m} : m in calibration months,
     ignoring None entries})
  4. On the witness month (default = last calibration month), at
     ell = ell_star_n, pick the offset with the largest geometric
     mean of (D, Monobit, Runs) p-values

Outputs land under data/processed/experiment4/calibration/n{N}/:

  subset.json              best subset for this n + source metadata
  ell_n_choice.json        ell_star_n + the P80 calculation
  witness_offset.json      witness_offset + diagnostics on selection
  per_month_ell_star.csv   one row per calibration month
  stream_utilization.json  survival rate stats per month

Aggregation operator: XOR-aggregation per src.calibration (see the
module docstring there for why the v3.2 §2.3 literal text
"sub-sample" / "Exp 2 1sbar framework" was replaced).

Run from the project root after the MI matrix runner has finished:
    python scripts/runner_exp4_calibration.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
DEFAULT_N_VALUES = [2, 3, 4, 5]

# ell grid: piling-up convergence (see src/calibration.py unit tests) means
# real fused streams should hit a passing ell well before 400. Cap at 400 to
# avoid wasted work; CLI can extend if a particular cell needs deeper.
ELL_MIN = 2
ELL_MAX = 400
ELL_STEP = 1

ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
VALID_OFFSET_RATIO_THRESHOLD = 0.80
MIN_BIT_COUNT = 2000

DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
DEFAULT_MI_SUMMARY_PATH = Path(
    "data/processed/experiment4/calibration/mi/mi_pool_summary.json"
)
DEFAULT_OUTPUT_ROOT = Path("data/processed/experiment4/calibration")


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_subsets_per_n(
    mi_summary_path: Path, n_values: list[int]
) -> dict[int, list[str]]:
    with mi_summary_path.open() as fp:
        mi = json.load(fp)
    raw = mi.get("subset_recommendations_by_max_pairwise_mi", {})
    out: dict[int, list[str]] = {}
    for n in n_values:
        rec = raw.get(str(n))
        if rec is None:
            raise KeyError(
                f"MI summary {mi_summary_path} has no recommendation for n={n}"
            )
        out[n] = list(rec["subset"])
    return out


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


def _write_outputs_for_n(
    n: int,
    subset: list[str],
    cell_results: list[dict],
    ell_star_n: int | None,
    witness_info: dict | None,
    output_root: Path,
    subdir_name: str | None = None,
) -> None:
    """Write one (n, subset) calibration result tree.

    By default the directory is named ``n{n}`` under ``output_root``
    (single-subset runner convention). The all-subsets runner passes
    ``subdir_name`` like ``n2_BNBUSDT-BTCUSDT`` so each subset gets
    its own collision-free directory.
    """
    n_dir = output_root / (subdir_name if subdir_name is not None else f"n{n}")
    n_dir.mkdir(parents=True, exist_ok=True)

    # subset.json
    (n_dir / "subset.json").write_text(
        json.dumps(
            {
                "n": n,
                "subset": subset,
                "source": "by_max_pairwise_mi",
                "note": "best n-asset subset from MI matrix; v3.2 §2.2 best-per-n",
            },
            indent=2,
        )
    )

    # per_month_ell_star.csv
    per_month_df = pd.DataFrame(cell_results)
    per_month_df.to_csv(n_dir / "per_month_ell_star.csv", index=False)

    # ell_n_choice.json
    ell_stars = [r["ell_star"] for r in cell_results]
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

    # witness_offset.json
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

    # stream_utilization.json
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
        description="Experiment 4 calibration runner (XOR-aggregation + +Runs gate)."
    )
    parser.add_argument(
        "--months",
        default=",".join(DEFAULT_CALIBRATION_MONTHS),
        help=f"calibration months (default: {DEFAULT_CALIBRATION_MONTHS[0]}..{DEFAULT_CALIBRATION_MONTHS[-1]})",
    )
    parser.add_argument(
        "--witness-month",
        default=DEFAULT_WITNESS_MONTH,
        help=f"month used for witness offset selection (default: {DEFAULT_WITNESS_MONTH})",
    )
    parser.add_argument(
        "--n-values",
        default=",".join(str(n) for n in DEFAULT_N_VALUES),
        help=f"fusion sizes to calibrate (default: {DEFAULT_N_VALUES})",
    )
    parser.add_argument(
        "--ell-min",
        type=int,
        default=ELL_MIN,
        help=f"sweep min (default: {ELL_MIN})",
    )
    parser.add_argument(
        "--ell-max",
        type=int,
        default=ELL_MAX,
        help=f"sweep max (default: {ELL_MAX})",
    )
    parser.add_argument(
        "--ell-step",
        type=int,
        default=ELL_STEP,
        help=f"sweep step (default: {ELL_STEP})",
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help=f"aggTrades root (default: {DEFAULT_INPUT_ROOT})",
    )
    parser.add_argument(
        "--mi-summary",
        default=str(DEFAULT_MI_SUMMARY_PATH),
        help=f"path to mi_pool_summary.json (default: {DEFAULT_MI_SUMMARY_PATH})",
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
        help="optional per-file row cap for smoke runs",
    )
    args = parser.parse_args()

    months = _parse_csv_list(args.months)
    n_values = [int(s) for s in _parse_csv_list(args.n_values)]
    witness_month = args.witness_month
    if witness_month not in months:
        print(
            f"[warn] witness_month={witness_month} not in calibration months; "
            "loading it separately"
        )

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"[fatal] input root does not exist: {input_root}")
        return 1
    mi_summary_path = Path(args.mi_summary)
    if not mi_summary_path.exists():
        print(f"[fatal] MI summary not found: {mi_summary_path}")
        print("        run scripts/runner_exp4_mi_matrix.py first")
        return 1
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    ell_grid = list(range(args.ell_min, args.ell_max + 1, args.ell_step))

    subsets_per_n = _load_subsets_per_n(mi_summary_path, n_values)
    all_assets_needed = sorted(
        {asset for subset in subsets_per_n.values() for asset in subset}
    )

    print(f"=== exp4 calibration ===")
    print(f"calibration months : {months[0]}..{months[-1]} ({len(months)} months)")
    print(f"witness month      : {witness_month}")
    print(f"n values           : {n_values}")
    print(f"ell grid           : [{args.ell_min}, {args.ell_max}] step {args.ell_step}")
    print(f"input_root         : {input_root}")
    print(f"output_root        : {output_root}")
    print(f"all assets needed  : {all_assets_needed}")
    print(f"subsets per n      :")
    for n, subset in subsets_per_n.items():
        print(f"    n={n}: {subset}")
    print()

    started = time.time()
    per_n_results: dict[int, list[dict]] = {n: [] for n in n_values}

    # Per-month outer loop so that all per-asset signs for the month are cached
    # in memory once and reused across the four n subsets.
    for month_idx, month in enumerate(months, start=1):
        month_start = time.time()
        print(f"--- month {month} ({month_idx}/{len(months)}) ---")
        signs_cache = {}
        for asset in all_assets_needed:
            t0 = time.time()
            signs_cache[asset] = build_per_asset_signs(
                asset, month, input_root, max_rows=args.max_rows
            )
            print(
                f"  loaded {asset}: signs.size={signs_cache[asset].signs.size:,}  "
                f"({time.time() - t0:.1f}s)"
            )

        for n in n_values:
            subset = subsets_per_n[n]
            t0 = time.time()
            result = _calibrate_one_cell(subset, month, signs_cache, ell_grid)
            elapsed_cell = time.time() - t0
            per_n_results[n].append(result)
            ell_star_str = str(result["ell_star"]) if result["ell_star"] is not None else "none"
            print(
                f"  n={n} {subset}: ell_star={ell_star_str:>4}  "
                f"survival={result['survival_rate']:.3f}  "
                f"fused_p1={result['fused_p1']:.3f}  "
                f"swept={result['swept_ell_count']:>3}  "
                f"({elapsed_cell:.1f}s)"
            )
        del signs_cache
        print(f"  month elapsed: {time.time() - month_start:.1f}s")
    print()

    # P80 + witness for each n
    witness_signs_cache = None
    for n in n_values:
        cell_results = per_n_results[n]
        ell_star_n = p80([r["ell_star"] for r in cell_results])
        subset = subsets_per_n[n]

        witness_info: dict | None = None
        if ell_star_n is None:
            print(f"n={n}: no ell_star_n (P80 of all-None); skipping witness selection")
        else:
            if witness_signs_cache is None:
                print(f"--- loading witness month {witness_month} for witness selection ---")
                witness_signs_cache = {
                    asset: build_per_asset_signs(
                        asset, witness_month, input_root, max_rows=args.max_rows
                    )
                    for asset in all_assets_needed
                }
            per_asset = [witness_signs_cache[a] for a in subset]
            fused_witness = build_fused_stream_from_signs(subset, witness_month, per_asset)
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
                print(
                    f"n={n}: ell_star_n={ell_star_n}  witness_offset={witness_offset}  "
                    f"(D={witness_eval.d_pvalue:.3g} M={witness_eval.monobit_pvalue:.3g} "
                    f"R={witness_eval.runs_pvalue:.3g})"
                )
            except ValueError as exc:
                print(f"n={n}: witness selection failed: {exc}")
                witness_info = {
                    "n": n,
                    "witness_month": witness_month,
                    "ell_star_n": ell_star_n,
                    "witness_offset": None,
                    "reason": str(exc),
                }

        _write_outputs_for_n(
            n=n,
            subset=subset,
            cell_results=cell_results,
            ell_star_n=ell_star_n,
            witness_info=witness_info,
            output_root=output_root,
        )

    # ----- top-level summary -----
    summary_path = output_root / "calibration_summary.json"
    summary = {
        "n_values": n_values,
        "calibration_months": months,
        "witness_month": witness_month,
        "gate_config": {
            "alpha": ALPHA,
            "pass_rate_threshold": PASS_RATE_THRESHOLD,
            "valid_offset_ratio_threshold": VALID_OFFSET_RATIO_THRESHOLD,
            "min_bit_count": MIN_BIT_COUNT,
            "ell_grid": f"[{args.ell_min}, {args.ell_max}] step {args.ell_step}",
            "aggregation_operator": "XOR-aggregation (see src/calibration.py)",
        },
        "subsets_per_n": {str(n): subsets_per_n[n] for n in n_values},
        "ell_star_per_n": {
            str(n): p80([r["ell_star"] for r in per_n_results[n]]) for n in n_values
        },
        "n_months_passed_per_n": {
            str(n): sum(1 for r in per_n_results[n] if r["ell_star"] is not None)
            for n in n_values
        },
        "elapsed_seconds": round(time.time() - started, 1),
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    print()
    print(f"=== outputs ===")
    for n in n_values:
        print(f"  data/processed/experiment4/calibration/n{n}/")
    print(f"  {summary_path}")
    print()
    print("=== top-line summary ===")
    for n in n_values:
        ell_n = p80([r["ell_star"] for r in per_n_results[n]])
        n_passed = sum(1 for r in per_n_results[n] if r["ell_star"] is not None)
        print(
            f"  n={n} subset={subsets_per_n[n]}: "
            f"ell_star_n={ell_n}  n_months_passed={n_passed}/{len(months)}"
        )
    print(f"elapsed: {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
