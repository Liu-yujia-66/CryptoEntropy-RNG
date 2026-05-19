from __future__ import annotations

"""
Plot Experiment 3 figures (per plan §1.6).

Reads:
- `data/processed/experiment3/per_asset_summary-{GATE}.csv`
   (from `scripts/aggregate_exp3_battery.py`)
- `data/processed/experiment3/per_cell_pvalues-{GATE}.csv`
   (from `scripts/runner_exp3_battery.py`)

Writes:
- `data/processed/experiment3/figures/exp3_pass_rate_per_asset-{GATE}.png`
   12 sub-tests × 5 assets heatmap, color = pass_rate, annotation = "X/Y"
- `data/processed/experiment3/figures/exp3_length_vs_pvalue-{GATE}.png`
   12-panel facet, x = per_offset_bits (log), y = -log10(p),
   colored by asset, hollow markers = sanity-invalid offsets,
   red dashed line = -log10(α=0.01)

Switch GATE constant to plot 'base' / 'apen' instead of 'runs'.

Run from project root:
    python scripts/plot_exp3.py
"""

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

from src.nist_extended import ALL_SUB_TESTS
from src.utils import ASSET_COLORS


# Configuration

GATE = "runs"
ALPHA = 0.01

# Use the same asset order as scripts/aggregate_exp3_battery.py and
# plan §1.4 admissible-months table (BTC, ETH, BNB, SOL, DOGE), NOT the
# alphabetical `src.utils.ASSET_ORDER`. Keeps Exp 3 figures / tables /
# plan all aligned to one display order.
ASSET_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

INPUT_DIR = Path("data/processed/experiment3")
PER_ASSET_PATH = INPUT_DIR / f"per_asset_summary-{GATE}.csv"
PER_CELL_PVALUES_PATH = INPUT_DIR / f"per_cell_pvalues-{GATE}.csv"

OUT_DIR = INPUT_DIR / "figures"
HEATMAP_PATH = OUT_DIR / f"exp3_pass_rate_per_asset-{GATE}.png"
SCATTER_PATH = OUT_DIR / f"exp3_length_vs_pvalue-{GATE}.png"

ASSET_SHORT = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "BNBUSDT": "BNB",
    "SOLUSDT": "SOL", "DOGEUSDT": "DOGE",
}


# Figure 1: per-asset × sub-test pass-rate heatmap


def plot_heatmap(summary: pd.DataFrame, out_path: Path) -> None:
    """5 asset × 12 sub-test pass-rate heatmap, annotated with X/Y counts."""
    pr_pivot = summary.pivot(
        index="sub_test", columns="asset", values="pass_rate"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)
    pass_pivot = summary.pivot(
        index="sub_test", columns="asset", values="n_passed_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)
    adm_pivot = summary.pivot(
        index="sub_test", columns="asset", values="n_admissible_months"
    ).reindex(index=ALL_SUB_TESTS, columns=ASSET_ORDER)

    fig, ax = plt.subplots(figsize=(7, 8))
    data = pr_pivot.values.astype(float)
    im = ax.imshow(data, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")

    # Annotate every cell with "X/Y" — choose text color for contrast.
    for i, sub_test in enumerate(ALL_SUB_TESTS):
        for j, asset in enumerate(ASSET_ORDER):
            rate = float(data[i, j])
            p_count = int(pass_pivot.loc[sub_test, asset])
            a_count = int(adm_pivot.loc[sub_test, asset])
            # Black text on the green/yellow band, white on extreme red/dark green
            text_color = "black" if 0.40 <= rate <= 0.90 else "white"
            ax.text(
                j, i, f"{p_count}/{a_count}",
                ha="center", va="center", color=text_color, fontsize=9,
            )

    ax.set_xticks(range(len(ASSET_ORDER)))
    ax.set_xticklabels([ASSET_SHORT[a] for a in ASSET_ORDER])
    ax.set_yticks(range(len(ALL_SUB_TESTS)))
    ax.set_yticklabels(ALL_SUB_TESTS)
    ax.set_xlabel("asset")
    ax.set_ylabel("sub-test")
    ax.set_title(
        f"Experiment 3 — per-asset × sub-test pass rate (GATE={GATE!r})\n"
        f"cell-level verdict: pass_rate ≥ 0.80 at α = {ALPHA};  "
        f"annotation: X / Y where Y = sanity-admissible months",
        fontsize=10,
    )

    cbar = fig.colorbar(im, ax=ax, shrink=0.75, label="pass_rate")
    cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


# Figure 2: length vs -log10(p) scatter, faceted by sub-test


def plot_length_vs_pvalue(pvalues: pd.DataFrame, out_path: Path) -> None:
    """12-panel facet: per-cell median bit length vs median -log10(p).

    Each point is one (asset, month) cell. Aggregating offsets → cell:
      x = median per_offset_bits across all offsets in the cell
      y = median -log10(p_value) across sanity-valid offsets only

    Cells with zero sanity-valid offsets (e.g. LongestRun on 5K-bracket cells,
    or ETH 2025-05 on the base gate where ℓ\* falls under 5K) contribute no
    point — they are documented as INVALID in the per_cell_verdict CSV but
    not on this figure.

    Red dashed horizontal line at y = -log10(α=0.01) = 2 is a reference,
    NOT the cell-level pass criterion. A cell above the line has the median
    offset's p < α (likely fails verdict); below the line, median p ≥ α
    (likely passes). Cell-level verdict is actually based on the 80%-pass-
    rate rule (plan §1.6), so the line is a rough but-not-strict indicator.

    Diagnostic purpose (plan §1.6): if within one sub-test panel the points
    drift systematically (y grows as x shrinks), then p-values still depend
    on length inside a sanity-valid bracket — implying the 5-bracket sanity
    grid is too coarse and should be revisited in Future Work (§5 #5/#6
    decision says: not in this thesis).
    """
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

    fig, axes = plt.subplots(4, 3, figsize=(13, 12), sharex=True, sharey=True)
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
        ax.set_title(sub_test, fontsize=10)
        ax.grid(linestyle=":", alpha=0.3)

    # Common axis labels (only on bottom row / left column due to sharex/sharey)
    for ax in axes[-1, :]:
        ax.set_xlabel("median per_offset_bits per cell (log)")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"median $-\log_{10}(p)$ per cell")

    # Single legend
    handles, labels = axes_flat[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="red", linestyle="--", linewidth=0.7))
    labels.append(rf"$-\log_{{10}}(\alpha={ALPHA})$")
    fig.legend(
        handles, labels,
        loc="upper right", bbox_to_anchor=(0.995, 0.965),
        fontsize=9, frameon=True, markerscale=1.4,
    )

    n_cells = per_cell.groupby("sub_test").size().median()
    fig.suptitle(
        f"Experiment 3 — per-cell median (bit length, $-\\log_{{10}}(p)$) "
        f"by sub-test (GATE={GATE!r})\n"
        f"each point = one (asset, month) cell; ~{int(n_cells)} cells per panel; "
        f"aggregation over sanity-valid offsets only",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


# Main


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    per_asset_path = project_root / PER_ASSET_PATH
    per_cell_path = project_root / PER_CELL_PVALUES_PATH

    if not per_asset_path.exists():
        raise FileNotFoundError(
            f"Missing {per_asset_path}; "
            f"run `python scripts/aggregate_exp3_battery.py` first."
        )
    if not per_cell_path.exists():
        raise FileNotFoundError(
            f"Missing {per_cell_path}; "
            f"run `python scripts/runner_exp3_battery.py` first."
        )

    summary = pd.read_csv(per_asset_path)
    pvalues = pd.read_csv(per_cell_path)
    print(f"[config] GATE={GATE!r}, α={ALPHA}")
    print(f"[load] {len(summary):>3,} rows from {per_asset_path.name}")
    print(f"[load] {len(pvalues):>3,} rows from {per_cell_path.name}")

    plot_heatmap(summary, project_root / HEATMAP_PATH)
    plot_length_vs_pvalue(pvalues, project_root / SCATTER_PATH)


if __name__ == "__main__":
    main()
