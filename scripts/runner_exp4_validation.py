"""
Experiment 4 — validation runner (plan v3.2 §2.5 / §2.6, v3.3 subset
selection).

For each fusion size n in {2, 3, 4, 5}:

  1. Read calibration_all_subsets/all_subsets_summary.csv, pick the
     subset with highest estimated_bits_per_month for this n (v3.3
     throughput-best policy retiring v3.2 §2.2 MI-best).
  2. Load that subset's calibration outputs (ell_n_choice.json,
     witness_offset.json).
  3. For each validation month (2025-10 .. 2026-03, default 6 months):
       - Load per-asset signs (cached across n within the same month).
       - Build the XOR-fused stream over the subset.
       - XOR-aggregate every offset 0..ell*_n-1 using
         src.calibration.xor_aggregate_offset.
       - Run src.battery.full_battery (up to 29 sub-tests) on each
         offset's aggregated output. Join the Exp 3 sanity matrix to
         flag per-(sub-test, length-bracket) invalid cells.
       - Compute cell-level verdict per sub-test: PASS if >=80% of
         admissible offsets have p >= alpha; FAIL otherwise; INVALID
         if all offsets are sanity-invalid for that sub-test.
       - Save the witness-offset stream as fused_stream.bin
         (deployment artefact for the Prototype).

Outputs land under data/processed/experiment4/validation/:

  n{N}/                                  # one directory per fusion size
    subset.json                          # subset + calibration metadata
    {month}/
      fused_stream.bin                   # witness-offset uint8 stream
      fused_stream.meta.json             # length, survival, ell*, witness, throughput
      verdict_row.csv                    # 1 row x 12 sub-test (cell-level)
      per_offset_pvalues.csv             # ell*_n rows x 12 sub-test (debug)
    per_month_verdict_matrix.csv         # 6 rows x 12 sub-test (paper §4.5 table)
    per_month_throughput.csv             # 6 rows: bits, bps, 256-bit latency
  validation_summary.json                # subsets / ell_n / witness per n + verdict counts

Out-of-sample by construction: ell*_n + witness come from the
9-month calibration window; this runner does no parameter selection
on validation months.

Run after runner_exp4_calibration_all_subsets.py:
    python scripts/runner_exp4_validation.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import numpy as np
import pandas as pd

from src.calibration import xor_aggregate_offset
from src.fusion import build_fused_stream_from_signs, build_per_asset_signs
from src.battery import (
    ALL_SUB_TESTS,
    bracket_for_length,
    full_battery,
)


DEFAULT_VALIDATION_MONTHS = [
    "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
]
DEFAULT_N_VALUES = [2, 3, 4, 5]

ALPHA = 0.01
PASS_RATE_THRESHOLD = 0.80
MIN_BIT_COUNT = 2000

DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
DEFAULT_CALIB_ROOT = Path("data/processed/experiment4/calibration_all_subsets")
DEFAULT_SANITY_PATH = Path(
    "data/processed/experiment3/sanity_check_validity_matrix-k1000.csv"
)
DEFAULT_OUTPUT_ROOT = Path("data/processed/experiment4/validation")


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_sanity_matrix(path: Path) -> dict[tuple[str, str], bool]:
    """Load Exp 3 sanity validity matrix -> dict[(sub_test, bracket), passed]."""
    df = pd.read_csv(path)
    return {
        (str(r.sub_test), str(r.bracket)): bool(r.passed_sanity)
        for r in df.itertuples(index=False)
    }


def _subset_dir_name(n: int, subset: list[str]) -> str:
    return f"n{n}_" + "-".join(sorted(subset))


def _select_best_subset_per_n(
    summary_csv: Path, n_values: list[int]
) -> dict[int, dict]:
    """For each n, pick the subset with max estimated_bits_per_month.

    Returns dict[n -> {subset: [...], ell_star_n, witness_offset,
    estimated_bits_per_month, calibration_dir}].
    """
    df = pd.read_csv(summary_csv)
    out: dict[int, dict] = {}
    for n in n_values:
        candidates = df[df["n"] == n].copy()
        if candidates.empty:
            raise KeyError(f"no subsets for n={n} in {summary_csv}")
        # Drop rows where calibration did not pick an ell_star_n (None)
        candidates = candidates.dropna(subset=["ell_star_n"])
        if candidates.empty:
            raise KeyError(
                f"no subsets for n={n} found an ell_star_n in calibration"
            )
        # Pick max throughput row
        best = candidates.sort_values(
            "estimated_bits_per_month", ascending=False
        ).iloc[0]
        subset_assets = best["subset"].split("-")
        dir_name = _subset_dir_name(n, subset_assets)
        out[n] = {
            "n": n,
            "subset": subset_assets,
            "subset_label": best["subset"],
            "ell_star_n": int(best["ell_star_n"]),
            "witness_offset": (
                int(best["witness_offset"])
                if not pd.isna(best["witness_offset"])
                else None
            ),
            "calibration_estimated_bits_per_month": float(
                best["estimated_bits_per_month"]
            ),
            "calibration_dir_name": dir_name,
        }
    return out


def _load_calibration_for_subset(
    calib_root: Path, dir_name: str
) -> tuple[dict, dict]:
    """Read ell_n_choice.json + witness_offset.json for one calibration subset."""
    ell_path = calib_root / dir_name / "ell_n_choice.json"
    witness_path = calib_root / dir_name / "witness_offset.json"
    with ell_path.open() as fp:
        ell_meta = json.load(fp)
    with witness_path.open() as fp:
        witness_meta = json.load(fp)
    return ell_meta, witness_meta


def _evaluate_cell(
    n: int,
    subset: list[str],
    ell_star_n: int,
    witness_offset: int | None,
    month: str,
    signs_cache: dict,
    sanity_matrix: dict[tuple[str, str], bool],
) -> dict:
    """Build fused, XOR-aggregate, run battery on every offset, compute
    cell verdict + return per-offset detail + deployment stream."""
    per_asset = [signs_cache[a] for a in subset]
    fused = build_fused_stream_from_signs(subset, month, per_asset)

    # Build per-offset aggregated streams + run battery
    per_offset_rows: list[dict] = []
    witness_stream: np.ndarray | None = None
    for offset in range(ell_star_n):
        agg = xor_aggregate_offset(fused.fused_bits, ell_star_n, offset)
        if witness_offset is not None and offset == witness_offset:
            witness_stream = agg
        row: dict = {
            "offset": offset,
            "bit_count": int(agg.size),
            "bracket": bracket_for_length(int(agg.size)),
        }
        if agg.size < 2:
            for sub_test in ALL_SUB_TESTS:
                row[f"{sub_test}_pvalue"] = float("nan")
                row[f"{sub_test}_sanity_valid"] = False
        else:
            results = full_battery(agg, sanity_matrix)
            for sub_test, (p_value, sanity_valid) in results.items():
                row[f"{sub_test}_pvalue"] = float(p_value)
                row[f"{sub_test}_sanity_valid"] = bool(sanity_valid)
        per_offset_rows.append(row)

    per_offset_df = pd.DataFrame(per_offset_rows)

    # Cell-level verdict per sub-test
    verdict_row: dict = {
        "n": n,
        "subset": "-".join(subset),
        "month": month,
        "ell_star_n": ell_star_n,
        "witness_offset": witness_offset,
        "raw_seconds": int(fused.raw_seconds),
        "kept_seconds": int(fused.kept_seconds),
        "survival_rate": float(fused.survival_rate),
        "fused_p1": (
            float(fused.fused_bits.mean()) if fused.kept_seconds > 0 else 0.0
        ),
        "per_offset_bit_count_median": (
            int(per_offset_df["bit_count"].median()) if not per_offset_df.empty else 0
        ),
    }
    for sub_test in ALL_SUB_TESTS:
        p_col = f"{sub_test}_pvalue"
        sv_col = f"{sub_test}_sanity_valid"
        valid_mask = per_offset_df[sv_col]
        n_valid = int(valid_mask.sum())
        if n_valid == 0:
            verdict = "INVALID"
            pass_rate = float("nan")
        else:
            valid_pvalues = per_offset_df.loc[valid_mask, p_col]
            n_pass = int((valid_pvalues >= ALPHA).sum())
            pass_rate = n_pass / n_valid
            verdict = "PASS" if pass_rate >= PASS_RATE_THRESHOLD else "FAIL"
        verdict_row[f"{sub_test}_verdict"] = verdict
        verdict_row[f"{sub_test}_pass_rate"] = pass_rate
        verdict_row[f"{sub_test}_n_valid_offsets"] = n_valid

    # Throughput — deployment uses the witness offset's stream as IKM, so a
    # missing witness means the Prototype contract is broken. Fail loud here
    # rather than silently fall back to a different summary statistic.
    if witness_stream is None:
        raise RuntimeError(
            f"n={n} subset={'-'.join(subset)} month={month}: "
            f"witness_offset={witness_offset} did not match any offset in the "
            f"sweep (range 0..{ell_star_n - 1}). Calibration must select a "
            f"valid witness_offset before validation."
        )
    output_bits = int(witness_stream.size)
    throughput = {
        "output_bits": output_bits,
        "raw_seconds": int(fused.raw_seconds),
        "bps_on_raw_seconds": (
            output_bits / fused.raw_seconds if fused.raw_seconds > 0 else 0.0
        ),
        "seconds_per_256_bits": (
            (256 / output_bits) * fused.raw_seconds if output_bits > 0 else float("inf")
        ),
        "hours_per_256_bits": (
            (256 / output_bits) * fused.raw_seconds / 3600 if output_bits > 0 else float("inf")
        ),
    }

    return {
        "verdict_row": verdict_row,
        "per_offset_df": per_offset_df,
        "witness_stream": witness_stream,
        "throughput": throughput,
        "fused_diagnostics": {
            "raw_seconds": int(fused.raw_seconds),
            "kept_seconds": int(fused.kept_seconds),
            "survival_rate": float(fused.survival_rate),
            "naive_baseline_0p85_pow_n": float(fused.naive_baseline),
            "empirical_independent_baseline": float(
                fused.empirical_independent_baseline
            ),
            "survival_vs_empirical_ratio": float(
                fused.survival_vs_empirical_ratio
            ),
            "per_asset_p1": fused.per_asset_p1,
            "per_asset_zero_delta_rate": fused.per_asset_zero_delta_rate,
            "pairwise_correlation": {
                f"{a}|{b}": float(v)
                for (a, b), v in fused.pairwise_correlation.items()
            },
            "pairwise_mi_1bit": {
                f"{a}|{b}": float(v)
                for (a, b), v in fused.pairwise_mi_1bit.items()
            },
        },
    }


def _write_per_cell_outputs(
    n: int,
    month: str,
    cell_result: dict,
    n_dir: Path,
) -> None:
    """Save fused_stream.bin + fused_stream.meta.json + verdict_row.csv +
    per_offset_pvalues.csv for one (n, month) cell."""
    month_dir = n_dir / month
    month_dir.mkdir(parents=True, exist_ok=True)

    witness = cell_result["witness_stream"]
    if witness is not None:
        (month_dir / "fused_stream.bin").write_bytes(witness.tobytes())

    meta = {
        "n": n,
        "month": month,
        "subset": cell_result["verdict_row"]["subset"].split("-"),
        "ell_star_n": cell_result["verdict_row"]["ell_star_n"],
        "witness_offset": cell_result["verdict_row"]["witness_offset"],
        "witness_stream_bit_count": (
            int(witness.size) if witness is not None else None
        ),
        "throughput": cell_result["throughput"],
        "fused_diagnostics": cell_result["fused_diagnostics"],
    }
    (month_dir / "fused_stream.meta.json").write_text(json.dumps(meta, indent=2))

    pd.DataFrame([cell_result["verdict_row"]]).to_csv(
        month_dir / "verdict_row.csv", index=False
    )
    cell_result["per_offset_df"].to_csv(
        month_dir / "per_offset_pvalues.csv", index=False
    )


def _write_per_n_outputs(
    n: int,
    subset_meta: dict,
    cell_results: dict[str, dict],
    n_dir: Path,
) -> dict:
    """Aggregate per-month results into per_month_verdict_matrix.csv +
    per_month_throughput.csv + subset.json. Return summary dict."""
    # subset.json
    (n_dir / "subset.json").write_text(json.dumps(subset_meta, indent=2))

    # per_month_verdict_matrix.csv
    rows: list[dict] = [cell["verdict_row"] for cell in cell_results.values()]
    verdict_df = pd.DataFrame(rows).sort_values("month")
    verdict_df.to_csv(n_dir / "per_month_verdict_matrix.csv", index=False)

    # per_month_throughput.csv
    throughput_rows: list[dict] = []
    for month, cell in sorted(cell_results.items()):
        throughput_rows.append(
            {
                "n": n,
                "subset": cell["verdict_row"]["subset"],
                "month": month,
                **cell["throughput"],
            }
        )
    throughput_df = pd.DataFrame(throughput_rows)
    throughput_df.to_csv(n_dir / "per_month_throughput.csv", index=False)

    # Per-n aggregate counts
    sub_test_pass_counts = {}
    for sub_test in ALL_SUB_TESTS:
        col = f"{sub_test}_verdict"
        sub_test_pass_counts[sub_test] = {
            "PASS": int((verdict_df[col] == "PASS").sum()),
            "FAIL": int((verdict_df[col] == "FAIL").sum()),
            "INVALID": int((verdict_df[col] == "INVALID").sum()),
        }

    output_bits_median = float(throughput_df["output_bits"].median())
    seconds_per_256_median = float(throughput_df["seconds_per_256_bits"].median())

    return {
        "n": n,
        "subset": subset_meta["subset"],
        "ell_star_n": subset_meta["ell_star_n"],
        "witness_offset": subset_meta["witness_offset"],
        "n_months": len(cell_results),
        "sub_test_pass_counts": sub_test_pass_counts,
        "output_bits_median": output_bits_median,
        "seconds_per_256_bits_median": seconds_per_256_median,
        "hours_per_256_bits_median": seconds_per_256_median / 3600,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experiment 4 validation runner."
    )
    parser.add_argument(
        "--n-values",
        default=",".join(str(n) for n in DEFAULT_N_VALUES),
        help=f"fusion sizes to validate (default: {DEFAULT_N_VALUES})",
    )
    parser.add_argument(
        "--months",
        default=",".join(DEFAULT_VALIDATION_MONTHS),
        help=f"validation months (default: {DEFAULT_VALIDATION_MONTHS[0]}..{DEFAULT_VALIDATION_MONTHS[-1]})",
    )
    parser.add_argument(
        "--calibration-root",
        default=str(DEFAULT_CALIB_ROOT),
        help=f"calibration_all_subsets root (default: {DEFAULT_CALIB_ROOT})",
    )
    parser.add_argument(
        "--sanity-matrix",
        default=str(DEFAULT_SANITY_PATH),
        help=f"Exp 3 sanity matrix CSV (default: {DEFAULT_SANITY_PATH})",
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
        help="optional per-file aggTrades row cap (default: full month)",
    )
    args = parser.parse_args()

    n_values = [int(s) for s in _parse_csv_list(args.n_values)]
    months = _parse_csv_list(args.months)

    calib_root = Path(args.calibration_root)
    summary_csv = calib_root / "all_subsets_summary.csv"
    if not summary_csv.exists():
        print(f"[fatal] calibration summary not found: {summary_csv}")
        print("        run scripts/runner_exp4_calibration_all_subsets.py first")
        return 1
    sanity_path = Path(args.sanity_matrix)
    if not sanity_path.exists():
        print(f"[fatal] sanity matrix not found: {sanity_path}")
        print("        run scripts/runner_exp3_sanity_check.py first")
        return 1
    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"[fatal] input root does not exist: {input_root}")
        return 1
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # ---------------- subset selection ----------------
    subset_picks = _select_best_subset_per_n(summary_csv, n_values)
    sanity_matrix = _load_sanity_matrix(sanity_path)
    all_assets_needed = sorted(
        {asset for pick in subset_picks.values() for asset in pick["subset"]}
    )

    # Reconcile each subset's calibration_dir against the on-disk artefact
    for n, pick in subset_picks.items():
        ell_meta, witness_meta = _load_calibration_for_subset(
            calib_root, pick["calibration_dir_name"]
        )
        # Cross-check (defensive; summary CSV should already agree)
        if ell_meta.get("ell_star_n") != pick["ell_star_n"]:
            raise RuntimeError(
                f"n={n}: summary CSV ell_star_n={pick['ell_star_n']} "
                f"differs from ell_n_choice.json {ell_meta.get('ell_star_n')}"
            )
        if witness_meta.get("witness_offset") != pick["witness_offset"]:
            raise RuntimeError(
                f"n={n}: summary CSV witness={pick['witness_offset']} "
                f"differs from witness_offset.json {witness_meta.get('witness_offset')}"
            )
        # Fail fast if calibration didn't pick a witness for this subset —
        # otherwise we'd burn ~30 min of signs IO + battery compute and
        # crash inside _evaluate_cell on the first month.
        if pick["witness_offset"] is None:
            raise RuntimeError(
                f"n={n} subset={pick['subset_label']}: witness_offset is None "
                f"in calibration_all_subsets output. The Prototype needs a "
                f"fixed witness offset per (n, subset). Re-run calibration or "
                f"pick a different subset for this n."
            )
        pick["calibration_ell_meta"] = ell_meta
        pick["calibration_witness_meta"] = witness_meta

    # ---------------- print header ----------------
    print("=== exp4 validation ===")
    print(f"n values        : {n_values}")
    print(f"validation months: {months[0]}..{months[-1]} ({len(months)} months)")
    print(f"calibration root: {calib_root}")
    print(f"sanity matrix   : {sanity_path}  ({len(sanity_matrix)} entries)")
    print(f"input root      : {input_root}")
    print(f"output root     : {output_root}")
    print(f"all assets needed: {all_assets_needed}")
    print()
    print("subset picks (throughput-best per n from calibration_all_subsets):")
    for n, pick in subset_picks.items():
        print(
            f"  n={n}: {pick['subset_label']}  "
            f"ell*={pick['ell_star_n']}  witness={pick['witness_offset']}  "
            f"calib_estimated_bits/mo={pick['calibration_estimated_bits_per_month']:,.0f}"
        )
    print()

    started = time.time()
    per_n_cells: dict[int, dict[str, dict]] = {n: {} for n in n_values}

    # Outer loop: month so per-asset signs are cached once per month.
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

        for n, pick in subset_picks.items():
            t0 = time.time()
            cell_result = _evaluate_cell(
                n=n,
                subset=pick["subset"],
                ell_star_n=pick["ell_star_n"],
                witness_offset=pick["witness_offset"],
                month=month,
                signs_cache=signs_cache,
                sanity_matrix=sanity_matrix,
            )
            elapsed_cell = time.time() - t0
            per_n_cells[n][month] = cell_result

            n_pass = sum(
                1
                for st in ALL_SUB_TESTS
                if cell_result["verdict_row"][f"{st}_verdict"] == "PASS"
            )
            n_fail = sum(
                1
                for st in ALL_SUB_TESTS
                if cell_result["verdict_row"][f"{st}_verdict"] == "FAIL"
            )
            n_invalid = sum(
                1
                for st in ALL_SUB_TESTS
                if cell_result["verdict_row"][f"{st}_verdict"] == "INVALID"
            )
            print(
                f"  n={n} {pick['subset_label']}: "
                f"verdict PASS={n_pass}/FAIL={n_fail}/INVALID={n_invalid}  "
                f"bits={cell_result['throughput']['output_bits']:,}  "
                f"({elapsed_cell:.1f}s)"
            )

            # Save per-cell outputs immediately (don't lose work on crash)
            n_dir = output_root / f"n{n}"
            _write_per_cell_outputs(n, month, cell_result, n_dir)

        del signs_cache
        print(f"  month elapsed: {time.time() - month_start:.1f}s")
    print()

    # ---------------- per-n aggregation ----------------
    per_n_summary: dict[str, dict] = {}
    for n, pick in subset_picks.items():
        cell_results = per_n_cells[n]
        n_dir = output_root / f"n{n}"
        subset_meta = {
            "n": n,
            "subset": pick["subset"],
            "ell_star_n": pick["ell_star_n"],
            "witness_offset": pick["witness_offset"],
            "calibration_source": pick["calibration_dir_name"],
            "calibration_estimated_bits_per_month": pick[
                "calibration_estimated_bits_per_month"
            ],
            "selection_criterion": "max estimated_bits_per_month from calibration_all_subsets",
        }
        summary = _write_per_n_outputs(n, subset_meta, cell_results, n_dir)
        per_n_summary[str(n)] = summary

    # ---------------- top-level summary ----------------
    summary_payload = {
        "n_values": n_values,
        "validation_months": months,
        "calibration_root": str(calib_root),
        "sanity_matrix_path": str(sanity_path),
        "gate_config": {
            "alpha": ALPHA,
            "pass_rate_threshold": PASS_RATE_THRESHOLD,
            "min_bit_count": MIN_BIT_COUNT,
            "sub_tests": ALL_SUB_TESTS,
            "n_sub_tests": len(ALL_SUB_TESTS),
        },
        "subset_picks": {
            str(n): {
                "subset": pick["subset"],
                "ell_star_n": pick["ell_star_n"],
                "witness_offset": pick["witness_offset"],
                "calibration_estimated_bits_per_month": pick[
                    "calibration_estimated_bits_per_month"
                ],
            }
            for n, pick in subset_picks.items()
        },
        "per_n_summary": per_n_summary,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (output_root / "validation_summary.json").write_text(
        json.dumps(summary_payload, indent=2)
    )

    # ---------------- console summary table ----------------
    print()
    print("=== validation summary ===")
    header = (
        "  n | subset                                    | ell* | "
        + " | ".join(f"{st[:7]:>7}" for st in ALL_SUB_TESTS)
        + " | bits_med | h/256-bit"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for n in n_values:
        pick = subset_picks[n]
        summary = per_n_summary[str(n)]
        verdict_summary = []
        for st in ALL_SUB_TESTS:
            counts = summary["sub_test_pass_counts"][st]
            verdict_summary.append(
                f"{counts['PASS']}/{counts['FAIL']}/{counts['INVALID']}"
            )
        verdict_str = " | ".join(f"{vs:>7}" for vs in verdict_summary)
        print(
            f"  {n} | {pick['subset_label']:<42} | {summary['ell_star_n']:>4} | "
            f"{verdict_str} | {summary['output_bits_median']:>8,.0f} | "
            f"{summary['hours_per_256_bits_median']:>6.2f} h"
        )
    print()
    print("verdict counts per sub-test: PASS/FAIL/INVALID across "
          f"{len(months)} validation months")
    print(f"top-level summary: {output_root / 'validation_summary.json'}")
    print(f"elapsed: {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
