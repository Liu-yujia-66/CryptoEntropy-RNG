"""
Experiment 4 — pairwise MI / Pearson heatmap.

Reads mi_pool_matrix.csv and rho_pool_matrix.csv from
scripts/runner_exp4_mi_matrix.py and draws a vertically stacked heatmap
(top: 1-bit mutual information; bottom: Pearson rho), with rows/cols reordered
by ascending row-mean MI for readability (raw CSV stays alphabetical).

Run from the project root after the matrix runner has finished:
    python scripts/plot_exp4_mi_matrix.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap as _LSC

INK = "#16324f"
# Monochrome "ink" colormap (no red/green): light blue -> vivid blue ->
# deep navy; the vivid mid-stop stops the mid-range washing out to grey.
INK_CMAP = _LSC.from_list("ink", ["#e8f1fa", "#4292c6", "#08306b"])

DISPLAY_NAMES = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}

DEFAULT_INPUT_DIR = Path("data/processed/experiment4/mi")
DEFAULT_OUTPUT_PATH = DEFAULT_INPUT_DIR / "figures" / "exp4_mi_matrix.png"

# Near-independent threshold (kept here only to label the colour bar).
NEAR_INDEPENDENT_THRESHOLD_BITS = 1e-3


def _reorder_by_row_mean(matrix: pd.DataFrame) -> list[str]:
    """Return asset order sorted by ascending row-mean (NaN ignored)."""
    means = matrix.mean(axis=1, skipna=True)
    return list(means.sort_values().index)


def _annotate(ax, values: np.ndarray, fmt: str, colour_threshold: float) -> None:
    n = values.shape[0]
    for i in range(n):
        for j in range(n):
            if np.isnan(values[i, j]):
                continue
            colour = "white" if values[i, j] > colour_threshold else "black"
            ax.text(
                j,
                i,
                fmt.format(values[i, j]),
                ha="center",
                va="center",
                color=colour,
                fontsize=9,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot the Experiment 4 pairwise MI / Pearson heatmap."
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help=f"directory containing mi_pool_matrix.csv and rho_pool_matrix.csv "
        f"(default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"output PNG path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--no-reorder",
        action="store_true",
        help="keep alphabetical row/column order (default: sort by mean MI ascending)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    mi_path = input_dir / "mi_pool_matrix.csv"
    rho_path = input_dir / "rho_pool_matrix.csv"
    if not mi_path.exists() or not rho_path.exists():
        print(f"[fatal] missing matrix CSV(s); expected:")
        print(f"          {mi_path}")
        print(f"          {rho_path}")
        return 1

    mi = pd.read_csv(mi_path, index_col=0)
    rho = pd.read_csv(rho_path, index_col=0)

    if not args.no_reorder:
        order = _reorder_by_row_mean(mi)
        mi = mi.loc[order, order]
        rho = rho.loc[order, order]

    labels = [DISPLAY_NAMES.get(a, a) for a in mi.index]
    n = len(labels)

    fig, axes = plt.subplots(2, 1, figsize=(7.0, 7.4))

    # ---- Top: MI heatmap (bits) ----
    ax = axes[0]
    mi_values = mi.values.astype(float)
    mi_masked = np.ma.masked_invalid(mi_values)
    cmap = INK_CMAP.copy()
    cmap.set_bad(color="white")
    vmax = float(np.nanmax(mi_values))
    im = ax.imshow(mi_masked, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels)
    ax.set_title("Pairwise 1-bit mutual information (bits)")
    _annotate(ax, mi_values, "{:.3f}", colour_threshold=0.55)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_label("MI (bits)")

    # ---- Bottom: Pearson heatmap ----
    ax = axes[1]
    rho_values = rho.values.astype(float)
    rho_masked = np.ma.masked_invalid(rho_values)
    cmap = INK_CMAP.copy()
    cmap.set_bad(color="white")
    rho_max = float(np.nanmax(np.abs(rho_values)))
    im = ax.imshow(rho_masked, cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels)
    ax.set_title("Pairwise Pearson correlation $\\rho$")
    _annotate(ax, rho_values, "{:.2f}", colour_threshold=0.55)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_label(r"|$\rho$|")

    fig.suptitle(
        "Per-second sign-bit pairwise dependence on calibration window "
        "(2025-01 .. 2025-09 pool)",
        fontsize=11,
    )
    fig.tight_layout()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")

    # ---- Print one-line subset + threshold summary for cross-checking ----
    print(f"asset order (left→right, top→bottom): {labels}")
    print(
        f"MI range:   {float(np.nanmin(mi_values)):.3f} .. "
        f"{float(np.nanmax(mi_values)):.3f} bits"
    )
    print(
        f"|rho| range: {float(np.nanmin(np.abs(rho_values))):.3f} .. "
        f"{float(np.nanmax(np.abs(rho_values))):.3f}"
    )
    n_above = int(np.nansum(mi_values >= NEAR_INDEPENDENT_THRESHOLD_BITS) // 2)
    n_pairs_total = n * (n - 1) // 2
    print(
        f"pairs at/above {NEAR_INDEPENDENT_THRESHOLD_BITS} bits "
        f"(plan v3.2 §2.4 'near-independent' line): "
        f"{n_above} / {n_pairs_total}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
