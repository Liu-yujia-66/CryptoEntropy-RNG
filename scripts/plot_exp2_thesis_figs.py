from __future__ import annotations

"""
Thesis figures for Experiment 2 (§4.3).

Following the supervisor conversation (L293) and the layout used by Onofri
et al. (2025) [paper 7], each figure is a "small-multiples" grid:

    rows = assets, cols = months in the quarter.

Each cell is an independent panel — no asset overlay. Within a single cell,
the two test statistics (D adaptive k, Monobit) are drawn with column-specific
    colours. The relaxed-criterion figure shows a single joint statistic (n_pass) per
cell instead.

Figures 4.2, 4.3, and 4.5 produce two figures — one per quarter — for the
year-over-year comparison. Figure 4.4 combines both quarters into one 2×3
figure:

    Q1  →  2025-01, 2025-02, 2025-03
    Q5  →  2026-01, 2026-02, 2026-03  (15 months later)

Full 15-month selected-ℓ* detail is reported in the thesis appendix tables.

Outputs land in thesis/figures/.  Naming convention:
  Fig 4.2a / 4.2b — exp2_fig_4_2{a,b}_single_offset_q{1,5}.png
  Fig 4.3a / 4.3b — exp2_fig_4_3{a,b}_all_offset_strict_q{1,5}.png
  Fig 4.4          — exp2_fig_4_4_all_offset_relaxed.png
  Fig 4.5a / 4.5b — exp2_fig_4_5{a,b}_1sbars_q{1,5}.png

Usage:
    python scripts/plot_exp2_thesis_figs.py
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
from matplotlib.artist import Artist
from matplotlib.offsetbox import AnchoredOffsetbox, VPacker, TextArea

from src.utils import ASSET_COLORS  # kept for Fig 4.4 (single-test relaxed criterion)

# (D-colour, Monobit-colour) pairs per column for Fig 4.2 / 4.3 / 4.5.
# Each month column uses its own contrasting pair; both lines are solid.
# Three pairs cover a 3-month quarter; extend if more columns are needed.
COLUMN_TEST_COLOR_PAIRS = [
    ("#3498db", "#ff7f0e"),  # col 0  — sky blue   / orange
    ("#d62728", "#2ca02c"),  # col 1  — red        / green
    ("#7b1fa2", "#fbc02d"),  # col 2  — deep purple / amber
    ("#17becf", "#bcbd22"),  # col 3  — cyan       / olive   (fallback)
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALPHA = 0.01
NEG_LOG_ALPHA = -np.log10(ALPHA)
PASS_RATE_THRESHOLD = 0.80
RELAXED_F = 3
RELAXED_F_FRACTION = 0.03

DEFAULT_PROCESSED_ROOT = Path("data/processed/experiment2")
DEFAULT_OUTPUT_DIR = Path("thesis/figures")

DEFAULT_Q1_MONTHS = ["2025-01", "2025-02", "2025-03"]
DEFAULT_Q5_MONTHS = ["2026-01", "2026-02", "2026-03"]
Q1_LABEL = "2025 Q1"
Q5_LABEL = "2026 Q1 (Q5)"

DISPLAY_NAMES = {
    "BNBUSDT": "BNB",
    "BTCUSDT": "BTC",
    "DOGEUSDT": "DOGE",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
}

# Asset draw order (descending transaction-time activity).
ASSET_ROW_ORDER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

RUN_SINGLE = "single-offset-per-month(50,2000,25)"
RUN_STRICT = "all-offset-per-month(50,2000,25)"
RUN_RELAXED = "relaxed-all-offset-per-month(3,0.03)-(10,2000,2)"
RUN_1SBARS = "all-offset-per-month-1sbars(10,600,1)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_dir(month: str) -> str:
    """Convert YYYY-MM (CLI form) to 1month-YYYY.MM (directory form)."""
    if "." in month:
        return f"1month-{month}"
    return f"1month-{month.replace('-', '.')}"


def _load_month(
    processed_root: Path, run_dir: str, month: str, csv_name: str
) -> pd.DataFrame:
    csv_path = processed_root / run_dir / _month_dir(month) / csv_name
    if not csv_path.exists():
        raise FileNotFoundError(f"missing CSV: {csv_path}")
    return pd.read_csv(csv_path)


def _safe_neg_log10(p: np.ndarray) -> np.ndarray:
    return -np.log10(np.clip(p, 1e-300, 1.0))


# ---------------------------------------------------------------------------
# Curve drawing — one curve per (asset, month, test); no asset overlay
# ---------------------------------------------------------------------------


def _smooth_subsample(
    x: np.ndarray, y: np.ndarray, rolling_window: int = 1, plot_step: int = 1
) -> tuple[np.ndarray, np.ndarray]:
    if rolling_window > 1 and y.size >= rolling_window:
        y = (
            pd.Series(y)
            .rolling(rolling_window, center=True, min_periods=1)
            .mean()
            .to_numpy()
        )
    if plot_step > 1:
        x = x[::plot_step]
        y = y[::plot_step]
    return x, y


def _draw_two_tests_cell(
    ax,
    df: pd.DataFrame,
    asset: str,
    col_d: str,
    col_mono: str,
    col_idx: int = 0,
    transform=None,
    plot_step: int = 1,
    rolling_window: int = 1,
) -> None:
    """One asset × one month → D + Monobit, both solid, column-specific colours.

    Each column (month) uses its own colour pair from COLUMN_TEST_COLOR_PAIRS
    so the months are visually distinct.
    """
    sub = df[df["asset"] == asset].sort_values("agg_level")
    if sub.empty:
        return
    x = sub["agg_level"].to_numpy()
    y_d = sub[col_d].to_numpy()
    y_mono = sub[col_mono].to_numpy()
    if transform is not None:
        y_d = transform(y_d)
        y_mono = transform(y_mono)

    xd, y_d = _smooth_subsample(x, y_d, rolling_window, plot_step)
    xm, y_mono = _smooth_subsample(x, y_mono, rolling_window, plot_step)

    d_color, mono_color = COLUMN_TEST_COLOR_PAIRS[
        col_idx % len(COLUMN_TEST_COLOR_PAIRS)
    ]
    ax.plot(xd, y_d, color=d_color, linewidth=1.4, linestyle="-", label=r"$D$")
    ax.plot(xm, y_mono, color=mono_color, linewidth=1.4, linestyle="-", label="Monobit")


# ---------------------------------------------------------------------------
# Common 5×N grid scaffolding (rows = assets, cols = months in a quarter)
# ---------------------------------------------------------------------------


def _setup_grid(months: list[str], figsize=None):
    n_cols = len(months)
    if figsize is None:
        figsize = (3 * n_cols + 1.5, 12)
    fig, axes = plt.subplots(
        5, n_cols, figsize=figsize, sharex="col", sharey=True, squeeze=False
    )
    return fig, axes


def _label_grid(axes, months: list[str], ylabel_left: str, xlabel: str) -> None:
    """Add row labels (asset), col headers (month), shared axis labels."""
    for col, month in enumerate(months):
        axes[0, col].set_title(month, fontsize=11)
    for row, asset in enumerate(ASSET_ROW_ORDER):
        axes[row, 0].set_ylabel(
            DISPLAY_NAMES.get(asset, asset) + "\n" + ylabel_left,
            fontsize=10,
        )
    for col in range(axes.shape[1]):
        axes[4, col].set_xlabel(xlabel, fontsize=10)


# ---------------------------------------------------------------------------
# Figure 4.2 — Single offset (5×N small-multiples)
# ---------------------------------------------------------------------------


def plot_fig_4_2(
    processed_root: Path, months: list[str], quarter_label: str, output_path: Path
) -> None:
    """5×N small-multiples for Single-offset over one quarter."""
    dfs = []
    for m in months:
        df = _load_month(
            processed_root, RUN_SINGLE, m, "summary_exp2_single_offset.csv"
        )
        if "valid" in df.columns:
            df = df[df["valid"].astype(bool)]
        dfs.append(df)

    fig, axes = _setup_grid(months)
    for row, asset in enumerate(ASSET_ROW_ORDER):
        for col, df in enumerate(dfs):
            ax = axes[row, col]
            _draw_two_tests_cell(
                ax,
                df,
                asset,
                col_d="predictability_pvalue",
                col_mono="monobit_pvalue",
                col_idx=col,
                transform=_safe_neg_log10,
            )
            ax.axhline(NEG_LOG_ALPHA, color="red", linestyle=":", linewidth=0.8)
            ax.grid(linestyle=":", alpha=0.4)
            ax.set_ylim(-1, 10)

    _label_grid(axes, months, ylabel_left=r"$-\log_{10}(p)$", xlabel=r"$\ell$ (trades)")

    # Per-column D / Monobit legend on the top row (colours vary by column).
    for col in range(axes.shape[1]):
        axes[0, col].legend(loc="upper right", fontsize=7, framealpha=0.85)

    fig.suptitle(
        f"Experiment 2 · Single-offset · {quarter_label}\n"
        "(rows = assets; $D$ and Monobit solid, colour pair per column; "
        "red dotted = $-\\log_{10}\\alpha$)",
        fontsize=11,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"[saved] {output_path}")


# ---------------------------------------------------------------------------
# Figures 4.3 / 4.5 — Pass-rate (2×2)
# ---------------------------------------------------------------------------


def plot_pass_rate_figure(
    processed_root: Path,
    run_dir: str,
    csv_name: str,
    months: list[str],
    quarter_label: str,
    output_path: Path,
    fig_title: str,
    xlabel: str,
    plot_step: int = 1,
    rolling_window: int = 1,
) -> None:
    """5×N small-multiples for an all-offset pass-rate run over one quarter."""
    dfs = [_load_month(processed_root, run_dir, m, csv_name) for m in months]

    fig, axes = _setup_grid(months)
    for row, asset in enumerate(ASSET_ROW_ORDER):
        for col, df in enumerate(dfs):
            ax = axes[row, col]
            _draw_two_tests_cell(
                ax,
                df,
                asset,
                col_d="predictability_pass_rate",
                col_mono="monobit_pass_rate",
                col_idx=col,
                plot_step=plot_step,
                rolling_window=rolling_window,
            )
            ax.axhline(PASS_RATE_THRESHOLD, color="red", linestyle=":", linewidth=0.8)
            ax.grid(linestyle=":", alpha=0.4)
            ax.set_ylim(-0.05, 1.05)

    _label_grid(axes, months, ylabel_left="pass rate", xlabel=xlabel)
    # Per-column D / Monobit legend on the top row (colours vary by column).
    for col in range(axes.shape[1]):
        axes[0, col].legend(loc="lower right", fontsize=7, framealpha=0.85)

    fig.suptitle(
        f"{fig_title} · {quarter_label}\n"
        "(rows = assets; $D$ and Monobit solid, colour pair per column; "
        "red dotted = 0.80 threshold)",
        fontsize=11,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"[saved] {output_path}")


# ---------------------------------------------------------------------------
# Figure 4.4 — Relaxed (2×N combined)
# ---------------------------------------------------------------------------


def _draw_relaxed_panel(
    ax,
    df: pd.DataFrame,
    ell_range: np.ndarray,
    threshold: np.ndarray,
    threshold_label: str,
    show_threshold_legend: bool,
) -> None:
    """Draw n_pass(ℓ) curves + stars + ℓ\\* summary box for one month panel."""
    for asset in ASSET_ROW_ORDER:
        sub = df[df["asset"] == asset].sort_values("agg_level")
        if sub.empty:
            continue
        x = sub["agg_level"].to_numpy()
        y = sub["num_offsets_passing_both"].to_numpy()
        ax.plot(x, y, color=ASSET_COLORS[asset], linewidth=1.3)

    ell_star_lines: list[tuple[str, str, str]] = []
    for asset in ASSET_ROW_ORDER:
        sub = df[df["asset"] == asset].sort_values("agg_level")
        accepted = (
            sub[sub["is_acceptable_relaxed"].astype(bool)] if not sub.empty else sub
        )
        if accepted is not None and not accepted.empty:
            ell_star = int(accepted["agg_level"].iloc[0])
            n_star = int(accepted["num_offsets_passing_both"].iloc[0])
            ax.plot(
                ell_star,
                n_star,
                marker="*",
                color=ASSET_COLORS[asset],
                markersize=14,
                markeredgecolor="black",
                markeredgewidth=0.5,
                linestyle="none",
            )
            ell_star_lines.append(
                (DISPLAY_NAMES.get(asset, asset), str(ell_star), ASSET_COLORS[asset])
            )
        else:
            ell_star_lines.append(
                (DISPLAY_NAMES.get(asset, asset), "—", ASSET_COLORS[asset])
            )

    # Single anchored box (one outline, multiple colour-coded lines inside).
    rows: list[Artist] = [
        TextArea(
            r"selected $\ell^*$:",
            textprops=dict(fontsize=11, color="black", family="monospace"),
        )
    ]
    for name, val, color in ell_star_lines:
        rows.append(
            TextArea(
                f"  {name:<5} = {val}",
                textprops=dict(fontsize=11, color=color, family="monospace"),
            )
        )
    box = VPacker(children=rows, align="left", pad=0, sep=2)
    anchored = AnchoredOffsetbox(
        loc="upper left",
        child=box,
        pad=0.4,
        borderpad=0.4,
        frameon=True,
    )
    anchored.patch.set_edgecolor("0.7")
    anchored.patch.set_facecolor("white")
    anchored.patch.set_alpha(0.9)
    ax.add_artist(anchored)

    line = ax.plot(
        ell_range,
        threshold,
        color="red",
        linestyle=":",
        linewidth=0.9,
        label=threshold_label,
    )
    if show_threshold_legend:
        ax.legend(handles=line, loc="upper right", fontsize=7, framealpha=0.85)
    ax.grid(linestyle=":", alpha=0.4)


def plot_fig_4_4_combined(
    processed_root: Path, q1_months: list[str], q5_months: list[str], output_path: Path
) -> None:
    """Single figure with Q1 (top row) and Q5 (bottom row) stacked.

    2 rows × N cols where N = months-per-quarter. Each row corresponds to
    one quarter; each cell is one month.
    """
    rows_data = [
        (
            "2025 Q1",
            q1_months,
            [
                _load_month(
                    processed_root,
                    RUN_RELAXED,
                    m,
                    "relaxed_all_assets_summary_exp2_k_acceptance.csv",
                )
                for m in q1_months
            ],
        ),
        (
            "2026 Q1 (Q5)",
            q5_months,
            [
                _load_month(
                    processed_root,
                    RUN_RELAXED,
                    m,
                    "relaxed_all_assets_summary_exp2_k_acceptance.csv",
                )
                for m in q5_months
            ],
        ),
    ]

    # Threshold curve covers the union of ℓ across all months in both rows.
    all_ells: set[int] = set()
    for _, _, dfs in rows_data:
        for df in dfs:
            all_ells.update(int(v) for v in df["agg_level"].unique())
    ell_range = np.array(sorted(all_ells))
    threshold = np.maximum(RELAXED_F, np.ceil(RELAXED_F_FRACTION * ell_range))
    threshold_label = (
        rf"$\max(F,\lceil f\cdot N_{{valid}}\rceil)$, "
        rf"$(F,f)=({RELAXED_F},{RELAXED_F_FRACTION})$"
    )

    n_cols = max(len(q1_months), len(q5_months))
    # Match Fig 4.3's per-cell aspect ratio: 4.3 uses (3*n_cols+1.5, 12) over
    # 5 rows → ~2.4 height per row. Use the same width formula here and scale
    # height to 2 rows so each cell has the same width:height as in 4.3.
    fig, axes = plt.subplots(
        2,
        n_cols,
        figsize=(3 * n_cols + 1.5, 7.5),
        sharey=True,
        sharex="col",
        squeeze=False,
    )

    for r, (row_label, months, dfs) in enumerate(rows_data):
        for c, (month, df) in enumerate(zip(months, dfs)):
            ax = axes[r, c]
            show_threshold_legend = r == 0 and c == n_cols - 1
            _draw_relaxed_panel(
                ax,
                df,
                ell_range,
                threshold,
                threshold_label,
                show_threshold_legend=show_threshold_legend,
            )
            ax.set_title(month, fontsize=11)
            if r == 1:
                ax.set_xlabel(r"$\ell$ (trades)", fontsize=10)
        # Quarter label on the left of each row
        axes[r, 0].set_ylabel(
            row_label + r"     $n_{\mathrm{pass}}(\ell)$",
            fontsize=10,
        )

    fig.suptitle(
        "Experiment 2 · All-offset, relaxed criterion · "
        "2025 Q1 (top) / 2026 Q1, Q5 (bottom)"
        "  (★ = selected $\\ell^*$)",
        fontsize=11,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"[saved] {output_path}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the eight Experiment 2 thesis figures (§4.3); "
        "four §4.3 subsections × Q1 / Q5 quarters."
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=DEFAULT_PROCESSED_ROOT,
        help="Root containing Experiment 2 run directories.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write the PNG files (thesis/figures by default).",
    )
    args = parser.parse_args()

    # (panel_letter, quarter_label_suffix, months, full label)
    quarters = [
        ("a", "q1", DEFAULT_Q1_MONTHS, Q1_LABEL),
        ("b", "q5", DEFAULT_Q5_MONTHS, Q5_LABEL),
    ]

    for panel, qsuffix, months, label in quarters:
        plot_fig_4_2(
            processed_root=args.processed_root,
            months=months,
            quarter_label=label,
            output_path=args.output_dir
            / f"exp2_fig_4_2{panel}_single_offset_{qsuffix}.png",
        )

    for panel, qsuffix, months, label in quarters:
        plot_pass_rate_figure(
            processed_root=args.processed_root,
            run_dir=RUN_STRICT,
            csv_name="all_assets_summary_exp2_k_acceptance.csv",
            months=months,
            quarter_label=label,
            output_path=args.output_dir
            / f"exp2_fig_4_3{panel}_all_offset_strict_{qsuffix}.png",
            fig_title="Experiment 2 · All-offset, strict criterion",
            xlabel=r"$\ell$ (trades)",
        )

    # Fig 4.4: combined Q1 (top) + Q5 (bottom) in a single figure.
    plot_fig_4_4_combined(
        processed_root=args.processed_root,
        q1_months=DEFAULT_Q1_MONTHS,
        q5_months=DEFAULT_Q5_MONTHS,
        output_path=args.output_dir / "exp2_fig_4_4_all_offset_relaxed.png",
    )

    for panel, qsuffix, months, label in quarters:
        plot_pass_rate_figure(
            processed_root=args.processed_root,
            run_dir=RUN_1SBARS,
            csv_name="all_assets_summary_exp2_k_acceptance.csv",
            months=months,
            quarter_label=label,
            output_path=args.output_dir / f"exp2_fig_4_5{panel}_1sbars_{qsuffix}.png",
            fig_title="Experiment 2 · 1-second bars (physical-time)",
            xlabel=r"$\ell$ (seconds)",
            # 1-second bars use the step=1 ℓ grid (~590 points per asset per
            # month). Raw plotting is too noisy; apply a 7-wide centred
            # rolling mean + every-5th subsample. Table A.5 stays at
            # full step=1 precision.
            rolling_window=7,
            plot_step=5,
        )


if __name__ == "__main__":
    main()
