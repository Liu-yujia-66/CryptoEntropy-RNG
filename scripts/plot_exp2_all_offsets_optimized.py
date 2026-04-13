from __future__ import annotations

from matplotlib.figure import Figure

"""
Redesigned plot utilities for Experiment 2 all-offset results.

Four figures, each serving a distinct purpose in the thesis narrative:

  1. pass_rate_curves.png   — pass rate vs ℓ, 2×2 by test, all assets overlaid;
                              stars mark each asset's selected ℓ on its curve.
  2. asset_panels.png       — per-asset: pass rate curves (left axis) and
                              avg bits/s (right axis, log scale); vertical line
                              at selected ℓ.
  3. tradeoff.png           — parametric trade-off: bottleneck pass rate vs
                              bits/s; each asset traces a curve as ℓ increases.
  4. selection_summary.png  — horizontal lollipop: selected ℓ and bit rate per
                              asset, annotated with the binding test.

Usage (standalone):
    python scripts/plot_exp2_all_offsets_optimized.py \\
        --summary-dir data/processed/experiment2/all-offset/full-3month-2026.01-03

Or invoked automatically by runner_exp2_all_offset.py.
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

from src.utils import ASSET_COLORS, ASSET_ORDER

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_INPUT_ROOT = Path("data/processed/experiment2/all-offset")
DEFAULT_OUTPUT_DIRNAME = "plots"
DEFAULT_FULL_DIRNAME = "full-3month-2026.01-03"

PASS_RATE_THRESHOLD = 0.80

# (csv_column, display_label, counted_in_is_acceptable)
TESTS = [
    ("predictability_pass_rate", "Predictability", True),
    ("shannon_bias_pass_rate", "Shannon Bias", False),
    ("monobit_pass_rate", "Monobit", True),
    ("runs_pass_rate", "Runs", True),
    ("approximate_entropy_pass_rate", "Approx. Entropy (m=5)", False),
]
ACCEPTANCE_COLS = [col for col, _, ok in TESTS if ok]

# Colors for individual tests inside per-asset panels
TEST_COLORS = {
    "predictability_pass_rate": "#1f77b4",
    "shannon_bias_pass_rate": "#9467bd",
    "monobit_pass_rate": "#ff7f0e",
    "runs_pass_rate": "#2ca02c",
    "approximate_entropy_pass_rate": "#d62728",
}

# Short names for the binding-test annotation in the summary chart
_BINDING_SHORT = {
    "predictability_pass_rate": "Pred.",
    "shannon_bias_pass_rate": "Shan.",
    "monobit_pass_rate": "Mono.",
    "runs_pass_rate": "Runs",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot Experiment 2 all-offset summaries."
    )
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=None,
        help="Directly specify the summary directory (overrides --input-root).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_summary_csv(summary_dir: Path, suffix: str) -> pd.DataFrame:
    """Load an all-assets summary CSV, falling back to per-asset files."""
    primary = summary_dir / f"all_assets_summary_exp2_{suffix}.csv"
    if primary.exists():
        return pd.read_csv(primary)

    frames: list[pd.DataFrame] = []
    per_asset = summary_dir / "by_asset"
    if per_asset.is_dir():
        for asset_dir in sorted(per_asset.iterdir()):
            if not asset_dir.is_dir():
                continue
            candidate = asset_dir / f"{asset_dir.name}_summary_exp2_{suffix}.csv"
            if candidate.exists():
                frames.append(pd.read_csv(candidate))

    if not frames:
        raise FileNotFoundError(
            f"No summary CSV for suffix '{suffix}' under {summary_dir}"
        )
    return pd.concat(frames, ignore_index=True)


def _normalize_acceptance_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "agg_level" not in df.columns and "sampling_k" in df.columns:
        df = df.rename(columns={"sampling_k": "agg_level"})
    return df


def _normalize_selected_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "selected_agg_level" not in df.columns and "selected_k" in df.columns:
        df = df.rename(columns={"selected_k": "selected_agg_level"})
    return df


def save_plot(fig: Figure, path: Path, dpi: int = 150) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {path.name}")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _threshold(acceptance_df: pd.DataFrame) -> float:
    if "pass_rate_threshold" in acceptance_df.columns:
        vals = acceptance_df["pass_rate_threshold"].dropna()
        if not vals.empty:
            return float(vals.iloc[0])
    return PASS_RATE_THRESHOLD


def _present_assets(df: pd.DataFrame) -> list[str]:
    return [a for a in ASSET_ORDER if a in df["asset"].values]


def _selected_ell(selected_df: pd.DataFrame, asset: str) -> int | None:
    row = selected_df[selected_df["asset"] == asset]
    if row.empty:
        return None
    val = row["selected_agg_level"].iloc[0]
    return None if pd.isna(val) else int(val)


# ---------------------------------------------------------------------------
# Figure 1: Pass rate vs ℓ  (2×2 by test, all assets)
# ---------------------------------------------------------------------------


def plot_pass_rate_curves(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    2×2 grid of pass-rate-vs-ℓ curves, one panel per statistical test.
    Stars mark each asset's selected ℓ on its own curve.
    ApproxEntropy panel is labelled "(reference)" to reflect that it does
    not enter the is_acceptable rule.
    """
    assets = _present_assets(acceptance_df)
    thr = _threshold(acceptance_df)

    n_tests = len(TESTS)
    n_cols = 2
    n_rows = (n_tests + n_cols - 1) // n_cols
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(12, 4 * n_rows), sharex=True, sharey=True
    )
    fig.suptitle(
        r"Offset Pass Rate vs Aggregation Level $\ell$",
        fontsize=13,
    )

    for ax, (col, label, in_acc) in zip(axes.flat, TESTS):
        if col not in acceptance_df.columns:
            ax.set_visible(False)
            continue

        for asset in assets:
            adf = acceptance_df[acceptance_df["asset"] == asset].sort_values(
                "agg_level"
            )
            c = ASSET_COLORS.get(asset, "#888888")
            ax.plot(
                adf["agg_level"],
                adf[col],
                color=c,
                linewidth=1.4 if in_acc else 0.9,
                alpha=1.0 if in_acc else 0.5,
                label=asset,
            )
            # Star at selected ℓ on this curve
            sel = _selected_ell(selected_df, asset)
            if sel is not None:
                match = adf[adf["agg_level"] == sel]
                if not match.empty:
                    ax.scatter(
                        sel,
                        float(match[col].iloc[0]),
                        color=c,
                        s=70,
                        marker="*",
                        zorder=5,
                    )

        ax.axhline(
            thr,
            color="#cc3333",
            linestyle="--",
            linewidth=1.0,
            label=f"threshold = {thr:.2f}",
        )
        title_suffix = "" if in_acc else "  (reference)"
        ax.set_title(label + title_suffix, fontsize=11)
        ax.set_ylim(-0.02, 1.05)
        ax.grid(True, alpha=0.25)

    # Hide any unused panels (e.g. 6th cell when 5 tests fill a 3×2 grid)
    for extra_ax in list(axes.flat)[n_tests:]:
        extra_ax.set_visible(False)

    # ylabel on left column of every used panel
    for r in range(n_rows):
        axes[r, 0].set_ylabel("Pass Rate")
    # xlabel on the bottom-most visible panel of each column
    for c in range(n_cols):
        for r in range(n_rows - 1, -1, -1):
            if axes[r, c].get_visible():
                axes[r, c].set_xlabel(r"Aggregation Level $\ell$")
                # sharex=True hides tick labels by default on non-bottom rows;
                # re-enable on this column's bottom-most visible panel.
                axes[r, c].tick_params(labelbottom=True)
                break

    # Single shared legend, placed in the first panel
    handles, labels = axes[0, 0].get_legend_handles_labels()
    axes[0, 0].legend(handles, labels, fontsize=7, frameon=True, loc="lower right")

    fig.tight_layout()
    save_plot(fig, output_dir / "pass_rate_curves.png")


# ---------------------------------------------------------------------------
# Figure 2: Per-asset acceptance curves + throughput overlay
# ---------------------------------------------------------------------------


def plot_asset_panels(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    One panel per asset (3-row × 2-col layout).
    Left axis : all four pass-rate curves + acceptance threshold.
    Right axis: avg bits/s on a log scale — shows the throughput cost of
                increasing ℓ alongside the randomness improvement.
    A vertical dash-dot line marks the selected ℓ.
    """
    assets = _present_assets(acceptance_df)
    thr = _threshold(acceptance_df)

    ncols = 2
    nrows = int(np.ceil(len(assets) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4.5 * nrows))
    axes_flat = np.atleast_1d(axes).ravel()
    fig.suptitle(
        r"Per-Asset Acceptance Curves and Throughput vs $\ell$",
        fontsize=13,
    )

    for ax, asset in zip(axes_flat, assets):
        adf = acceptance_df[acceptance_df["asset"] == asset].sort_values("agg_level")
        ax2 = ax.twinx()

        # Pass rate lines (left axis)
        for col, label, in_acc in TESTS:
            if col not in adf.columns:
                continue
            ax.plot(
                adf["agg_level"],
                adf[col],
                color=TEST_COLORS[col],
                linewidth=1.4 if in_acc else 0.9,
                alpha=1.0 if in_acc else 0.45,
                label=label,
            )

        ax.axhline(
            thr,
            color="#444444",
            linestyle="--",
            linewidth=0.9,
            label=f"threshold = {thr:.2f}",
        )

        # Bits/s (right axis, log scale)
        if "avg_bits_per_second" in adf.columns:
            bps_vals = adf["avg_bits_per_second"].replace(0, np.nan)
            ax2.plot(
                adf["agg_level"],
                bps_vals,
                color="#888888",
                linewidth=1.2,
                linestyle="-.",
                alpha=0.8,
                label="bits/s",
            )
            ax2.set_ylabel("bits / s  (log)", color="#888888", fontsize=8)
            ax2.tick_params(axis="y", colors="#888888", labelsize=7)
            ax2.set_yscale("log")

        # Selected-ℓ vertical line
        sel = _selected_ell(selected_df, asset)
        if sel is not None:
            ax.axvline(
                sel,
                color="#000000",
                linestyle="-.",
                linewidth=1.0,
                label=f"ℓ* = {sel}",
            )

        ax.set_title(asset, fontsize=11)
        ax.set_xlabel(r"Aggregation Level $\ell$", fontsize=9)
        ax.set_ylabel("Pass Rate", fontsize=9)
        ax.set_ylim(-0.02, 1.05)
        ax.grid(True, alpha=0.25)

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="lower right", frameon=True)

    for ax in axes_flat[len(assets) :]:
        ax.set_visible(False)

    fig.tight_layout()
    save_plot(fig, output_dir / "asset_panels.png")


# ---------------------------------------------------------------------------
# Figure 3: Randomness vs throughput trade-off  (core thesis figure)
# ---------------------------------------------------------------------------


def plot_tradeoff(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Parametric trade-off: bottleneck pass rate vs avg bits/s (log x-axis).

    For each asset, as ℓ increases the trajectory moves left (lower bits/s)
    and upward (higher pass rate).  The star marks the selected ℓ — the
    rightmost point on the trajectory that first crosses the acceptance
    threshold, i.e. the cheapest ℓ that achieves acceptable randomness.

    Bottleneck pass rate = min(Predictability, Monobit, Runs) — the test
    that is hardest to satisfy at each ℓ.
    """
    assets = _present_assets(acceptance_df)
    thr = _threshold(acceptance_df)

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle(
        r"Randomness–Throughput Trade-off"
        "\n"
        r"(trajectory: $\ell$ increases from right $\rightarrow$ left)",
        fontsize=12,
    )

    for asset in assets:
        adf = acceptance_df[acceptance_df["asset"] == asset].sort_values("agg_level")
        if "avg_bits_per_second" not in adf.columns:
            continue

        avail = [c for c in ACCEPTANCE_COLS if c in adf.columns]
        if not avail:
            continue

        bps = adf["avg_bits_per_second"].replace(0, np.nan).to_numpy(dtype=float)
        bottleneck = adf[avail].min(axis=1).to_numpy(dtype=float)
        ells = adf["agg_level"].to_numpy()
        c = ASSET_COLORS.get(asset, "#888888")

        sel = _selected_ell(selected_df, asset)
        legend_label = (
            f"{asset}  (ℓ* = {sel})" if sel is not None else f"{asset}  (no ℓ selected)"
        )

        ax.plot(bps, bottleneck, color=c, linewidth=1.6, alpha=0.85, label=legend_label)

        # Circle at trajectory start (ℓ=min), square at end (ℓ=max)
        ax.scatter(bps[0], bottleneck[0], color=c, s=35, marker="o", zorder=4)
        ax.scatter(bps[-1], bottleneck[-1], color=c, s=35, marker="s", zorder=4)

        # Annotate the starting ℓ value
        ax.annotate(
            f"ℓ={ells[0]}",
            xy=(bps[0], bottleneck[0]),
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=7,
            color=c,
        )

        # Star at selected ℓ
        if sel is not None:
            m = adf[adf["agg_level"] == sel]
            if not m.empty:
                sx = float(m["avg_bits_per_second"].iloc[0])
                sy = float(m[avail].min(axis=1).iloc[0])
                ax.scatter(
                    sx,
                    sy,
                    color=c,
                    s=200,
                    marker="*",
                    zorder=6,
                    edgecolors="black",
                    linewidths=0.5,
                )

    ax.axhline(
        thr,
        color="#cc3333",
        linestyle="--",
        linewidth=1.1,
        label=f"acceptance threshold = {thr:.2f}",
    )

    ax.set_xscale("log")
    ax.set_xlabel("Average Bits per Second  (log scale)", fontsize=10)
    ax.set_ylabel(
        "Bottleneck Pass Rate\n(min of Predictability, Monobit, Runs)",
        fontsize=9,
    )
    ax.set_ylim(-0.02, 1.05)
    ax.grid(True, alpha=0.25, which="both")
    ax.legend(fontsize=8, frameon=True, loc="upper left")

    fig.tight_layout()
    save_plot(fig, output_dir / "tradeoff.png")


# ---------------------------------------------------------------------------
# Figure 4: Selection summary
# ---------------------------------------------------------------------------


def plot_selection_summary(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Horizontal lollipop chart: selected ℓ (left panel) and corresponding
    avg bits/s (right panel) per asset.  The left panel also annotates the
    binding test — the acceptance test with the lowest pass rate at the
    selected ℓ, i.e. the last barrier to cross.
    """
    assets = _present_assets(selected_df)
    if not assets:
        return

    df = selected_df.set_index("asset").reindex(assets).reset_index()
    y_pos = np.arange(len(df))

    fig, (ax_k, ax_bps) = plt.subplots(
        1,
        2,
        figsize=(12, max(4.0, 1.0 * len(assets))),
        sharey=True,
        gridspec_kw={"width_ratios": [1.3, 1]},
    )
    fig.suptitle(
        r"Experiment 2: Selected $\ell$ and Bit Rate per Asset",
        fontsize=13,
    )

    for y, row in zip(y_pos, df.itertuples()):
        asset = str(row.asset)
        c = ASSET_COLORS.get(asset, "#888888")
        sel_val = getattr(row, "selected_agg_level", float("nan"))
        has_sel = not pd.isna(sel_val)

        if has_sel:
            k_val = int(sel_val)

            ax_k.scatter(k_val, y, s=80, c=[c], zorder=3)
            ax_k.hlines(y, xmin=0, xmax=k_val, colors=[c], linewidth=2.0)
            ax_k.annotate(
                str(k_val),
                xy=(k_val, y),
                xytext=(5, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
            )

            # Binding test: the acceptance test with the lowest pass rate at k_val
            sel_acc = acceptance_df[
                (acceptance_df["asset"] == asset)
                & (acceptance_df["agg_level"] == k_val)
            ]
            if not sel_acc.empty:
                avail = [col for col in ACCEPTANCE_COLS if col in sel_acc.columns]
                if avail:
                    rates = {col: float(sel_acc[col].iloc[0]) for col in avail}
                    binding = min(rates, key=lambda k: rates[k])
                    ax_k.annotate(
                        f"  [{_BINDING_SHORT.get(binding, binding)}: {rates[binding]:.2f}]",
                        xy=(k_val, y),
                        xytext=(32, 0),
                        textcoords="offset points",
                        va="center",
                        fontsize=7,
                        color="#555555",
                        style="italic",
                    )

            bps_val = getattr(row, "avg_bits_per_second", float("nan"))
            if not pd.isna(bps_val):
                bps = float(bps_val)
                ax_bps.scatter(bps, y, s=80, c=[c], zorder=3)
                ax_bps.hlines(y, xmin=0, xmax=bps, colors=[c], linewidth=2.0)
                ax_bps.annotate(
                    f"{bps:.4f}",
                    xy=(bps, y),
                    xytext=(5, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                )
        else:
            for ax in (ax_k, ax_bps):
                ax.scatter(0, y, s=50, c=["#cccccc"], marker="x", zorder=3)
                ax.annotate(
                    "N/A",
                    xy=(0, y),
                    xytext=(8, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                    color="#888888",
                    style="italic",
                )

    ax_k.set_xlabel(r"Selected $\ell$", fontsize=10)
    ax_k.set_title(r"Selected Aggregation Level $\ell$", fontsize=11)
    ax_k.set_yticks(y_pos)
    ax_k.set_yticklabels(df["asset"].tolist())
    ax_k.set_xlim(left=0)
    ax_k.grid(axis="x", alpha=0.25)
    ax_k.invert_yaxis()

    ax_bps.set_xlabel("Average Bits per Second", fontsize=10)
    ax_bps.set_title(r"Bit Rate at Selected $\ell$", fontsize=11)
    ax_bps.set_xlim(left=0)
    ax_bps.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    save_plot(fig, output_dir / "selection_summary.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    summary_dir = (
        args.summary_dir
        if args.summary_dir is not None
        else args.input_root / DEFAULT_FULL_DIRNAME
    )
    output_dir = summary_dir / DEFAULT_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    acceptance_df = _normalize_acceptance_df(
        load_summary_csv(summary_dir, "k_acceptance")
    )
    selected_df = _normalize_selected_df(load_summary_csv(summary_dir, "selected_k"))

    plot_pass_rate_curves(acceptance_df, selected_df, output_dir)
    plot_asset_panels(acceptance_df, selected_df, output_dir)
    plot_tradeoff(acceptance_df, selected_df, output_dir)
    plot_selection_summary(acceptance_df, selected_df, output_dir)


if __name__ == "__main__":
    main()
