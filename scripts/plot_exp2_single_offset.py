from __future__ import annotations

"""
Plot -log10(p-value) vs k for Experiment 2 single-offset results.

Shows how randomness emerges as the aggregation window k grows, with a
horizontal threshold line at -log10(alpha).

Default usage:
    python scripts/plot_exp2_single_offset.py --summary-dir data/processed/experiment2/single-offset-v2/full-2026.01-03

Or run automatically via exp2_single_offset_runner.py.
"""

import argparse
import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALPHA = 0.01
THRESHOLD = -np.log10(ALPHA)  # 2.0

ASSET_ORDER = ["BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT"]
ASSET_COLORS = {
    "BTCUSDT": "#F7931A",
    "ETHUSDT": "#627EEA",
    "BNBUSDT": "#F3BA2F",
    "SOLUSDT": "#9945FF",
    "DOGEUSDT": "#C2A633",
}

TESTS = [
    ("monobit_pvalue",               "Monobit"),
    ("runs_pvalue",                  "Runs"),
    ("approximate_entropy_pvalue",   "Approx. Entropy"),
    ("predictability_pvalue",        "Predictability"),
]

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def _neg_log10(p: pd.Series) -> pd.Series:
    """Convert p-values to -log10(p), clipping zeros to avoid inf."""
    clipped = p.clip(lower=1e-300)
    return -np.log10(clipped)


def plot_all_assets(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
) -> None:
    """One figure with 4 subplots (one per test), all assets overlaid."""
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]
    n_tests = len(TESTS)

    fig, axes = plt.subplots(
        1, n_tests, figsize=(5 * n_tests, 5), sharey=False
    )
    fig.suptitle("-log₁₀(p-value) vs Aggregation Window k  [offset=0]", fontsize=13)

    for ax, (col, label) in zip(axes, TESTS):
        for asset in assets:
            asset_df = df[df["asset"] == asset].sort_values("sampling_k")
            valid = asset_df[asset_df["valid"]]
            if valid.empty:
                continue
            y = _neg_log10(valid[col])
            ax.plot(
                valid["sampling_k"],
                y,
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=asset,
                color=ASSET_COLORS.get(asset),
            )

        ax.axhline(threshold, color="red", linestyle="--", linewidth=1.0,
                   label=f"α={alpha}")
        ax.set_title(label)
        ax.set_xlabel("k")
        ax.set_ylabel("-log₁₀(p-value)")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out_path = output_dir / "all_assets_neg_log_pvalue_vs_k.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out_path}")


def plot_per_asset(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
) -> None:
    """One figure per asset with all 4 tests on the same axes."""
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]

    for asset in assets:
        asset_df = df[(df["asset"] == asset) & df["valid"]].sort_values("sampling_k")
        if asset_df.empty:
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.suptitle(f"{asset} — -log₁₀(p-value) vs k  [offset=0]")

        for col, label in TESTS:
            y = _neg_log10(asset_df[col])
            ax.plot(asset_df["sampling_k"], y, marker="o", markersize=3,
                    linewidth=1.2, label=label)

        ax.axhline(threshold, color="red", linestyle="--", linewidth=1.0,
                   label=f"α={alpha}  (threshold)")
        ax.set_xlabel("k")
        ax.set_ylabel("-log₁₀(p-value)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        out_path = output_dir / f"{asset}_neg_log_pvalue_vs_k.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[plot] {out_path}")


def plot_per_test(
    df: pd.DataFrame,
    output_dir: Path,
    alpha: float,
) -> None:
    """One figure per test, all assets on the same axes (alternative view)."""
    threshold = -np.log10(alpha)
    assets = [a for a in ASSET_ORDER if a in df["asset"].unique()]

    for col, label in TESTS:
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.suptitle(f"{label} — -log₁₀(p-value) vs k  [offset=0]")

        for asset in assets:
            asset_df = df[(df["asset"] == asset) & df["valid"]].sort_values("sampling_k")
            if asset_df.empty:
                continue
            y = _neg_log10(asset_df[col])
            ax.plot(
                asset_df["sampling_k"], y,
                marker="o", markersize=3, linewidth=1.2,
                label=asset, color=ASSET_COLORS.get(asset),
            )

        ax.axhline(threshold, color="red", linestyle="--", linewidth=1.0,
                   label=f"α={alpha}  (threshold)")
        ax.set_xlabel("k")
        ax.set_ylabel("-log₁₀(p-value)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        safe_label = label.lower().replace(" ", "_").replace(".", "")
        out_path = output_dir / f"all_assets_{safe_label}_neg_log_pvalue_vs_k.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[plot] {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    summary_path = args.summary_dir / "summary_exp2_single_offset.csv"

    if not summary_path.exists():
        print(f"[error] summary file not found: {summary_path}")
        return

    df = pd.read_csv(summary_path)

    output_dir = args.output_dir if args.output_dir else args.summary_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_all_assets(df, output_dir, alpha=args.alpha)
    plot_per_asset(df, output_dir, alpha=args.alpha)
    plot_per_test(df, output_dir, alpha=args.alpha)

    print(f"[done] all plots saved to {output_dir}")


if __name__ == "__main__":
    main()
