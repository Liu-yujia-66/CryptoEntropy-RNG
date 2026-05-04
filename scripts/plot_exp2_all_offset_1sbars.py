from __future__ import annotations

"""
Plot pass-rate curves for Experiment 2, 1-second bars.

Reads `all_assets_summary_exp2_k_acceptance.csv` and produces a single
pass_rate_curves.png with one panel per statistical test, all assets overlaid.
No gate/reference distinction — every test is plotted equally.

Usage:
    python scripts/plot_exp2_all_offset_1sbars.py \
        --summary-dir "data/processed/experiment2/all-offset-per-month-1sbars(10,700,2)/1month-2025.01"
    
    扫某个目录下所有的：
    for d in "data/processed/experiment2/all-offset-per-month-1sbars(10,700,2)"/1month-*/; do
        echo "=== $d ==="
        python scripts/plot_exp2_all_offset_1sbars.py --summary-dir "$d"
    done

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

PASS_RATE_THRESHOLD = 0.80

TESTS = [
    ("predictability_pass_rate", "Predictability (adaptive k)", True),
    ("predictability_k2_pass_rate", "Predictability (k=2)", False),
    ("shannon_bias_pass_rate", "Shannon Bias", False),
    ("monobit_pass_rate", "Monobit", True),
    ("runs_pass_rate", "Runs", False),
    ("approximate_entropy_pass_rate", "Approx. Entropy (m=5)", False),
]

TEST_COLORS = {
    "predictability_pass_rate": "#1f77b4",
    "predictability_k2_pass_rate": "#17becf",
    "shannon_bias_pass_rate": "#9467bd",
    "monobit_pass_rate": "#ff7f0e",
    "runs_pass_rate": "#2ca02c",
    "approximate_entropy_pass_rate": "#d62728",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot 1s-bars pass-rate curves from k_acceptance CSV."
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        required=True,
        help="Directory containing all_assets_summary_exp2_k_acceptance.csv",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_acceptance(summary_dir: Path) -> pd.DataFrame:
    primary = summary_dir / "all_assets_summary_exp2_k_acceptance.csv"
    if primary.exists():
        return pd.read_csv(primary)

    frames: list[pd.DataFrame] = []
    per_asset = summary_dir / "by_asset"
    if per_asset.is_dir():
        for asset_dir in sorted(per_asset.iterdir()):
            if not asset_dir.is_dir():
                continue
            candidate = asset_dir / f"{asset_dir.name}_summary_exp2_k_acceptance.csv"
            if candidate.exists():
                frames.append(pd.read_csv(candidate))
    if not frames:
        raise FileNotFoundError(f"No k_acceptance CSV under {summary_dir}")
    return pd.concat(frames, ignore_index=True)


def _present_assets(df: pd.DataFrame) -> list[str]:
    return [a for a in ASSET_ORDER if a in df["asset"].values]


def _threshold(df: pd.DataFrame) -> float:
    if "pass_rate_threshold" in df.columns:
        vals = df["pass_rate_threshold"].dropna()
        if not vals.empty:
            return float(vals.iloc[0])
    return PASS_RATE_THRESHOLD


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------


def plot_pass_rate_curves(
    acceptance_df: pd.DataFrame,
    output_dir: Path,
    period_label: str = "",
) -> None:
    assets = _present_assets(acceptance_df)
    thr = _threshold(acceptance_df)

    # Filter to tests that exist in the data
    tests = [
        (col, label, in_acc)
        for col, label, in_acc in TESTS
        if col in acceptance_df.columns
    ]
    n_tests = len(tests)
    n_cols = 2
    n_rows = (n_tests + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(12, 4 * n_rows), sharex=True, sharey=True
    )
    fig.suptitle(
        r"Offset Pass Rate vs Aggregation Level $\ell$  (1s bars)"
        + (f"\n{period_label}" if period_label else ""),
        fontsize=13,
    )

    for ax, (col, label, in_acc) in zip(axes.flat, tests):
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

    for extra_ax in list(axes.flat)[n_tests:]:
        extra_ax.set_visible(False)

    for r in range(n_rows):
        axes[r, 0].set_ylabel("Pass Rate")
    for c in range(n_cols):
        for r in range(n_rows - 1, -1, -1):
            if axes[r, c].get_visible():
                axes[r, c].set_xlabel(r"Aggregation Level $\ell$")
                axes[r, c].tick_params(labelbottom=True)
                break

    handles, labels = axes[0, 0].get_legend_handles_labels()
    axes[0, 0].legend(handles, labels, fontsize=7, frameon=True, loc="lower right")

    fig.tight_layout()
    out_path = output_dir / "pass_rate_curves.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


# ---------------------------------------------------------------------------
# Per-asset panels
# ---------------------------------------------------------------------------


def plot_asset_panels(
    acceptance_df: pd.DataFrame,
    output_dir: Path,
    period_label: str = "",
) -> None:
    assets = _present_assets(acceptance_df)
    thr = _threshold(acceptance_df)

    ncols = 2
    nrows = int(np.ceil(len(assets) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4.5 * nrows))
    axes_flat = np.atleast_1d(axes).ravel()
    fig.suptitle(
        r"Per-Asset Pass-Rate Curves vs $\ell$  (1s bars)"
        + (f"\nPeriod: {period_label}" if period_label else ""),
        fontsize=13,
    )

    for ax, asset in zip(axes_flat, assets):
        adf = acceptance_df[acceptance_df["asset"] == asset].sort_values("agg_level")
        ax2 = ax.twinx()

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
        else:
            ax2.set_visible(False)

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
    out_path = output_dir / "asset_panels.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    summary_dir: Path = args.summary_dir
    acceptance_df = _load_acceptance(summary_dir)
    plot_pass_rate_curves(acceptance_df, summary_dir, period_label=summary_dir.name)
    plot_asset_panels(acceptance_df, summary_dir, period_label=summary_dir.name)


if __name__ == "__main__":
    main()
