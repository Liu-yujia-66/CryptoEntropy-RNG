from __future__ import annotations

"""
Plot Experiment 3 figures.

Path layout (per-criterion subdir under data/processed/experiment3/):

    experiment3/{gate}-gate/
        per_cell_pvalues.csv     <- read
        per_asset_summary.csv    <- read
        figures/
            pass_rate_per_asset.png    <- write
            length_vs_pvalue.png       <- write

Figures:
- `pass_rate_per_asset.png`
   29 sub-tests × 5 assets heatmap, color = pass_rate, annotation = "X/Y"
- `length_vs_pvalue.png`
   29-panel facet (5 × 6 grid; the 30th panel holds the legend),
   x = per_offset_bits (log), y = -log10(p), colored by asset,
   red dashed line = -log10(α=0.01)

Normally invoked at the end of `runner_exp3_battery.py`, which forwards
its own GATE via `--gate`. Standalone use:

    python scripts/plot_exp3.py --gate runs
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.battery import ALL_SUB_TESTS
from src.utils import ASSET_COLORS


VALID_GATES = ("base", "runs", "apen")
ALPHA = 0.01

# Monochrome "ink" palette (no red/green): pass-rate heatmap maps high
# pass-rate -> faint, low pass-rate -> deep navy so failures stand out.
from matplotlib.colors import LinearSegmentedColormap as _LSC
INK = "#16324f"
# Same saturated-blue ramp as the MI matrix; reversed so low pass-rate
# (failures) reads deep navy and high pass-rate reads faint blue.
PASS_RATE_CMAP = _LSC.from_list("inkpass", ["#08306b", "#4292c6", "#e8f1fa"])
PASS_RATE_CMAP.set_bad("white")

# Display asset order (BTC, ETH, BNB, SOL, DOGE), NOT the alphabetical
# `src.utils.ASSET_ORDER`. Matches scripts/aggregate_exp3_battery.py so
# Exp 3 figures and tables share one order.
ASSET_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

ASSET_SHORT = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "BNBUSDT": "BNB",
    "SOLUSDT": "SOL", "DOGEUSDT": "DOGE",
}


def _criterion_label(gate: str) -> str:
    return {
        "base": "base criterion",
        "runs": "+Runs criterion",
        "apen": "+Runs + ApEn criterion",
    }.get(gate, f"{gate} criterion")


def _paths_for_gate(gate: str) -> tuple[Path, Path, Path, Path]:
    """Return (per_asset_input, per_cell_input, heatmap_out, scatter_out)."""
    gate_dir = Path("data/processed/experiment3") / f"{gate}-gate"
    fig_dir = gate_dir / "figures"
    return (
        gate_dir / "per_asset_summary.csv",
        gate_dir / "per_cell_pvalues.csv",
        fig_dir / "pass_rate_per_asset.png",
        fig_dir / "length_vs_pvalue.png",
    )


def plot_heatmap(summary: pd.DataFrame, out_path: Path, gate: str) -> None:
    """5 asset × 29 sub-test pass-rate heatmap, annotated with X/Y counts."""
    pr_pivot = summary.pivot(
        index="sub_test", columns="asset", values="pass_rate"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)
    pass_pivot = summary.pivot(
        index="sub_test", columns="asset", values="n_passed_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)
    adm_pivot = summary.pivot(
        index="sub_test", columns="asset", values="n_admissible_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)

    # Height ~0.4 in/row: 29 rows × 0.4 ≈ 12 in (fits A4 page).
    fig, ax = plt.subplots(figsize=(7, 12))
    # pass_rate is NA when n_admissible_months == 0 (e.g. an Alphabit sub-test
    # like MultinomialBitsOver_L16 for an asset with no ≥100K cell — ETH has
    # zero 100K cells). pd.to_numeric coerces pd.NA → NaN so imshow renders it
    # blank instead of `.astype(float)` choking on NAType.
    data = pr_pivot.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    im = ax.imshow(data, cmap=PASS_RATE_CMAP, vmin=0.0, vmax=1.0, aspect="auto")

    # Annotate every cell with "X/Y" — choose text color for contrast.
    for i, sub_test in enumerate(ALL_SUB_TESTS):
        for j, asset in enumerate(ASSET_ORDER):
            rate = data[i, j]
            p = pass_pivot.loc[sub_test, asset]
            a = adm_pivot.loc[sub_test, asset]
            if pd.isna(a):
                continue  # (asset, sub_test) absent from summary — skip
            text_color = (
                "white" if (pd.notna(rate) and rate < 0.5) else "#1a1a1a"
            )
            ax.text(
                j, i, f"{int(p)}/{int(a)}",
                ha="center", va="center", color=text_color, fontsize=9,
            )

    ax.set_xticks(range(len(ASSET_ORDER)))
    ax.set_xticklabels([ASSET_SHORT[a] for a in ASSET_ORDER])
    ax.set_yticks(range(len(ALL_SUB_TESTS)))
    ax.set_yticklabels(ALL_SUB_TESTS)
    ax.set_xlabel("asset")
    ax.set_ylabel("sub-test")
    criterion_label = _criterion_label(gate)
    ax.set_title(
        f"Experiment 3 — per-asset × sub-test pass rate ({criterion_label})\n"
        f"cell-level verdict: pass_rate ≥ 0.80 at α = {ALPHA};  "
        f"annotation: X / Y where Y = sanity-admissible months",
        fontsize=10,
        pad=28,
    )

    cbar = fig.colorbar(im, ax=ax, shrink=0.75, fraction=0.075, pad=0.04, label="pass_rate")
    cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def plot_length_vs_pvalue(pvalues: pd.DataFrame, out_path: Path, gate: str) -> None:
    """29-panel facet (5 × 6 grid; the 30th panel holds the legend):
    per-cell median bit length vs median -log10(p).

    Each point is one (asset, month) cell. Aggregating offsets → cell:
      x = median per_offset_bits across all offsets in the cell
      y = median -log10(p_value) across sanity-valid offsets only

    Cells with zero sanity-valid offsets (e.g. LongestRun on 5K-bracket cells,
    or ETH 2025-05 on the base criterion where ℓ\* falls under 5K) contribute no
    point — they are documented as INVALID in the per_cell_verdict CSV but
    not on this figure.

    Red dashed horizontal line at y = -log10(α=0.01) = 2 is a reference,
    NOT the cell-level pass criterion. A cell above the line has the median
    offset's p < α (likely fails verdict); below the line, median p ≥ α
    (likely passes). Cell-level verdict is actually based on the 80%-pass-
    rate rule, so the line is a rough but-not-strict indicator.

    Diagnostic purpose: if within one sub-test panel the points drift
    systematically (y grows as x shrinks), then p-values still depend on
    length inside a sanity-valid bracket — implying the 5-bracket sanity
    grid is too coarse.
    """
    criterion_label = _criterion_label(gate)
    # -log10(p_value) per offset, clipped to avoid -inf
    pvalues = pvalues.copy()
    pvalues["neg_log_p"] = -np.log10(np.clip(pvalues["p_value"].to_numpy(), 1e-10, 1.0))

    # Aggregate to (asset, month, sub_test): one point per cell.
    # y aggregation is over sanity-valid offsets only (matches cell verdict logic).
    valid_only = pvalues[pvalues.sanity_valid]
    per_cell = (
        valid_only.groupby(["asset", "month", "sub_test"], sort=False)
        .agg(
            bits_median=("per_offset_bits", "median"),
            neg_log_p_median=("neg_log_p", "median"),
            n_valid=("p_value", "size"),
        )
        .reset_index()
    )
    threshold = -np.log10(ALPHA)

    # 5 rows × 6 cols = 30 panels for 29 sub-tests; the 30th holds the legend.
    fig, axes = plt.subplots(5, 6, figsize=(20, 14), sharex=True, sharey=True)
    axes_flat = axes.flatten()

    for i, sub_test in enumerate(ALL_SUB_TESTS):
        ax = axes_flat[i]
        sub = per_cell[per_cell.sub_test == sub_test]
        for asset in ASSET_ORDER:
            asset_data = sub[sub.asset == asset]
            color = ASSET_COLORS.get(asset, "#888888")
            ax.scatter(
                asset_data["bits_median"],
                asset_data["neg_log_p_median"],
                c=color, s=35, alpha=0.75, label=ASSET_SHORT[asset],
                edgecolors="white", linewidth=0.5,
            )
        ax.axhline(threshold, color="red", linestyle="--", linewidth=0.7)
        ax.set_xscale("log")
        ax.set_title(sub_test, fontsize=9)
        ax.grid(linestyle=":", alpha=0.3)

    # Common axis labels (only on bottom row / left column due to sharex/sharey)
    for ax in axes[-1, :]:
        ax.set_xlabel("median per_offset_bits per cell (log)")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"median $-\log_{10}(p)$ per cell")

    # Shared legend: 5 assets + the α reference line.
    handles, labels = axes_flat[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="red", linestyle="--", linewidth=0.7))
    labels.append(rf"$-\log_{{10}}(\alpha={ALPHA})$")

    # 30 panels for 29 sub-tests: drop the legend into the first empty panel
    # instead of floating it over a data panel; hide any remaining extras.
    extras = list(range(len(ALL_SUB_TESTS), len(axes_flat)))
    if extras:
        legend_ax = axes_flat[extras[0]]
        legend_ax.axis("off")
        legend_ax.legend(
            handles, labels, loc="center",
            fontsize=11, frameon=True, markerscale=1.6,
        )
        for j in extras[1:]:
            axes_flat[j].set_visible(False)
    else:
        fig.legend(
            handles, labels,
            loc="upper right", bbox_to_anchor=(0.995, 0.965),
            fontsize=9, frameon=True, markerscale=1.4,
        )

    n_cells = per_cell.groupby("sub_test").size().median()
    fig.suptitle(
        f"Experiment 3 — per-cell median (bit length, $-\\log_{{10}}(p)$) "
        f"by sub-test ({criterion_label})\n"
        f"each point = one (asset, month) cell; ~{int(n_cells)} cells per panel; "
        f"aggregation over sanity-valid offsets only",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot Exp 3 figures from per-cell pvalues and per-asset summary."
    )
    parser.add_argument(
        "--gate", choices=VALID_GATES, default="runs",
        help="which gate's outputs to plot (default: runs)",
    )
    args = parser.parse_args()
    gate = args.gate

    project_root = Path(__file__).resolve().parent.parent
    per_asset_rel, per_cell_rel, heatmap_rel, scatter_rel = _paths_for_gate(gate)
    per_asset_path = project_root / per_asset_rel
    per_cell_path = project_root / per_cell_rel
    heatmap_path = project_root / heatmap_rel
    scatter_path = project_root / scatter_rel

    if not per_asset_path.exists():
        raise FileNotFoundError(
            f"Missing {per_asset_path}; "
            f"run `python scripts/aggregate_exp3_battery.py --gate {gate}` first."
        )
    if not per_cell_path.exists():
        raise FileNotFoundError(
            f"Missing {per_cell_path}; "
            f"run `python scripts/runner_exp3_battery.py` with criterion={gate!r} first."
        )

    summary = pd.read_csv(per_asset_path)
    pvalues = pd.read_csv(per_cell_path)
    print(f"[config] gate={gate!r}, α={ALPHA}")
    print(f"[load] {len(summary):>3,} rows from {per_asset_path.name}")
    print(f"[load] {len(pvalues):>3,} rows from {per_cell_path.name}")

    plot_heatmap(summary, heatmap_path, gate)
    plot_length_vs_pvalue(pvalues, scatter_path, gate)


if __name__ == "__main__":
    main()
