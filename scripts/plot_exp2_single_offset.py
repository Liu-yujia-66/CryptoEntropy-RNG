from __future__ import annotations

"""
Plot -log10(p-value) vs aggregation level ell for Experiment 2 single-offset results.

Shows how randomness emerges as the aggregation level ell grows, with a
horizontal threshold line at -log10(alpha). The predictability test itself uses
an adaptive internal block length `predictability_k`, so the per-asset plots
also show that internal order on a secondary axis to make the dependence on ell
explicit.

Default usage:
    python scripts/plot_exp2_single_offset.py --summary-dir data/processed/experiment2/single-offset/full-3month-2026.01-03

Or run automatically via exp2_single_offset_runner.py.
"""

import argparse
import os
import re
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

ALPHA = 0.01
THRESHOLD = -np.log10(ALPHA)

TESTS = [
    ("predictability_pvalue", "Predictability (adaptive k)"),
    ("predictability_k2_pvalue", "Predictability (k=2)"),
    ("shannon_bias_pvalue", "Shannon Bias"),
    ("monobit_pvalue", "Monobit"),
    ("runs_pvalue", "Runs"),
    ("approximate_entropy_pvalue", "Approx. Entropy (m=5)"),
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot -log10(p-value) vs k for single-offset Experiment 2 results."
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        required=True,
        help="Directory containing summary_exp2_single_offset.csv (one period).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to save plots. Defaults to <summary-dir>/plots.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=ALPHA,
        help="Significance level for the threshold line (default 0.01).",
    )
    return parser.parse_args()


def _neg_log10(p: pd.Series) -> pd.Series:
    """Convert p-values to -log10(p), clipping zeros to avoid inf."""
    clipped = p.clip(lower=1e-300)
    return pd.Series(
        -np.log10(clipped.to_numpy()),
        index=clipped.index,
    )


def _extract_period_label(df: pd.DataFrame, summary_dir: Path) -> str:
    """Infer a concise YYYY-MM range label from source_file metadata or directory name."""
    month_pattern = re.compile(r"(\d{4}-\d{2})")
    months: set[str] = set()

    if "source_file" in df.columns:
        for value in df["source_file"].dropna().astype(str):
            months.update(month_pattern.findall(value))

    if months:
        ordered = sorted(months)
        if len(ordered) == 1:
            return ordered[0]
        return f"{ordered[0]} to {ordered[-1]}"

    name_matches = month_pattern.findall(summary_dir.name)
    if name_matches:
        if len(name_matches) == 1:
            return name_matches[0]
        return f"{name_matches[0]} to {name_matches[-1]}"

    return summary_dir.name


def plot_all_assets(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
    period_label: str,
) -> None:
    """3×2 grid — one subplot per test, all assets overlaid. Unused panels hidden."""
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]

    n_tests = len(TESTS)
    n_cols = 2
    n_rows = (n_tests + n_cols - 1) // n_cols
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(12, 4 * n_rows), sharey=False
    )
    fig.suptitle(
        r"$-\log_{10}(p)$ vs Aggregation Level $\ell$  "
        + f"[offset = 0, period = {period_label}]",
        fontsize=13,
    )

    axes_flat = axes.flat if hasattr(axes, "flat") else [axes]
    for ax, (col, label) in zip(axes_flat, TESTS):
        for asset in assets:
            asset_df = df[df["asset"] == asset].sort_values("agg_level")
            valid = asset_df[asset_df["valid"]]
            if valid.empty:
                continue
            y = _neg_log10(valid[col])
            ax.plot(
                valid["agg_level"],
                y,
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=asset,
                color=ASSET_COLORS.get(asset),
            )

        ax.axhline(
            threshold,
            color="red",
            linestyle="--",
            linewidth=1.0,
            label=r"$\alpha$" + f"={alpha}",
        )
        ax.set_title(label, fontsize=11)
        ax.set_xlabel(r"Aggregation Level $\ell$")
        if ax in axes[:, 0]:
            ax.set_ylabel(r"$-\log_{10}(p)$")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    # Hide any unused panels (e.g. 6th cell when 5 tests fill a 3×2 grid)
    for extra_ax in list(axes.flat)[n_tests:]:
        extra_ax.set_visible(False)

    fig.tight_layout()
    out_path = output_dir.parent / "overview.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


def plot_per_asset(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
    period_label: str,
) -> None:
    """
    One figure per asset with all four tests on the main axis.

    The secondary axis shows the adaptive block length used by the
    predictability test, so readers can see that ell changes both the sequence
    and the internal test order through the effective sample size.
    """
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]

    for asset in assets:
        asset_df = df[(df["asset"] == asset) & df["valid"]].sort_values("agg_level")
        if asset_df.empty:
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        ax2 = ax.twinx()
        fig.suptitle(
            r"{} — $-\log_{{10}}(p)$ vs $\ell$".format(asset)
            + f"  [offset = 0, period = {period_label}]"
        )

        for col, label in TESTS:
            y = _neg_log10(asset_df[col])
            ax.plot(
                asset_df["agg_level"],
                y,
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=label,
            )

        ax.axhline(
            threshold,
            color="red",
            linestyle="--",
            linewidth=1.0,
            label=f"α={alpha}  (threshold)",
        )
        ax.set_xlabel(r"Aggregation Level $\ell$")
        ax.set_ylabel(r"$-\log_{10}(p)$")
        # `predictability_k` is adaptive, so it drifts with ell as bit_count changes.
        # Showing it on the right axis avoids hiding that second moving part.
        ax2.step(
            asset_df["agg_level"],
            asset_df["predictability_k"],
            where="mid",
            color="#444444",
            linewidth=1.1,
            linestyle=":",
            alpha=0.75,
            label="Predictability k",
        )
        ax2.set_ylabel("Adaptive Predictability k", color="#444444")
        ax2.tick_params(axis="y", colors="#444444")
        k_min = int(asset_df["predictability_k"].min())
        k_max = int(asset_df["predictability_k"].max())
        ax2.set_ylim(k_min - 0.5, k_max + 0.5)
        ax.legend()
        ax.grid(True, alpha=0.3)
        lines_1, labels_1 = ax.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best")
        fig.tight_layout()

        by_asset_dir = output_dir.parent / "by_asset"
        by_asset_dir.mkdir(parents=True, exist_ok=True)
        out_path = by_asset_dir / f"{asset}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[plot] {out_path}")


def plot_per_test(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
    period_label: str,
) -> None:
    """One figure per test, all assets on the same axes (alternative view)."""
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]

    for col, label in TESTS:
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.suptitle(
            r"{} — $-\log_{{10}}(p)$ vs $\ell$".format(label)
            + f"  [offset = 0, period = {period_label}]"
        )

        for asset in assets:
            asset_df = df[(df["asset"] == asset) & df["valid"]].sort_values("agg_level")
            if asset_df.empty:
                continue
            y = _neg_log10(asset_df[col])
            ax.plot(
                asset_df["agg_level"],
                y,
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=asset,
                color=ASSET_COLORS.get(asset),
            )

        ax.axhline(
            threshold,
            color="red",
            linestyle="--",
            linewidth=1.0,
            label=r"$\alpha$" + f"={alpha}",
        )
        ax.set_xlabel(r"Aggregation Level $\ell$")
        ax.set_ylabel(r"$-\log_{10}(p)$")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        safe_label = label.lower().replace(" ", "_").replace(".", "")
        out_path = output_dir / f"{safe_label}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[plot] {out_path}")


def plot_predictability_k(
    df: pd.DataFrame,
    output_dir: Path,
    period_label: str,
) -> None:
    """Standalone overview of the adaptive predictability block length vs ell."""
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]
    ncols = 2
    nrows = int(np.ceil(len(assets) / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(10, max(4.6 * nrows, 6.5)),
        sharex=True,
        sharey=True,
    )
    axes_array = np.atleast_1d(axes).ravel()
    fig.suptitle(
        r"Adaptive Predictability $k$ vs $\ell$"
        + f"  [offset = 0, period = {period_label}]"
    )

    for ax, asset in zip(axes_array, assets):
        asset_df = df[(df["asset"] == asset) & df["valid"]].sort_values("agg_level")
        if asset_df.empty:
            ax.set_visible(False)
            continue
        ax.step(
            asset_df["agg_level"],
            asset_df["predictability_k"],
            where="mid",
            linewidth=1.8,
            color=ASSET_COLORS.get(asset),
        )
        ax.set_title(asset, fontsize=11)
        ax.set_xlabel(r"Aggregation Level $\ell$")
        ax.set_ylabel(r"Adaptive Predictability $k$")
        ax.tick_params(axis="x", labelbottom=True)
        ax.tick_params(axis="y", labelleft=True)
        ax.grid(True, alpha=0.3)

    for ax in axes_array[len(assets) :]:
        ax.set_visible(False)

    fig.tight_layout()

    out_path = output_dir / "predictability_k.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


def main() -> None:
    args = parse_args()
    summary_path = args.summary_dir / "summary_exp2_single_offset.csv"

    if not summary_path.exists():
        print(f"[error] summary file not found: {summary_path}")
        return

    df = pd.read_csv(summary_path)
    period_label = _extract_period_label(df, args.summary_dir)

    output_dir = args.output_dir if args.output_dir else args.summary_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_all_assets(df, output_dir, alpha=args.alpha, period_label=period_label)
    plot_per_asset(df, output_dir, alpha=args.alpha, period_label=period_label)
    plot_per_test(df, output_dir, alpha=args.alpha, period_label=period_label)
    plot_predictability_k(df, output_dir, period_label=period_label)

    print(f"[done] all plots saved to {output_dir}")


if __name__ == "__main__":
    main()
