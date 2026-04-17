from __future__ import annotations

"""
Post-process k_acceptance CSVs to select k under different gate criteria.

Reads all_assets_summary_exp2_k_acceptance.csv from each period directory,
picks the smallest acceptable agg_level under three gates:
  - is_acceptable                (predictability + monobit)
  - is_acceptable_with_runs      (predictability + monobit + runs)
  - is_acceptable_with_runs_apen (predictability + monobit + runs + apen)

Outputs a cross-period summary table to stdout and saves
selected_ell_by_window.txt in the data root.

Usage:
    python scripts/select_ell_exp2_1sbars.py \
        --summary-dir "data/processed/experiment2/all-offset-per-month-1sbars(10,700,2)"
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import ASSET_ORDER

DISPLAY_NAMES = {
    "BNBUSDT": "BNB",
    "BTCUSDT": "BTC",
    "DOGEUSDT": "DOGE",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
}
HEADER_ASSETS = [a for a in ASSET_ORDER if a in DISPLAY_NAMES]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select k from k_acceptance CSVs.")
    parser.add_argument("--summary-dir", type=Path, required=True)
    return parser.parse_args()


def _pick_k(df: pd.DataFrame, col: str) -> dict[str, int | None]:
    """For each asset, return the smallest agg_level where col is True."""
    result: dict[str, int | None] = {}
    for asset, group in df.groupby("asset"):
        acceptable = group[group[col]].sort_values("agg_level")
        if acceptable.empty:
            result[str(asset)] = None
        else:
            result[str(asset)] = int(acceptable.iloc[0]["agg_level"])
    return result


def _format_table(
    rows: list[tuple[str, dict[str, int | None]]],
) -> list[str]:
    lines: list[str] = []
    window_width = max(len("Window"), max(len(label) for label, _ in rows))
    asset_widths = []
    for i, asset in enumerate(HEADER_ASSETS):
        display = DISPLAY_NAMES[asset]
        col_vals = [
            str(sel.get(asset, "-") or "-") for _, sel in rows
        ]
        width = max(len(display), max(len(v) for v in col_vals))
        asset_widths.append(width)

    header = " | ".join(
        [f"{'Window':<{window_width}}"]
        + [
            f"{DISPLAY_NAMES[asset]:<{asset_widths[i]}}"
            for i, asset in enumerate(HEADER_ASSETS)
        ]
    )
    separator = "-+-".join(
        "-" * w for w in [window_width, *asset_widths]
    )
    lines.append(header)
    lines.append(separator)
    for label, sel in rows:
        vals = []
        for i, asset in enumerate(HEADER_ASSETS):
            v = sel.get(asset)
            vals.append(f"{'-' if v is None else str(v):<{asset_widths[i]}}")
        lines.append(f"{label:<{window_width}} | " + " | ".join(vals))
    return lines


def main() -> None:
    args = parse_args()
    summary_dir: Path = args.summary_dir

    period_dirs = sorted(
        d for d in summary_dir.iterdir()
        if d.is_dir() and (d / "all_assets_summary_exp2_k_acceptance.csv").exists()
    )
    if not period_dirs:
        print(f"[error] no period directories with k_acceptance found in {summary_dir}")
        return

    base_rows: list[tuple[str, dict[str, int | None]]] = []
    with_runs_rows: list[tuple[str, dict[str, int | None]]] = []
    with_runs_apen_rows: list[tuple[str, dict[str, int | None]]] = []

    for pdir in period_dirs:
        df = pd.read_csv(pdir / "all_assets_summary_exp2_k_acceptance.csv")
        thr = df["pass_rate_threshold"].iloc[0]
        df["is_acceptable_with_runs_apen"] = (
            df["is_acceptable_with_runs"]
            & (df["approximate_entropy_pass_rate"] >= thr)
        )
        label = pdir.name.removeprefix("1month-")
        base_rows.append((label, _pick_k(df, "is_acceptable")))
        with_runs_rows.append((label, _pick_k(df, "is_acceptable_with_runs")))
        with_runs_apen_rows.append(
            (label, _pick_k(df, "is_acceptable_with_runs_apen"))
        )

    base_table = _format_table(base_rows)
    with_runs_table = _format_table(with_runs_rows)
    with_runs_apen_table = _format_table(with_runs_apen_rows)

    # Read config from first CSV
    sample = pd.read_csv(
        period_dirs[0] / "all_assets_summary_exp2_k_acceptance.csv", nrows=1
    )
    alpha = sample["alpha"].iloc[0] if "alpha" in sample.columns else "?"
    threshold = (
        sample["pass_rate_threshold"].iloc[0]
        if "pass_rate_threshold" in sample.columns
        else "?"
    )

    selection_lines = [
        "",
        f"Selected ell per window (PASS_RATE_THRESHOLD = {threshold}, ALPHA = {alpha})",
        "",
        "Gate: predictability + monobit",
        *base_table,
        "",
        "Gate: predictability + monobit + runs",
        *with_runs_table,
        "",
        "Gate: predictability + monobit + runs + apen",
        *with_runs_apen_table,
    ]

    selection_text = "\n".join(selection_lines)
    print(selection_text)

    out_path = summary_dir / "selected_ell_by_window.txt"
    if out_path.exists():
        existing = out_path.read_text(encoding="utf-8")
        lines = existing.split("\n")
        # Insert after the AGG_STEP line
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("AGG_STEP"):
                insert_idx = i + 1
                break
        if insert_idx is not None:
            for sel_line in reversed(selection_lines):
                lines.insert(insert_idx, sel_line)
            out_path.write_text("\n".join(lines), encoding="utf-8")
        else:
            out_path.write_text(existing.rstrip("\n") + "\n" + selection_text + "\n", encoding="utf-8")
    else:
        out_path.write_text(selection_text + "\n", encoding="utf-8")
    print(f"\n[saved] {out_path}")


if __name__ == "__main__":
    main()
