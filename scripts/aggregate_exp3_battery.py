from __future__ import annotations

"""
Aggregate Experiment 3 per-cell p-values into per-cell verdicts and a
per-asset summary.

Reads `per_cell_pvalues-{GATE}.csv` (produced by `runner_exp3_battery.py`)
and applies the cell-level verdict rule:

    For each (asset, month, sub_test) cell:
      if the sub_test produced no p-value rows for this cell (an Alphabit
      sub-test TestU01 length-skipped on every offset stream):
          verdict = "NOT_RUN"    (does NOT enter n_admissible_months)
      else:
          valid_offsets = offsets in this cell with sanity_valid=True
          if |valid_offsets| == 0:
              verdict = "INVALID" (ran, but sanity-failed; not admissible)
          else:
              pass_rate = mean(p >= α  for o in valid_offsets)
              verdict = "PASS" if pass_rate >= 0.80 else "FAIL"

    For each (asset, sub_test):
      n_admissible_months = # months where verdict in {PASS, FAIL}
      n_passed_months     = # months where verdict == "PASS"
      pass_rate           = n_passed_months / n_admissible_months

    NOT_RUN vs INVALID: NOT_RUN = TestU01 never ran the sub-test at this
    length (its own length eligibility); INVALID = the sub-test ran but
    every offset landed in a sanity-failed bracket. Both stay out of the
    admissible denominator, but are kept distinct so per_cell_verdict
    preserves a three-state record (passed / failed / not_run).

    NOTE: verdict uses literal "PASS"/"FAIL"/"INVALID"/"NOT_RUN". "N/A"
    and "NA" are in `pd.read_csv` default na_values and would be silently
    converted to NaN downstream; none of the four strings used here are,
    so they all read back as plain strings.

Path layout (per-gate subdir under data/processed/experiment3/):

    experiment3/{gate}-gate/
        per_cell_pvalues.csv      <- read (runner output)
        per_cell_verdict.csv      <- write
        per_asset_summary.csv     <- write

Writes two CSVs side-by-side with the input:

- `per_cell_verdict.csv`   (N cells × 29 sub-tests; per-cell verdict)
  - long format: asset, month, sub_test, cell_bracket, n_offsets,
    n_valid_offsets, n_pass_offsets, pass_rate, verdict
  - "29 sub-tests" = 5 stats.py + 7 nistrng + 17 Alphabit. This CSV is a
    complete N×29 grid: an Alphabit sub-test TestU01 length-skipped on a
    cell's streams gets an explicit verdict="NOT_RUN" row (n_offsets=0),
    not a missing row — keeping "TestU01 didn't run it" distinct from
    "ran and sanity-failed" (INVALID).
- `per_asset_summary.csv`  (5 assets × 29 sub-tests; the main result)
  - schema: asset, sub_test, n_admissible_months,
    n_passed_months, pass_rate, dominant_bracket

Both are stable-sorted so re-runs produce identical bytes.

Normally invoked at the end of `runner_exp3_battery.py`, which forwards
its own GATE via `--gate`. Standalone use:

    python scripts/aggregate_exp3_battery.py --gate runs
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.battery import ALL_SUB_TESTS

# Configuration

VALID_GATES = ("base", "runs", "apen")
ALPHA = 0.01
PASS_THRESHOLD = 0.80


def _paths_for_gate(gate: str) -> tuple[Path, Path, Path]:
    """Return (input pvalues, output verdict, output summary) paths for `gate`.

    All three live under `data/processed/experiment3/{gate}-gate/` so each
    gate's artefacts cluster together (instead of `-{gate}.csv` suffixes
    scattered across the parent dir).
    """
    gate_dir = Path("data/processed/experiment3") / f"{gate}-gate"
    return (
        gate_dir / "per_cell_pvalues.csv",
        gate_dir / "per_cell_verdict.csv",
        gate_dir / "per_asset_summary.csv",
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


# Aggregation


def _build_per_cell_verdict(df: pd.DataFrame) -> pd.DataFrame:
    """Long-format cell-level verdict, as a complete (asset, month) × 29
    sub-test grid. One row per (asset, month, sub_test).

    A (cell, sub_test) combination with no p-value rows in `df` is an
    Alphabit sub-test that TestU01 length-skipped on this cell's streams —
    the 12 fixed stats.py/nistrng sub-tests always emit a p-value, so a
    missing row is always an Alphabit length-skip. Such combinations get
    verdict="NOT_RUN" so the output stays a full N×29 grid and preserves
    the three-state record (passed / failed / not_run).

    The cell_bracket column is the sanity bracket the cell falls into
    (taken from the first offset's bracket — within a cell, offsets share
    the same per_offset_bits ± drop-zero noise, so bracket is essentially
    constant).
    """
    # cell_bracket per (asset, month): take first observed bracket
    cell_bracket = df.drop_duplicates(["asset", "month"])[
        ["asset", "month", "sanity_bracket"]
    ].rename(columns={"sanity_bracket": "cell_bracket"})

    # Per (asset, month, sub_test) counts over the p-value rows that exist.
    # Precompute the "valid-and-passing" indicator as a column so agg can
    # sum it directly — avoids a per-group apply (slow + the
    # `include_groups=` overload trips type-checkers).
    df_aug = df.assign(_pass=(df["p_value"] >= ALPHA) & df["sanity_valid"].astype(bool))
    observed = (
        df_aug.groupby(["asset", "month", "sub_test"], sort=False)
        .agg(
            n_offsets=("p_value", "size"),
            n_valid_offsets=("sanity_valid", "sum"),  # True counts as 1
            n_pass_offsets=("_pass", "sum"),
        )
        .reset_index()
    )

    # Expand to the full (asset, month) × ALL_SUB_TESTS grid; rows absent
    # from `observed` are Alphabit length-skips -> NOT_RUN below.
    cells = df[["asset", "month"]].drop_duplicates()
    full_grid = cells.merge(pd.DataFrame({"sub_test": ALL_SUB_TESTS}), how="cross")
    verdict = full_grid.merge(observed, on=["asset", "month", "sub_test"], how="left")

    # not_run: the (cell, sub_test) had zero p-value rows (compute before fillna).
    not_run = verdict["n_offsets"].isna()
    for col in ("n_offsets", "n_valid_offsets", "n_pass_offsets"):
        verdict[col] = verdict[col].fillna(0).astype(int)

    # pass_rate over valid offsets; verdict ∈ {PASS, FAIL, INVALID, NOT_RUN}.
    # NOTE: literal "INVALID"/"NOT_RUN" — pd.read_csv default na_values
    # includes both "N/A" AND "NA" (and other variants), which would
    # silently convert those verdicts to NaN downstream. Neither "INVALID"
    # nor "NOT_RUN" is in pandas' default na_values, so consumers read them
    # back as plain strings.
    has_valid = verdict["n_valid_offsets"] > 0
    verdict["pass_rate"] = pd.NA
    verdict.loc[has_valid, "pass_rate"] = (
        verdict.loc[has_valid, "n_pass_offsets"]
        / verdict.loc[has_valid, "n_valid_offsets"]
    )
    # Default INVALID (ran, no sanity-valid offset); NOT_RUN overrides it for
    # length-skipped sub-tests; PASS/FAIL override it where offsets ran.
    verdict["verdict"] = "INVALID"
    verdict.loc[not_run, "verdict"] = "NOT_RUN"
    verdict.loc[has_valid & (verdict["pass_rate"] >= PASS_THRESHOLD), "verdict"] = (
        "PASS"
    )
    verdict.loc[has_valid & (verdict["pass_rate"] < PASS_THRESHOLD), "verdict"] = "FAIL"

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

      n_admissible_months = months where verdict in {PASS, FAIL} (denom Y)
                            — excludes INVALID (sanity-failed) and NOT_RUN
                            (TestU01 length-skip)
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

    # n_admissible / n_passed per (asset, sub_test). Admissible = the
    # sub-test ran AND was sanity-valid -> only PASS / FAIL count; both
    # INVALID (ran, sanity-failed) and NOT_RUN (TestU01 length-skip) are
    # excluded from the denominator.
    summary = (
        verdict.groupby(["asset", "sub_test"], sort=False)
        .agg(
            n_admissible_months=(
                "verdict",
                lambda s: int(s.isin(["PASS", "FAIL"]).sum()),
            ),
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
    """5 × 29 matrix showing 'X/Y' per (asset, sub_test) cell."""
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
    """5 sections (per asset), each a months × 29 sub-tests verdict matrix."""
    short = {
        # stats.py (5) + nistrng (7) = 12 fixed sub-tests
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
        # TestU01 Alphabit (17): 4 MultinomialBitsOver + 2 HammingIndep +
        # 1 HammingCorr + 5 RandomWalk1 L=64 + 5 RandomWalk1 L=320
        "Alphabit_MultinomialBitsOver_L2":  "MnB2",
        "Alphabit_MultinomialBitsOver_L4":  "MnB4",
        "Alphabit_MultinomialBitsOver_L8":  "MnB8",
        "Alphabit_MultinomialBitsOver_L16": "MnB16",
        "Alphabit_HammingIndep_L16": "HmI16",
        "Alphabit_HammingIndep_L32": "HmI32",
        "Alphabit_HammingCorr_L32":  "HmC32",
        "Alphabit_RandomWalk1_L64_H":  "RW64H",
        "Alphabit_RandomWalk1_L64_M":  "RW64M",
        "Alphabit_RandomWalk1_L64_J":  "RW64J",
        "Alphabit_RandomWalk1_L64_R":  "RW64R",
        "Alphabit_RandomWalk1_L64_C":  "RW64C",
        "Alphabit_RandomWalk1_L320_H": "R320H",
        "Alphabit_RandomWalk1_L320_M": "R320M",
        "Alphabit_RandomWalk1_L320_J": "R320J",
        "Alphabit_RandomWalk1_L320_R": "R320R",
        "Alphabit_RandomWalk1_L320_C": "R320C",
    }
    verdict_char = {"PASS": "✓", "FAIL": "✗", "INVALID": "-", "NOT_RUN": "·"}

    print(
        "\nPer-cell verdict matrix "
        "(✓ pass, ✗ fail, - sanity-invalid, · TestU01 not-run):"
    )
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
    parser = argparse.ArgumentParser(
        description="Aggregate Exp 3 per-cell p-values into cell verdicts "
                    "and per-asset summary."
    )
    parser.add_argument(
        "--gate", choices=VALID_GATES, default="runs",
        help="which gate's per_cell_pvalues.csv to aggregate (default: runs)",
    )
    args = parser.parse_args()
    gate = args.gate

    project_root = Path(__file__).resolve().parent.parent
    input_rel, verdict_rel, summary_rel = _paths_for_gate(gate)
    input_path = project_root / input_rel
    per_cell_verdict_path = project_root / verdict_rel
    per_asset_summary_path = project_root / summary_rel

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input not found: {input_path}\n"
            f"Run `python scripts/runner_exp3_battery.py` (with GATE={gate!r}) first."
        )

    print(f"[config] gate={gate!r}, α={ALPHA}, pass threshold={PASS_THRESHOLD}")
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

    # Headline stats. PASS rate is over admissible (PASS + FAIL) cell-tests;
    # INVALID (sanity-failed) and NOT_RUN (TestU01 length-skip) are reported
    # separately rather than diluting the denominator.
    n_pass = int((verdict["verdict"] == "PASS").sum())
    n_fail = int((verdict["verdict"] == "FAIL").sum())
    n_invalid = int((verdict["verdict"] == "INVALID").sum())
    n_not_run = int((verdict["verdict"] == "NOT_RUN").sum())
    n_admissible = n_pass + n_fail
    pass_pct = f"{n_pass / n_admissible:.1%}" if n_admissible else "n/a"
    print(
        f"\n[headline] {n_pass}/{n_admissible} admissible cell-tests PASS "
        f"({pass_pct}); {n_fail} FAIL; {n_invalid} INVALID (sanity-failed); "
        f"{n_not_run} NOT_RUN (TestU01 length-skip); {len(verdict)} total"
    )


if __name__ == "__main__":
    main()
