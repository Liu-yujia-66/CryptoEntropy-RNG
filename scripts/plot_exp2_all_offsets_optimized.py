from __future__ import annotations

"""
Plot utilities for optimized Experiment 2 all-offset outputs.

Default usage:
    python scripts/plot_exp2_all_offsets_optimized.py
"""

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_HEATMAP_CMAP = "RdBu_r"
# DEFAULT_HEATMAP_CMAP = "icefire"
# DEFAULT_HEATMAP_CMAP = "YlGnBu"
# DEFAULT_HEATMAP_CMAP = "viridis"
# DEFAULT_HEATMAP_CMAP = "crest"
# DEFAULT_HEATMAP_CMAP = "RdYlGn"
# DEFAULT_HEATMAP_CMAP = "cividis"


DEFAULT_INPUT_ROOT = Path("data/processed/experiment2/all-offset-optimized")
DEFAULT_OUTPUT_DIRNAME = "plots"
DEFAULT_MAX_ROWS = None

# Fallback summary subdirectory used when --summary-dir is not passed.
# Only relevant for standalone CLI use; the runner always passes --summary-dir.
DEFAULT_FULL_DIRNAME = "full-2025.04-06"

ALPHA = 0.01
# ASSET_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
ASSET_ORDER = ["BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT"]

TEST_METRICS = [
    ("predictability_pass_rate", "predictability_pvalue", "Predictability"),
    ("monobit_pass_rate", "monobit_pvalue", "Monobit"),
    ("runs_pass_rate", "runs_pvalue", "Runs"),
    ("approximate_entropy_pass_rate", "approximate_entropy_pvalue", "Approx. Entropy"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot optimized Experiment 2 all-offset summaries."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root directory containing optimized all-offset summary outputs.",
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
    parser.add_argument(
        "--cmap",
        type=str,
        default=DEFAULT_HEATMAP_CMAP,
        help="Matplotlib colormap for acceptance heatmap (e.g. RdBu_r, YlGnBu, viridis).",
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=None,
        help="Directly specify the summary directory, bypassing --input-root resolution.",
    )
    return parser.parse_args()


def resolve_summary_dir(input_root: Path, max_rows: int | None) -> Path:
    return input_root / (
        f"rows{max_rows}" if max_rows is not None else DEFAULT_FULL_DIRNAME
    )


def _candidate_suffixes(suffix: str) -> list[str]:
    if suffix == "monthly":
        return ["monthly", "monthly_light"]
    return [suffix]


def load_summary_csv(summary_dir: Path, suffix: str) -> pd.DataFrame:
    """Load an all-assets summary CSV from summary_dir.

    Supports both the full monthly suffix and the optimized light monthly suffix.
    """
    for candidate_suffix in _candidate_suffixes(suffix):
        primary = summary_dir / f"all_assets_summary_exp2_{candidate_suffix}.csv"
        if primary.exists():
            return pd.read_csv(primary)

    per_asset_dir = summary_dir / "by_asset"
    frames: list[pd.DataFrame] = []
    if per_asset_dir.is_dir():
        for asset_dir in sorted(per_asset_dir.iterdir()):
            if not asset_dir.is_dir():
                continue
            asset = asset_dir.name
            for candidate_suffix in _candidate_suffixes(suffix):
                candidate = asset_dir / f"{asset}_summary_exp2_{candidate_suffix}.csv"
                if candidate.exists():
                    frames.append(pd.read_csv(candidate))
                    break

    if not frames:
        raise FileNotFoundError(
            f"No summary CSV found for suffix '{suffix}' under {summary_dir}"
        )
    return pd.concat(frames, ignore_index=True)


def save_plot(fig: Figure, path: Path, dpi: int = 300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _asset_palette(assets: list[str]) -> dict[str, tuple]:
    colors = sns.color_palette("tab10", n_colors=len(ASSET_ORDER))
    full_map = dict(zip(ASSET_ORDER, colors))
    return {a: full_map[a] for a in assets if a in full_map}


def _as_python_int(value: object) -> int:
    return int(np.asarray(value).item())


def _as_python_float(value: object) -> float:
    return float(np.asarray(value).item())


def plot_acceptance_heatmap(
    acceptance_df: pd.DataFrame,
    output_dir: Path,
    cmap: str = DEFAULT_HEATMAP_CMAP,
) -> None:
    present_assets = [a for a in ASSET_ORDER if a in acceptance_df["asset"].values]

    fig, axes = plt.subplots(2, 2, figsize=(16, 8.8), constrained_layout=True)
    fig.suptitle(
        "Pass Rate Across Offsets — Asset x Aggregation Level k",
        fontsize=13,
        linespacing=2,
    )

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
            cmap=cmap,
            annot=True,
            fmt=".2f",
            annot_kws={"size": 7},
            linewidths=0.5,
            cbar=False,
        )
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Aggregation Level k")
        ax.set_ylabel("Asset")
        ax.tick_params(axis="x", labelsize=8, rotation=45)
        ax.tick_params(axis="y", labelsize=9)

    norm = Normalize(vmin=0.0, vmax=1.0)
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(
        sm,
        ax=axes,
        orientation="horizontal",
        fraction=0.035,
        pad=0.04,
        aspect=55,
    )
    cbar.set_label("Pass Rate")

    save_plot(fig, output_dir / "acceptance_heatmap.png")
    print("[plot] acceptance_heatmap.png")


def plot_pvalue_distributions(combined_df: pd.DataFrame, output_dir: Path) -> None:
    present_assets = [a for a in ASSET_ORDER if a in combined_df["asset"].values]

    for _, pval_col, label in TEST_METRICS:
        if pval_col not in combined_df.columns:
            continue

        fig, axes = plt.subplots(
            1,
            len(present_assets),
            figsize=(4.5 * len(present_assets), 5.5),
            sharey=True,
        )
        if len(present_assets) == 1:
            axes = [axes]

        fig.suptitle(
            f"{label} p-value Distribution Across Offsets",
            fontsize=13,
        )

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
                label=f"alpha = {ALPHA}",
            )
            ax.set_title(asset, fontsize=10)
            ax.set_xlabel("k")
            ax.set_ylabel("p-value" if ax is axes[0] else "")
            ax.tick_params(axis="x", labelsize=8, rotation=60)

        axes[0].legend(frameon=True, fontsize=8)
        save_plot(fig, output_dir / f"pvalue_dist_{pval_col}.png")
        print(f"[plot] pvalue_dist_{pval_col}.png")


def plot_bits_per_second(
    acceptance_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    present_assets = [a for a in ASSET_ORDER if a in acceptance_df["asset"].values]
    palette = _asset_palette(present_assets)

    fig, ax = plt.subplots(figsize=(11, 6))

    for asset in present_assets:
        asset = str(asset)
        asset_df = acceptance_df[acceptance_df["asset"] == asset].sort_values(
            "sampling_k"
        )
        color = palette[asset]

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
            sel_k = _as_python_int(sel_row["selected_k"].iloc[0])
            match = asset_df[asset_df["sampling_k"] == sel_k]["avg_bits_per_second"]
            if not match.empty:
                ax.scatter(
                    sel_k,
                    _as_python_float(match.iloc[0]),
                    s=120,
                    color=color,
                    zorder=5,
                    marker="*",
                )

    ax.set_title(
        "Average Bit Rate vs Aggregation Level k  (* = selected k)",
        fontsize=12,
    )
    ax.set_xlabel("Aggregation Level k")
    ax.set_ylabel("Average Bits per Second")
    ax.tick_params(axis="x", labelsize=8)
    ax.legend(frameon=True)
    save_plot(fig, output_dir / "bits_per_second.png")
    print("[plot] bits_per_second.png")


def plot_selection_summary(selected_df: pd.DataFrame, output_dir: Path) -> None:
    # Include all assets present in selected_df, ordered by ASSET_ORDER.
    all_assets = [a for a in ASSET_ORDER if a in selected_df["asset"].values]
    if not all_assets:
        return

    df = selected_df.set_index("asset").reindex(all_assets).reset_index()

    palette_map = _asset_palette(all_assets)
    y_pos = np.arange(len(df))

    fig, (ax_k, ax_bps) = plt.subplots(
        1,
        2,
        figsize=(12, max(4.8, 1.0 * len(all_assets))),
        sharey=True,
        gridspec_kw={"width_ratios": [1.15, 1]},
    )
    fig.suptitle(
        "Experiment 2: Selected k and Corresponding Bit Rate per Asset",
        fontsize=13,
    )

    for y, row in zip(y_pos, df.itertuples()):
        asset = str(row.asset)
        color = palette_map[asset]
        has_k = not pd.isna(row.selected_k)

        if has_k:
            k_val = _as_python_int(row.selected_k)
            ax_k.scatter(k_val, y, s=95, c=[color], zorder=3)
            ax_k.hlines(y, xmin=0, xmax=k_val, colors=[color], linewidth=1.8)
            ax_k.annotate(
                f"{k_val}",
                xy=(k_val, y),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
            )
            if "avg_bits_per_second" in df.columns and not pd.isna(
                row.avg_bits_per_second
            ):
                bps = _as_python_float(row.avg_bits_per_second)
                ax_bps.scatter(bps, y, s=95, c=[color], zorder=3)
                ax_bps.hlines(y, xmin=0, xmax=bps, colors=[color], linewidth=1.8)
                ax_bps.annotate(
                    f"{bps:.4f}",
                    xy=(bps, y),
                    xytext=(6, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                )
        else:
            # No acceptable k found — show a grey "N/A" marker on both panels.
            for ax in (ax_k, ax_bps):
                ax.scatter(0, y, s=60, c=["#cccccc"], zorder=3, marker="x")
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

    ax_k.set_xlabel("Selected k")
    ax_k.set_title("Selected Aggregation Level k")
    ax_k.set_yticks(y_pos)
    ax_k.set_yticklabels(df["asset"])
    ax_k.set_xlim(left=0)
    ax_k.grid(axis="x", alpha=0.25, linewidth=0.8)
    ax_k.invert_yaxis()

    ax_bps.set_xlabel("Average Bits per Second")
    ax_bps.set_title("Bit Rate at Selected k")
    ax_bps.set_xlim(left=0)
    ax_bps.grid(axis="x", alpha=0.25, linewidth=0.8)
    ax_bps.tick_params(axis="y", left=False, labelleft=False)

    save_plot(fig, output_dir / "selection_summary.png")
    print("[plot] selection_summary.png")


def main() -> None:
    args = parse_args()
    sns.set_theme(style=args.style)

    summary_dir = (
        args.summary_dir
        if args.summary_dir is not None
        else resolve_summary_dir(args.input_root, args.max_rows)
    )
    output_dir = summary_dir / DEFAULT_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    acceptance_df = load_summary_csv(summary_dir, "k_acceptance")
    combined_df = load_summary_csv(summary_dir, "offset_stats")
    selected_df = load_summary_csv(summary_dir, "selected_k")

    plot_acceptance_heatmap(acceptance_df, output_dir, cmap=args.cmap)
    plot_pvalue_distributions(combined_df, output_dir)
    plot_bits_per_second(acceptance_df, selected_df, output_dir)
    plot_selection_summary(selected_df, output_dir)


if __name__ == "__main__":
    main()
