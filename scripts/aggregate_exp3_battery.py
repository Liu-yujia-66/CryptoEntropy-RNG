from __future__ import annotations

"""
Aggregate Experiment 3 per-cell p-values into the plan §1.6 summaries.

Reads `per_cell_pvalues-{GATE}.csv` (produced by `runner_exp3_battery.py`)
and applies the cell-level verdict rule from plan §1.6:

    For each (asset, month, sub_test) cell:
      valid_offsets = offsets in this cell with sanity_valid=True
      if |valid_offsets| == 0:
          verdict = "INVALID"     (does NOT enter n_admissible_months)
      else:
          pass_rate = mean(p >= α  for o in valid_offsets)
          verdict = "PASS" if pass_rate >= 0.80 else "FAIL"

    For each (asset, sub_test):
      n_admissible_months = # months where verdict != "INVALID"
      n_passed_months     = # months where verdict == "PASS"
      pass_rate           = n_passed_months / n_admissible_months

    NOTE: verdict uses literal "INVALID" (not "N/A" or "NA"). Both "N/A"
    and "NA" are in `pd.read_csv` default na_values, so they would be
    silently converted to NaN downstream and corrupt verdict parsing.
    "INVALID" is not in pandas' default na list and reads back as a string.

Writes two CSVs side-by-side with the input:

- `per_cell_verdict-{GATE}.csv`   (62 cells × 12 sub-tests; per-cell verdict)
  - long format: asset, month, sub_test, n_valid_offsets, n_pass_offsets,
    pass_rate, verdict, cell_bracket
- `per_asset_summary-{GATE}.csv`  (5 assets × 12 sub-tests; the main result)
  - schema per plan §1.6: asset, sub_test, n_admissible_months,
    n_passed_months, pass_rate, dominant_bracket

Both are stable-sorted so re-runs produce identical bytes.

Run from project root (after `runner_exp3_battery.py` finishes):
    python scripts/aggregate_exp3_battery.py

Switch the GATE constant (or symlink the CSV) to aggregate base/apen runs.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nist_extended import ALL_SUB_TESTS, SANITY_BRACKETS

# Configuration

# base / runs / apen
GATE = "runs"
ALPHA = 0.01
PASS_THRESHOLD = 0.80

INPUT_PATH = Path(f"data/processed/experiment3/per_cell_pvalues-{GATE}.csv")
PER_CELL_VERDICT_PATH = Path(f"data/processed/experiment3/per_cell_verdict-{GATE}.csv")
PER_ASSET_SUMMARY_PATH = Path(
    f"data/processed/experiment3/per_asset_summary-{GATE}.csv"
)

# Asset display order (descending raw trades/s, same as Exp 1 / Exp 2)
ASSET_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
ASSET_SHORT = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}

# Bracket order (smallest → largest), used for dominant_bracket tie-breaking
BRACKET_ORDER = [label for _, label in SANITY_BRACKETS]


# Aggregation


def _build_per_cell_verdict(df: pd.DataFrame) -> pd.DataFrame:
    """Long-format cell-level verdict. One row per (asset, month, sub_test).

    The cell_bracket column is the sanity bracket the cell falls into
    (taken from the first offset's bracket — within a cell, offsets share
    the same per_offset_bits ± drop-zero noise, so bracket is essentially
    constant; see plan §1.6 'Cell 内 sanity_valid 的均匀性').
    """
    # cell_bracket per (asset, month): take first observed bracket
    cell_bracket = df.drop_duplicates(["asset", "month"])[
        ["asset", "month", "sanity_bracket"]
    ].rename(columns={"sanity_bracket": "cell_bracket"})

    # Per (asset, month, sub_test) counts. Precompute the "valid-and-passing"
    # indicator as a column so agg can sum it directly — avoids a per-group
    # apply (slow + the `include_groups=` overload trips type-checkers).
    df_aug = df.assign(_pass=(df["p_value"] >= ALPHA) & df["sanity_valid"].astype(bool))
    verdict = (
        df_aug.groupby(["asset", "month", "sub_test"], sort=False)
        .agg(
            n_offsets=("p_value", "size"),
            n_valid_offsets=("sanity_valid", "sum"),  # True counts as 1
            n_pass_offsets=("_pass", "sum"),
        )
        .reset_index()
    )

    # pass_rate over valid offsets; verdict ∈ {PASS, FAIL, INVALID}
    # NOTE: literal "INVALID" — pd.read_csv default na_values includes both
    # "N/A" AND "NA" (and many other variants), which would silently
    # convert the sanity-invalid verdict to NaN downstream. "INVALID" is
    # not in pandas' default na_values, so consumers can read normally.
    verdict["n_valid_offsets"] = verdict["n_valid_offsets"].astype(int)
    verdict["n_pass_offsets"] = verdict["n_pass_offsets"].astype(int)
    has_valid = verdict["n_valid_offsets"] > 0
    verdict["pass_rate"] = pd.NA
    verdict.loc[has_valid, "pass_rate"] = (
        verdict.loc[has_valid, "n_pass_offsets"]
        / verdict.loc[has_valid, "n_valid_offsets"]
    )
    verdict["verdict"] = "INVALID"
    verdict.loc[has_valid & (verdict["pass_rate"] >= PASS_THRESHOLD), "verdict"] = (
        "PASS"
    )
    verdict.loc[has_valid & (verdict["pass_rate"] < PASS_THRESHOLD), "verdict"] = "FAIL"

    # Attach cell_bracket
    verdict = verdict.merge(cell_bracket, on=["asset", "month"])

    # Sort by (asset_order, month, sub_test_order)
    verdict["_asset_rank"] = verdict["asset"].map(
        {a: i for i, a in enumerate(ASSET_ORDER)}
    )
    verdict["_subtest_rank"] = verdict["sub_test"].map(
        {s: i for i, s in enumerate(ALL_SUB_TESTS)}
    )
    verdict = (
        verdict.sort_values(["_asset_rank", "month", "_subtest_rank"])
        .drop(columns=["_asset_rank", "_subtest_rank"])
        .reset_index(drop=True)
    )

    return verdict[
        [
            "asset",
            "month",
            "sub_test",
            "cell_bracket",
            "n_offsets",
            "n_valid_offsets",
            "n_pass_offsets",
            "pass_rate",
            "verdict",
        ]
    ]


def _build_per_asset_summary(verdict: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cell-level verdicts to per-(asset, sub_test) summary.

    Per plan §1.6:
      n_admissible_months = months where verdict != "INVALID"  (denominator Y)
      n_passed_months     = months where verdict == "PASS" (numerator X)
      pass_rate           = X / Y
      dominant_bracket    = most-common cell_bracket for this asset
                            (constant across sub_tests of one asset)
    """
    # dominant_bracket per asset (mode of cell_bracket across unique months)
    cell_brackets = verdict.drop_duplicates(["asset", "month"])[
        ["asset", "cell_bracket"]
    ]
    dom = (
        cell_brackets.groupby("asset")["cell_bracket"]
        .agg(lambda s: s.mode().iloc[0])
        .reset_index()
        .rename(columns={"cell_bracket": "dominant_bracket"})
    )

    # n_admissible / n_passed per (asset, sub_test)
    summary = (
        verdict.groupby(["asset", "sub_test"], sort=False)
        .agg(
            n_admissible_months=("verdict", lambda s: int((s != "INVALID").sum())),
            n_passed_months=("verdict", lambda s: int((s == "PASS").sum())),
        )
        .reset_index()
    )
    summary["pass_rate"] = summary["n_passed_months"] / summary[
        "n_admissible_months"
    ].replace(0, pd.NA)
    summary = summary.merge(dom, on="asset")

    # Sort by (asset_order, sub_test_order)
    summary["_asset_rank"] = summary["asset"].map(
        {a: i for i, a in enumerate(ASSET_ORDER)}
    )
    summary["_subtest_rank"] = summary["sub_test"].map(
        {s: i for i, s in enumerate(ALL_SUB_TESTS)}
    )
    summary = (
        summary.sort_values(["_asset_rank", "_subtest_rank"])
        .drop(columns=["_asset_rank", "_subtest_rank"])
        .reset_index(drop=True)
    )

    return summary[
        [
            "asset",
            "sub_test",
            "n_admissible_months",
            "n_passed_months",
            "pass_rate",
            "dominant_bracket",
        ]
    ]


# Display helpers


def _print_per_asset_matrix(summary: pd.DataFrame) -> None:
    """5 × 12 matrix showing 'X/Y' per (asset, sub_test) cell."""
    pivot_pass = summary.pivot(
        index="sub_test", columns="asset", values="n_passed_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)
    pivot_adm = summary.pivot(
        index="sub_test", columns="asset", values="n_admissible_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)

    print(f"\nPer-asset × sub-test (n_passed / n_admissible)")
    print(f"  pass criterion: cell pass_rate ≥ {PASS_THRESHOLD:.2f} at α = {ALPHA}")
    print()

    def _fmt(x: object) -> str:
        # NaN appears if the pivot is missing an (asset, sub_test) cell;
        # str() also quiets Pyright's Scalar-includes-complex complaint.
        return " -" if pd.isna(x) else f"{int(x):>2}"  # type: ignore[arg-type]

    # header
    print(
        f"  {'sub_test':<18}" + " ".join(f"  {ASSET_SHORT[a]:>5}" for a in ASSET_ORDER)
    )
    for sub_test in ALL_SUB_TESTS:
        parts = [f"  {sub_test:<18}"]
        for asset in ASSET_ORDER:
            p = pivot_pass.loc[sub_test, asset]
            a = pivot_adm.loc[sub_test, asset]
            parts.append(f"  {_fmt(p)}/{_fmt(a)}")
        print("".join(parts))


def _print_per_cell_verdict_matrix(verdict: pd.DataFrame) -> None:
    """5 sections (per asset), each a months × 12 sub-tests verdict matrix."""
    short = {
        "D_adaptive": "D_a",
        "D_k2": "D_2",
        "Monobit": "Mb",
        "Runs": "Rn",
        "ApEn": "AE",
        "BlockFrequency": "BF",
        "CumSum_forward": "CSf",
        "CumSum_backward": "CSb",
        "LongestRun": "LR",
        "DFT": "DF",
        "Serial_m": "Sm",
        "Serial_m_minus_1": "Sm1",
    }
    verdict_char = {"PASS": "✓", "FAIL": "✗", "INVALID": "-"}

    print(f"\nPer-cell verdict matrix (✓ = pass, ✗ = fail, - = sanity NA):")
    for asset in ASSET_ORDER:
        sub = verdict[verdict.asset == asset]
        if sub.empty:
            continue
        pivot = (
            sub.pivot(index="month", columns="sub_test", values="verdict")
            .reindex(columns=ALL_SUB_TESTS)
            .replace(verdict_char)
        )
        pivot.columns = [short[c] for c in pivot.columns]
        print(f"\n{ASSET_SHORT[asset]}:")
        print(pivot.to_string())


# Main


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    input_path = project_root / INPUT_PATH
    per_cell_verdict_path = project_root / PER_CELL_VERDICT_PATH
    per_asset_summary_path = project_root / PER_ASSET_SUMMARY_PATH

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input not found: {input_path}\n"
            f"Run `python scripts/runner_exp3_battery.py` (with GATE={GATE!r}) first."
        )

    print(f"[config] GATE={GATE!r}, α={ALPHA}, pass threshold={PASS_THRESHOLD}")
    print(f"[config] input:  {input_path}")
    print(f"[config] output: {per_cell_verdict_path}")
    print(f"[config] output: {per_asset_summary_path}")
    print()

    df = pd.read_csv(input_path)
    print(f"[load] {len(df):,} rows from {input_path.name}")

    verdict = _build_per_cell_verdict(df)
    print(f"[verdict] {len(verdict):,} (asset, month, sub_test) cells")

    summary = _build_per_asset_summary(verdict)
    print(f"[summary] {len(summary):,} (asset, sub_test) rows")

    # Save
    verdict.to_csv(per_cell_verdict_path, index=False)
    summary.to_csv(per_asset_summary_path, index=False)
    print(f"\n[saved] {per_cell_verdict_path}")
    print(f"[saved] {per_asset_summary_path}")

    # Display
    _print_per_asset_matrix(summary)
    _print_per_cell_verdict_matrix(verdict)

    # Headline stats
    n_pass = (verdict["verdict"] == "PASS").sum()
    n_fail = (verdict["verdict"] == "FAIL").sum()
    n_invalid = (verdict["verdict"] == "INVALID").sum()
    total = len(verdict)
    print(
        f"\n[headline] {n_pass}/{total} cell-tests PASS  ({n_pass/total:.1%}); "
        f"{n_fail} FAIL; {n_invalid} INVALID (sanity-excluded)"
    )


if __name__ == "__main__":
    main()
