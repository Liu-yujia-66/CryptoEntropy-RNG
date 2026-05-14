from __future__ import annotations

"""
Experiment 1 baseline plotter.

Reads the per-(asset, month) summary CSV produced by
`scripts/runner_exp1_baseline.py` and produces:

  - per_asset_summary.csv      : 5-row aggregation matching thesis Table 4.2
                                 (bps median, 1-H max, ρ₁ median, Monobit
                                 rejects k/N, Runs rejects k/N, L_max max)
  - per_asset_summary.md       : same content as a markdown table for
                                 thesis paste-in
  - per_asset_distributions.png: 4-panel diagnostic
                                 (bps box, ρ₁ box, Monobit −log10 p ECDF,
                                 L_max histogram), one colour per asset

Invoked by the runner via run_plot_subprocess; can also be run standalone:
    python scripts/plot_exp1_baseline.py --summary-dir data/processed/experiment1
"""

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

from src.utils import ASSET_COLORS, ASSET_ORDER


ALPHA = 0.01

DISPLAY_NAMES = {
    "BNBUSDT": "BNB",
    "BTCUSDT": "BTC",
    "DOGEUSDT": "DOGE",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
}


def _per_asset_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-(asset, month) rows into the per-asset summary table."""
    rows: list[dict[str, object]] = []
    grouped = df.groupby("asset", sort=False)
    for asset, group in grouped:
        n = len(group)
        l_max_max = int(
            np.nanmax(
                np.concatenate(
                    [
                        group["longest_run_0"].to_numpy(),
                        group["longest_run_1"].to_numpy(),
                    ]
                )
            )
        )
        rows.append(
            {
                "asset": DISPLAY_NAMES.get(asset, asset),
                "n_months": n,
                "bps_median": float(group["bits_per_second"].median()),
                "shannon_bias_max": float(group["shannon_bias"].max()),
                "lag1_median": float(group["lag1_autocorrelation"].median()),
                "monobit_rejects": int((group["monobit_pvalue"] < ALPHA).sum()),
                "runs_rejects": int((group["runs_pvalue"] < ALPHA).sum()),
                "apen_rejects": int(
                    (group["approximate_entropy_pvalue"] < ALPHA).sum()
                ),
                "predictability_rejects": int(
                    (group["predictability_pvalue"] < ALPHA).sum()
                ),
                "predictability_k2_rejects": int(
                    (group["predictability_k2_pvalue"] < ALPHA).sum()
                ),
                "longest_run_max": l_max_max,
            }
        )

    out = pd.DataFrame(rows)
    asset_rank = {DISPLAY_NAMES.get(a, a): i for i, a in enumerate(ASSET_ORDER)}
    out = out.sort_values(
        "asset", key=lambda s: s.map(asset_rank).fillna(len(ASSET_ORDER))
    )
    return out.reset_index(drop=True)


def _summary_to_markdown(summary: pd.DataFrame) -> str:
    """Render the per-asset summary as a markdown table matching thesis Table 4.2."""
    headers = [
        "Asset",
        "bps median",
        "1−H max",
        "ρ₁ median",
        "Monobit rejects",
        "Runs rejects",
        "ApEn rejects",
        "D rejects",
        "D(k=2) rejects",
        "L_max max",
    ]
    align = ["l", "r", "r", "r", "c", "c", "c", "c", "c", "r"]

    def fmt_row(r: pd.Series) -> list[str]:
        return [
            str(r["asset"]),
            f"{r['bps_median']:.2f}",
            f"{r['shannon_bias_max']:.2e}",
            f"{r['lag1_median']:+.3f}",
            f"{r['monobit_rejects']}/{r['n_months']}",
            f"{r['runs_rejects']}/{r['n_months']}",
            f"{r['apen_rejects']}/{r['n_months']}",
            f"{r['predictability_rejects']}/{r['n_months']}",
            f"{r['predictability_k2_rejects']}/{r['n_months']}",
            f"{r['longest_run_max']}",
        ]

    body = [fmt_row(r) for _, r in summary.iterrows()]

    sep_map = {"l": ":---", "r": "---:", "c": ":---:"}
    sep = [sep_map[a] for a in align]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(sep) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _plot_distributions(df: pd.DataFrame, output_path: Path) -> None:
    """Four-panel asset-level distribution view."""
    asset_rank = {a: i for i, a in enumerate(ASSET_ORDER)}
    assets = sorted(df["asset"].unique(), key=lambda a: asset_rank.get(a, len(ASSET_ORDER)))

    bps_data = [df.loc[df["asset"] == a, "bits_per_second"].to_numpy() for a in assets]
    rho_data = [df.loc[df["asset"] == a, "lag1_autocorrelation"].to_numpy() for a in assets]
    l_max_data = [
        np.maximum(
            df.loc[df["asset"] == a, "longest_run_0"].to_numpy(),
            df.loc[df["asset"] == a, "longest_run_1"].to_numpy(),
        )
        for a in assets
    ]

    labels = [DISPLAY_NAMES.get(a, a) for a in assets]
    colors = [ASSET_COLORS.get(a, "#444444") for a in assets]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Experiment 1 baseline — per-(asset, month) distributions")

    # bps boxplot
    ax = axes[0, 0]
    bp = ax.boxplot(bps_data, tick_labels=labels, patch_artist=True)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.set_title("bits per second")
    ax.set_ylabel("bps")
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # ρ₁ boxplot
    ax = axes[0, 1]
    bp = ax.boxplot(rho_data, tick_labels=labels, patch_artist=True)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.axhline(0.0, color="gray", linewidth=0.7)
    ax.set_title("lag-1 autocorrelation $\\rho_1$")
    ax.set_ylabel("$\\rho_1$")
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # Monobit −log10 p ECDF
    ax = axes[1, 0]
    for a, c, label in zip(assets, colors, labels):
        p = df.loc[df["asset"] == a, "monobit_pvalue"].to_numpy()
        # clip to avoid log(0); double-precision floor ~2.2e-308
        p = np.clip(p, 1e-308, 1.0)
        x = np.sort(-np.log10(p))
        y = np.arange(1, x.size + 1) / x.size
        ax.step(x, y, where="post", color=c, label=label, linewidth=1.5)
    ax.axvline(-np.log10(ALPHA), color="red", linestyle="--", linewidth=0.7,
               label=f"$-\\log_{{10}}\\alpha$ = {-np.log10(ALPHA):.0f}")
    ax.set_xscale("log")
    ax.set_title("Monobit $-\\log_{10}(p)$ ECDF")
    ax.set_xlabel("$-\\log_{10}(p)$")
    ax.set_ylabel("ECDF")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(linestyle=":", alpha=0.5)

    # L_max histogram (per-asset overlay)
    ax = axes[1, 1]
    all_lmax = np.concatenate(l_max_data) if l_max_data else np.array([])
    if all_lmax.size:
        bins = np.linspace(all_lmax.min(), all_lmax.max(), 30)
    else:
        bins = 30
    for data, c, label in zip(l_max_data, colors, labels):
        ax.hist(data, bins=bins, alpha=0.5, color=c, label=label)
    ax.set_title("$L_{\\max}$ per (asset, month)")
    ax.set_xlabel("$L_{\\max}$ = max(0-run, 1-run)")
    ax.set_ylabel("count")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the per-asset Exp 1 summary from the per-month CSV."
    )
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=Path("data/processed/experiment1"),
        help="Directory containing all_assets_summary_exp1_baseline.csv.",
    )
    args = parser.parse_args()

    csv_path = args.summary_dir / "all_assets_summary_exp1_baseline.csv"
    if not csv_path.exists():
        print(f"[error] summary CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path)
    summary = _per_asset_summary(df)

    summary_csv = args.summary_dir / "per_asset_summary.csv"
    summary.to_csv(summary_csv, index=False)
    print(f"[saved] {summary_csv}")

    summary_md = args.summary_dir / "per_asset_summary.md"
    summary_md.write_text(_summary_to_markdown(summary) + "\n", encoding="utf-8")
    print(f"[saved] {summary_md}")

    plot_path = args.summary_dir / "per_asset_distributions.png"
    _plot_distributions(df, plot_path)
    print(f"[saved] {plot_path}")


if __name__ == "__main__":
    main()
