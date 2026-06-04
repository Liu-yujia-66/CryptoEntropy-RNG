"""
Generate a human-readable text summary of exp4 validation results.

Reads:
  data/processed/experiment4/validation/validation_summary.json
  data/processed/experiment4/validation/n{2,3,4,5}/per_month_verdict_matrix.csv
  data/processed/experiment4/validation/n{2,3,4,5}/per_month_throughput.csv

Writes:
  data/processed/experiment4/validation/validation_summary.txt

Three sections per n:
  - pick: subset, ell*_n, witness_offset, output bits / throughput medians
  - sub-test PASS/FAIL/INVALID/NOT_RUN counts across the 6 validation months
  - per-month overall pass count (29 sub-tests minus INVALID/NOT_RUN)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VAL_DIR = ROOT / "data/processed/experiment4/validation"


def _short(asset: str) -> str:
    return {
        "BTCUSDT": "BTC", "ETHUSDT": "ETH", "BNBUSDT": "BNB",
        "SOLUSDT": "SOL", "DOGEUSDT": "DOGE",
    }.get(asset, asset)


def _fmt_subset(subset: list[str]) -> str:
    return "+".join(_short(a) for a in subset)


def write_summary(val_dir: Path | str = DEFAULT_VAL_DIR) -> Path:
    val_dir = Path(val_dir)
    summary_json = val_dir / "validation_summary.json"
    out_path = val_dir / "validation_summary.txt"

    with summary_json.open() as fp:
        summary = json.load(fp)

    n_values = summary["n_values"]
    months = summary["validation_months"]
    sub_tests = summary["gate_config"]["sub_tests"]
    gate = summary["gate_config"]

    lines: list[str] = []
    push = lines.append

    push("Experiment 4 validation — per-n summary")
    push("=" * 110)
    try:
        source_label = str(summary_json.relative_to(ROOT))
    except ValueError:
        source_label = str(summary_json)
    push(f"Source         : {source_label}")
    push(f"Months         : {months[0]}..{months[-1]} ({len(months)} months)")
    push(f"Calibration src: {summary['calibration_root']}")
    push(f"Gate           : alpha={gate['alpha']}  pass_rate_threshold={gate['pass_rate_threshold']}  "
         f"min_bit_count={gate['min_bit_count']}  sub_tests={gate['n_sub_tests']}")
    push(f"Verdict per sub-test per month: PASS if pass_rate >= {gate['pass_rate_threshold']} on "
         f">= {gate['pass_rate_threshold']:.0%} of valid offsets; INVALID if too few valid offsets; "
         f"NOT_RUN if the +Alphabit sanity matrix excludes that (ell, sub_test) cell.")
    push("")

    push("--- per-n picks and median throughput ---")
    push(f"  {'n':>2}  {'subset':<22}  {'ell*':>4}  {'witness':>7}  "
         f"{'out_bits/mo':>12}  {'sec/256':>9}  {'hr/256':>7}")
    push("  " + "-" * 76)
    for n_str in (str(n) for n in n_values):
        s = summary["per_n_summary"][n_str]
        push(
            f"  {s['n']:>2}  {_fmt_subset(s['subset']):<22}  "
            f"{s['ell_star_n']:>4}  {s['witness_offset']:>7}  "
            f"{int(round(s['output_bits_median'])):>12,}  "
            f"{s['seconds_per_256_bits_median']:>9,.0f}  "
            f"{s['hours_per_256_bits_median']:>7.3f}"
        )
    push("")

    for n_str in (str(n) for n in n_values):
        s = summary["per_n_summary"][n_str]
        push(f"--- n = {s['n']}  subset = {_fmt_subset(s['subset'])}  "
             f"(ell*={s['ell_star_n']}, witness={s['witness_offset']}) ---")
        push(f"  {'sub-test':<38}  {'PASS':>5}  {'FAIL':>5}  {'INV':>5}  {'N/R':>5}  verdict")
        push("  " + "-" * 78)
        counts = s["sub_test_pass_counts"]
        for sub in sub_tests:
            c = counts[sub]
            # Effective verdict: PASS if no FAIL across months where the test ran.
            ran_months = c["PASS"] + c["FAIL"]
            if ran_months == 0:
                verdict = "N/A"
            elif c["FAIL"] == 0:
                verdict = "PASS"
            else:
                verdict = f"FAIL ({c['FAIL']}/{ran_months})"
            push(
                f"  {sub:<38}  {c['PASS']:>5}  {c['FAIL']:>5}  "
                f"{c['INVALID']:>5}  {c['NOT_RUN']:>5}  {verdict}"
            )
        # Worst-case: how many sub-tests FAIL at least once across the 6 months.
        n_with_any_fail = sum(1 for sub in sub_tests if counts[sub]["FAIL"] > 0)
        push(f"  -> {n_with_any_fail}/{len(sub_tests)} sub-tests FAIL at least once across the {len(months)} months.")
        push("")

    push("--- per-month overall pass count (sub-tests that PASS that month, out of those that ran) ---")
    push(f"  {'n':>2}  {'subset':<22}  " + "  ".join(f"{m:>9}" for m in months))
    push("  " + "-" * (28 + 11 * len(months)))
    for n in n_values:
        n_dir = val_dir / f"n{n}"
        verdict_df = pd.read_csv(n_dir / "per_month_verdict_matrix.csv")
        subset_label = _fmt_subset(summary["per_n_summary"][str(n)]["subset"])
        per_month_strs = []
        for month in months:
            row = verdict_df[verdict_df["month"] == month].iloc[0]
            pass_count = sum(1 for st in sub_tests if row[f"{st}_verdict"] == "PASS")
            ran_count = sum(
                1 for st in sub_tests if row[f"{st}_verdict"] in ("PASS", "FAIL")
            )
            per_month_strs.append(f"{pass_count:>2}/{ran_count:<2}    ")
        push(f"  {n:>2}  {subset_label:<22}  " + "  ".join(per_month_strs))
    push("")

    out_path.write_text("\n".join(lines))
    return out_path


if __name__ == "__main__":
    written = write_summary()
    print(f"wrote {written}")
