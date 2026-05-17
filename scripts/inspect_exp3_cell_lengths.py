from __future__ import annotations

"""
Inspect per-(asset, month) bit stream lengths for Exp 3 planning.

Reads the 1sbar +Runs gate selected ell* from Exp 2 outputs and estimates
the per-offset bit stream length, classifying each cell into a sanity-check
length bracket (<5K / 5K / 10K / 25K / 50K / 100K).

The estimate uses:
    per_offset_bits ≈ avg_bits_per_second × calendar_month_seconds

where avg_bits_per_second is averaged across the valid offsets at the
selected ell* (Exp 2 1sbars runner output). This matches Exp 3's intended
test units (one bit stream per (asset, month, offset)).

Usage:
    python scripts/inspect_exp3_cell_lengths.py
    python scripts/inspect_exp3_cell_lengths.py \
        --input-root "data/processed/experiment2/all-offset-per-month-1sbars(10,600,1)"

Outputs:
    data/processed/experiment3/cell_length_inspection.csv
    plus pretty-printed table to stdout
"""

import argparse
import calendar
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


DEFAULT_INPUT_ROOT = Path(
    "data/processed/experiment2/all-offset-per-month-1sbars(10,600,1)"
)
DEFAULT_OUTPUT = Path("data/processed/experiment3/cell_length_inspection.csv")
DEFAULT_TXT_OUTPUT = Path("data/processed/experiment3/cell_length_inspection.txt")

# Sanity check brackets (lower bounds). Cell with N bits is assigned to the
# largest bracket k such that BRACKETS[k] <= N. Cells < 5K get "<5K".
BRACKETS = [5_000, 10_000, 25_000, 50_000, 100_000]
BRACKET_LABELS = ["5K", "10K", "25K", "50K", "100K"]

ASSET_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
DISPLAY_NAMES = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}


def month_seconds(month_label: str) -> int:
    """Calendar seconds in a YYYY-MM month."""
    year, month = map(int, month_label.split("-"))
    days = calendar.monthrange(year, month)[1]
    return days * 86400


def classify_bracket(bits: float | None) -> str:
    if bits is None or pd.isna(bits):
        return "FAIL"
    if bits < BRACKETS[0]:
        return "<5K"
    for i in range(len(BRACKETS) - 1):
        if bits < BRACKETS[i + 1]:
            return BRACKET_LABELS[i]
    return BRACKET_LABELS[-1]


def find_selected_ell(df: pd.DataFrame, gate_column: str) -> dict[str, int | None]:
    """For each asset, return the smallest agg_level where gate_column is True."""
    result: dict[str, int | None] = {}
    for asset, group in df.groupby("asset"):
        acceptable = group[group[gate_column].astype(bool)].sort_values("agg_level")
        result[str(asset)] = (
            int(acceptable.iloc[0]["agg_level"]) if not acceptable.empty else None
        )
    return result


def cell_bps(df: pd.DataFrame, asset: str, ell: int | None) -> float | None:
    if ell is None:
        return None
    row = df[(df["asset"] == asset) & (df["agg_level"] == ell)]
    if row.empty:
        return None
    val = row["avg_bits_per_second"].iloc[0]
    return float(val) if pd.notna(val) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Exp 2 1sbar per-month output root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the per-cell CSV.",
    )
    parser.add_argument(
        "--txt-output",
        type=Path,
        default=DEFAULT_TXT_OUTPUT,
        help="Where to write the pretty-printed text report.",
    )
    return parser.parse_args()


def _fmt_int(x: int | None) -> str:
    return f"{x:>8,}" if x is not None else "    FAIL"


def _fmt_bracket(b: str) -> str:
    return f"{b:>6}"


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    input_root = project_root / args.input_root
    output_path = project_root / args.output
    txt_output_path = project_root / args.txt_output

    # Collect all printed lines so we can both stdout and txt-file them.
    lines: list[str] = []

    def emit(s: str = "") -> None:
        print(s)
        lines.append(s)

    if not input_root.exists():
        sys.exit(f"[error] input root not found: {input_root}")

    period_dirs = sorted(input_root.glob("1month-*"))
    if not period_dirs:
        sys.exit(f"[error] no 1month-* dirs under {input_root}")

    rows: list[dict[str, object]] = []
    for period_dir in period_dirs:
        csv_path = period_dir / "all_assets_summary_exp2_k_acceptance.csv"
        if not csv_path.exists():
            print(f"[skip] {csv_path} (missing)")
            continue

        # "1month-2025.01" -> "2025-01"
        month_label = period_dir.name.removeprefix("1month-").replace(".", "-")
        sec = month_seconds(month_label)
        df = pd.read_csv(csv_path)

        ell_base_map = find_selected_ell(df, "is_acceptable")
        ell_runs_map = find_selected_ell(df, "is_acceptable_with_runs")

        for asset in ASSET_ORDER:
            ell_base = ell_base_map.get(asset)
            ell_runs = ell_runs_map.get(asset)

            bps_base = cell_bps(df, asset, ell_base)
            bps_runs = cell_bps(df, asset, ell_runs)

            bits_base = bps_base * sec if bps_base is not None else None
            bits_runs = bps_runs * sec if bps_runs is not None else None

            rows.append(
                {
                    "asset": asset,
                    "month": month_label,
                    "month_seconds": sec,
                    "ell_base": ell_base,
                    "ell_runs": ell_runs,
                    "bps_base": bps_base,
                    "bps_runs": bps_runs,
                    "per_offset_bits_base": int(bits_base) if bits_base else None,
                    "per_offset_bits_runs": int(bits_runs) if bits_runs else None,
                    "sanity_bracket_base": classify_bracket(bits_base),
                    "sanity_bracket_runs": classify_bracket(bits_runs),
                }
            )

    if not rows:
        sys.exit("[error] no rows produced")

    out_df = pd.DataFrame(rows).sort_values(["asset", "month"]).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    emit(f"[saved] {output_path}  ({len(out_df)} rows)")
    emit()

    # =========================================================================
    # Per-cell rows: actual length + label (long format, easy to grep)
    # =========================================================================
    emit("=" * 78)
    emit("Per-cell rows: actual bit count + sanity bracket label (+Runs gate)")
    emit("=" * 78)
    emit(
        f"{'asset':<6} {'month':<8} {'ell':>5}  {'per_offset_bits':>15}  bracket"
    )
    emit("-" * 56)
    for _, r in out_df.iterrows():
        asset = DISPLAY_NAMES[str(r["asset"])]
        month = str(r["month"])
        ell = r["ell_runs"]
        bits = r["per_offset_bits_runs"]
        bracket = str(r["sanity_bracket_runs"])
        if pd.notna(ell):
            ell_s = f"{int(ell):>5}"
        else:
            ell_s = "    -"
        if pd.notna(bits):
            bits_s = f"{int(bits):>15,}"
        else:
            bits_s = f"{'FAIL':>15}"
        emit(f"{asset:<6} {month:<8} {ell_s}  {bits_s}  {bracket}")
    emit()

    # =========================================================================
    # Pivot 1: actual bit count, asset × month
    # =========================================================================
    emit("=" * 78)
    emit("Per-offset bit count @ Exp 2 1sbar +Runs gate ell*")
    emit("=" * 78)
    pivot_bits = out_df.pivot(
        index="month", columns="asset", values="per_offset_bits_runs"
    )[ASSET_ORDER]
    pivot_bits = pivot_bits.rename(columns=DISPLAY_NAMES)
    header = "Month       | " + " | ".join(f"{c:>8}" for c in pivot_bits.columns)
    sep = "-" * len(header)
    emit(header)
    emit(sep)
    for month, row in pivot_bits.iterrows():
        cells = " | ".join(_fmt_int(int(v) if pd.notna(v) else None) for v in row)
        emit(f"{month}    | {cells}")
    emit()

    # =========================================================================
    # Pivot 2: sanity bracket label, asset × month
    # =========================================================================
    emit("=" * 78)
    emit("Sanity bracket @ Exp 2 1sbar +Runs gate ell*")
    emit("=" * 78)
    pivot_b = out_df.pivot(
        index="month", columns="asset", values="sanity_bracket_runs"
    )[ASSET_ORDER]
    pivot_b = pivot_b.rename(columns=DISPLAY_NAMES)
    header = "Month       | " + " | ".join(f"{c:>6}" for c in pivot_b.columns)
    sep = "-" * len(header)
    emit(header)
    emit(sep)
    for month, row in pivot_b.iterrows():
        cells = " | ".join(_fmt_bracket(str(v)) for v in row)
        emit(f"{month}    | {cells}")
    emit()

    # =========================================================================
    # Distribution summary
    # =========================================================================
    emit("=" * 78)
    emit("Sanity bracket distribution (+Runs gate)")
    emit("=" * 78)
    bracket_order = ["FAIL", "<5K", "5K", "10K", "25K", "50K", "100K"]
    counts = out_df["sanity_bracket_runs"].value_counts()
    for b in bracket_order:
        if b in counts.index:
            emit(f"  {b:<6}: {counts[b]:>3} cells")
    emit(f"  {'TOTAL':<6}: {len(out_df):>3} cells")
    emit()

    # Per-asset distribution
    emit("Per-asset distribution (+Runs gate):")
    for asset in ASSET_ORDER:
        sub = out_df[out_df["asset"] == asset]
        sub_counts = sub["sanity_bracket_runs"].value_counts()
        parts = [
            f"{b}={int(sub_counts[b])}" for b in bracket_order if b in sub_counts.index
        ]
        emit(f"  {DISPLAY_NAMES[asset]:<5}: {', '.join(parts)}")
    emit()

    # =========================================================================
    # Stats on accepted cells
    # =========================================================================
    valid_bits = out_df["per_offset_bits_runs"].dropna()
    if not valid_bits.empty:
        emit("=" * 78)
        emit(f"Stats on +Runs accepted cells ({len(valid_bits)} of {len(out_df)})")
        emit("=" * 78)
        emit(f"  median: {int(valid_bits.median()):>10,} bits")
        emit(f"  p5:     {int(valid_bits.quantile(0.05)):>10,} bits")
        emit(f"  p25:    {int(valid_bits.quantile(0.25)):>10,} bits")
        emit(f"  p75:    {int(valid_bits.quantile(0.75)):>10,} bits")
        emit(f"  p95:    {int(valid_bits.quantile(0.95)):>10,} bits")
        emit(f"  min:    {int(valid_bits.min()):>10,} bits")
        emit(f"  max:    {int(valid_bits.max()):>10,} bits")
        emit()

    # =========================================================================
    # Useful side info: how often +Runs differs from base in ell* + bits
    # =========================================================================
    emit("=" * 78)
    emit("Base gate (D + Monobit only) comparison")
    emit("=" * 78)
    valid_base = out_df["per_offset_bits_base"].dropna()
    n_base_only = (
        out_df["per_offset_bits_base"].notna() & out_df["per_offset_bits_runs"].isna()
    ).sum()
    emit(f"  Base accepts {len(valid_base)} of {len(out_df)} cells")
    emit(f"  +Runs accepts {len(valid_bits)} of {len(out_df)} cells")
    emit(f"  Cells where base accepts but +Runs rejects: {n_base_only}")
    if not valid_base.empty:
        emit(f"  Base bits median: {int(valid_base.median()):>10,}")
        emit(f"  +Runs bits median:{int(valid_bits.median()):>10,}")
    emit()

    # =========================================================================
    # Write txt
    # =========================================================================
    txt_output_path.parent.mkdir(parents=True, exist_ok=True)
    txt_output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[saved] {txt_output_path}")


if __name__ == "__main__":
    main()
