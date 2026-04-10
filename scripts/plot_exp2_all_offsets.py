from __future__ import annotations

"""
Plot utilities for Experiment 2 all-offset outputs.

Default usage:
    python scripts/plot_exp2_all_offsets.py
"""

import argparse
from pathlib import Path

import matplotlib
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_INPUT_ROOT = Path("data/processed/experiment2/all-offset")
DEFAULT_OUTPUT_DIRNAME = "plots"
DEFAULT_MAX_ROWS = None
# DEFAULT_MAX_ROWS = 100_000

ALPHA = 0.01
ASSET_ORDER = ["BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT"]

# (pass_rate_col, pvalue_col, display_label)
TEST_METRICS = [
    ("predictability_pass_rate", "predictability_pvalue", "Predictability"),
    ("monobit_pass_rate", "monobit_pvalue", "Monobit"),
    ("runs_pass_rate", "runs_pvalue", "Runs"),
    ("approximate_entropy_pass_rate", "approximate_entropy_pvalue", "Approx. Entropy"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot Experiment 2 all-offset summaries."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root directory containing all-offset summary outputs.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help="Optional row cap label used by the experiment outputs.",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="whitegrid",
        help="Seaborn style name.",
    )
    return parser.parse_args()


def resolve_summary_dir(input_root: Path, max_rows: int | None) -> Path:
    return input_root / (f"rows{max_rows}" if max_rows is not None else "full")


def load_summary_csv(summary_dir: Path, suffix: str) -> pd.DataFrame:
    """Load the all-assets summary CSV from summary_dir.

    Primary:  summary_dir/all_assets_summary_exp2_all_offsets_<suffix>.csv
    Fallback: concatenate per-asset subdirectory files.
    """
    primary = summary_dir / f"all_assets_summary_exp2_all_offsets_{suffix}.csv"
    if primary.exists():
        return pd.read_csv(primary)

    # fallback: load per-asset files from summary/ subdirectory and concatenate
    per_asset_dir = summary_dir / "by_asset"
    frames: list[pd.DataFrame] = []
    if per_asset_dir.is_dir():
        for asset_dir in sorted(per_asset_dir.iterdir()):
            if not asset_dir.is_dir():
                continue
            asset = asset_dir.name
            candidate = asset_dir / f"{asset}_summary_exp2_all_offsets_{suffix}.csv"
            if candidate.exists():
                frames.append(pd.read_csv(candidate))
    if not frames:
        raise FileNotFoundError(
            f"No summary CSV found for suffix '{suffix}' under {summary_dir}"
        )
    return pd.concat(frames, ignore_index=True)


def save_plot(fig: Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _asset_palette(assets: list[str]) -> dict[str, tuple]:
    colors = sns.color_palette("tab10", n_colors=len(ASSET_ORDER))
    full_map = dict(zip(ASSET_ORDER, colors))
    return {a: full_map[a] for a in assets if a in full_map}


def plot_acceptance_heatmap(acceptance_df: pd.DataFrame, output_dir: Path) -> None:
    """2×2 heatmap grid: one panel per test, rows=asset, cols=k, color=pass rate."""
    present_assets = [a for a in ASSET_ORDER if a in acceptance_df["asset"].values]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle("Pass Rate Across Offsets — Asset × Aggregation Level k", fontsize=13)

    for ax, (pass_col, _, label) in zip(axes.flat, TEST_METRICS):
        if pass_col not in acceptance_df.columns:
            ax.set_visible(False)
            continue

        pivot = acceptance_df.pivot(
            index="asset", columns="sampling_k", values=pass_col
        ).reindex([a for a in present_assets if a in acceptance_df["asset"].values])

        sns.heatmap(
            pivot,
            ax=ax,
            vmin=0.0,
            vmax=1.0,
            cmap="RdYlGn",
            annot=True,
            fmt=".2f",
            linewidths=0.5,
            cbar_kws={"shrink": 0.8, "label": "Pass Rate"},
        )
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Aggregation Level k")
        ax.set_ylabel("Asset")

    save_plot(fig, output_dir / "acceptance_heatmap.png")
    print(f"[plot] acceptance_heatmap.png")


def plot_pvalue_distributions(combined_df: pd.DataFrame, output_dir: Path) -> None:
    """One figure per test: 5 subplots (one per asset), boxplots of p-values across
    offsets vs k, with alpha threshold line."""
    present_assets = [a for a in ASSET_ORDER if a in combined_df["asset"].values]

    for _, pval_col, label in TEST_METRICS:
        if pval_col not in combined_df.columns:
            continue

        fig, axes = plt.subplots(
            1,
            len(present_assets),
            figsize=(4 * len(present_assets), 5),
            sharey=True,
        )
        if len(present_assets) == 1:
            axes = [axes]

        fig.suptitle(f"{label} p-value Distribution Across Offsets", fontsize=13)

        for ax, asset in zip(axes, present_assets):
            asset_df = combined_df[combined_df["asset"] == asset].copy()
            asset_df["sampling_k"] = asset_df["sampling_k"].astype(str)

            sns.boxplot(
                data=asset_df,
                x="sampling_k",
                y=pval_col,
                ax=ax,
                color="#7bbfde",
                flierprops={"marker": ".", "markersize": 2, "alpha": 0.4},
            )
            ax.axhline(
                ALPHA,
                color="#cc3333",
                linestyle="--",
                linewidth=1.2,
                label=f"α = {ALPHA}",
            )
            ax.set_title(asset, fontsize=10)
            ax.set_xlabel("k")
            ax.set_ylabel("p-value" if ax is axes[0] else "")
            ax.tick_params(axis="x", labelsize=8)

        axes[0].legend(frameon=True, fontsize=8)
        save_plot(fig, output_dir / f"pvalue_dist_{pval_col}.png")
        print(f"[plot] pvalue_dist_{pval_col}.png")


def plot_bits_per_second(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Line plot of avg bits/s vs k for all assets; selected k marked with ★."""
    present_assets = [a for a in ASSET_ORDER if a in acceptance_df["asset"].values]
    palette = _asset_palette(present_assets)

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for asset in present_assets:
        asset_df = acceptance_df[acceptance_df["asset"] == asset].sort_values(
            "sampling_k"
        )
        color = palette.get(asset, "gray")

        ax.plot(
            asset_df["sampling_k"],
            asset_df["avg_bits_per_second"],
            marker="o",
            linewidth=1.8,
            label=asset,
            color=color,
        )

        sel_row = selected_df[selected_df["asset"] == asset]
        if not sel_row.empty and not pd.isna(sel_row["selected_k"].iloc[0]):
            sel_k = int(sel_row["selected_k"].iloc[0])
            match = asset_df[asset_df["sampling_k"] == sel_k]["avg_bits_per_second"]
            if not match.empty:
                ax.scatter(
                    sel_k, match.iloc[0], s=120, color=color, zorder=5, marker="*"
                )

    ax.set_title(
        "Average Bit Rate vs Aggregation Level k  (★ = selected k)", fontsize=12
    )
    ax.set_xlabel("Aggregation Level k")
    ax.set_ylabel("Average Bits per Second")
    ax.legend(frameon=True)
    save_plot(fig, output_dir / "bits_per_second.png")
    print("[plot] bits_per_second.png")


def plot_selection_summary(selected_df: pd.DataFrame, output_dir: Path) -> None:
    """Two-panel horizontal bar chart: selected k (left) and bits/s at selected k (right)."""
    clean = selected_df.dropna(subset=["selected_k"]).copy()
    if clean.empty:
        return

    clean["selected_k"] = clean["selected_k"].astype(int)
    clean = (
        clean.set_index("asset")
        .reindex([a for a in ASSET_ORDER if a in clean["asset"].values])
        .reset_index()
    )

    present_assets = clean["asset"].tolist()
    palette = list(_asset_palette(present_assets).values())

    fig, (ax_k, ax_bps) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        "Experiment 2: Selected k and Corresponding Bit Rate per Asset", fontsize=13
    )

    bars_k = ax_k.barh(clean["asset"], clean["selected_k"], color=palette)
    ax_k.set_xlabel("Selected k")
    ax_k.set_title("Selected Aggregation Level k")
    ax_k.bar_label(bars_k, padding=4, fmt="%d")
    ax_k.invert_yaxis()

    bars_bps = ax_bps.barh(clean["asset"], clean["avg_bits_per_second"], color=palette)
    ax_bps.set_xlabel("Bits per Second")
    ax_bps.set_title("Bit Rate at Selected k")
    ax_bps.bar_label(bars_bps, padding=4, fmt="%.4f")
    ax_bps.invert_yaxis()

    save_plot(fig, output_dir / "selection_summary.png")
    print("[plot] selection_summary.png")


def main() -> None:
    args = parse_args()
    sns.set_theme(style=args.style)

    summary_dir = resolve_summary_dir(args.input_root, args.max_rows)
    output_dir = summary_dir / DEFAULT_OUTPUT_DIRNAME

    acceptance_df = load_summary_csv(summary_dir, "k_acceptance")
    selected_df = load_summary_csv(summary_dir, "selected_k")
    combined_df = load_summary_csv(summary_dir, "combined")

    plot_acceptance_heatmap(acceptance_df, output_dir)
    plot_pvalue_distributions(combined_df, output_dir)
    plot_bits_per_second(acceptance_df, selected_df, output_dir)
    plot_selection_summary(selected_df, output_dir)

    print(f"[done] saved plots under {output_dir}")


if __name__ == "__main__":
    main()
