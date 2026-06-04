"""
Experiment 4 — validation visualisation.

Produces two thesis figures from the validation outputs: the cell-level
verdict matrices (exp4_validation_verdict.png, one panel per n) and the
n-axis trade-offs (exp4_validation_tradeoff.png: bits/month, ell*_n, and
combined p(1) median). Outputs go to data/processed/experiment4/figures/.

Run from the project root after runner_exp4_validation.py:
    python scripts/plot_exp4_validation.py
"""

from __future__ import annotations

import argparse
import json
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
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

DEFAULT_VALIDATION_ROOT = Path("data/processed/experiment4/validation")
DEFAULT_CALIB_SUMMARY = Path(
    "data/processed/experiment4/calibration_all_subsets/all_subsets_summary.csv"
)
DEFAULT_FIGURES_DIR = Path("data/processed/experiment4/validation/figures")

# 29 sub-tests = 5 stats.py + 7 nistrng + 17 Alphabit. Pulled from the
# battery module so this stays in sync with whatever full_battery() returns
# (and with plot_exp3 / aggregate_exp3_battery).
from src.battery import ALL_SUB_TESTS as _ALL_SUB_TESTS

SUB_TESTS: list[str] = list(_ALL_SUB_TESTS)

# Per-sub-test compact label (matches the `short` dict in
# scripts/aggregate_exp3_battery.py so heatmaps read consistently
# across Exp 3 and Exp 4). 12 fixed + 17 Alphabit = 29.
_SUB_TEST_LABEL = {
    "D_adaptive": "D_adp",
    "D_k2": "D_k=2",
    "Monobit": "Mono",
    "Runs": "Runs",
    "ApEn": "ApEn",
    "BlockFrequency": "BlockF",
    "CumSum_forward": "CSum_F",
    "CumSum_backward": "CSum_B",
    "LongestRun": "LRun",
    "DFT": "DFT",
    "Serial_m": "Ser_m",
    "Serial_m_minus_1": "Ser_m-1",
    "Alphabit_MultinomialBitsOver_L2":  "MnB2",
    "Alphabit_MultinomialBitsOver_L4":  "MnB4",
    "Alphabit_MultinomialBitsOver_L8":  "MnB8",
    "Alphabit_MultinomialBitsOver_L16": "MnB16",
    "Alphabit_HammingIndep_L16": "HmI16",
    "Alphabit_HammingIndep_L32": "HmI32",
    "Alphabit_HammingCorr_L32":  "HmC32",
    "Alphabit_RandomWalk1_L64_H":  "RW64H",
    "Alphabit_RandomWalk1_L64_M":  "RW64M",
    "Alphabit_RandomWalk1_L64_J":  "RW64J",
    "Alphabit_RandomWalk1_L64_R":  "RW64R",
    "Alphabit_RandomWalk1_L64_C":  "RW64C",
    "Alphabit_RandomWalk1_L320_H": "R320H",
    "Alphabit_RandomWalk1_L320_M": "R320M",
    "Alphabit_RandomWalk1_L320_J": "R320J",
    "Alphabit_RandomWalk1_L320_R": "R320R",
    "Alphabit_RandomWalk1_L320_C": "R320C",
}
SUB_TEST_LABELS: list[str] = [_SUB_TEST_LABEL.get(s, s) for s in SUB_TESTS]

DISPLAY_ASSET_NAME = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}

# Verdict colour mapping: 0=PASS, 1=FAIL, 2=INVALID, 3=NOT_RUN.
# INVALID (ran, all-offset sanity-failed) is mid-grey; NOT_RUN (TestU01
# length-skipped on every offset of this cell — common for
# MultinomialBitsOver_L16 / RandomWalk1_L320 on short fused streams) is
# paler so it reads as "no data" rather than "ran and failed sanity". Any
# unknown verdict string is binned into NOT_RUN by the .get() default.
VERDICT_COLOURS = ListedColormap(["#e8f1fa", "#08306b", "#bdc7d1", "#ffffff"])
VERDICT_LABELS = {"PASS": 0, "FAIL": 1, "INVALID": 2, "NOT_RUN": 3}


def _short_subset(subset: list[str]) -> str:
    return "+".join(DISPLAY_ASSET_NAME.get(a, a) for a in subset)


def _load_verdict_matrix(n_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    """Return (verdict matrix months × sub_tests with 0/1/2/3 codes,
    month labels)."""
    df = pd.read_csv(n_dir / "per_month_verdict_matrix.csv").sort_values("month")
    months = df["month"].tolist()
    matrix = np.zeros((len(months), len(SUB_TESTS)), dtype=np.int8)
    for i, sub in enumerate(SUB_TESTS):
        col = f"{sub}_verdict"
        # If the verdict column is missing (e.g. older outputs re-plotted
        # against the current SUB_TESTS list), mark every month NOT_RUN.
        if col not in df.columns:
            matrix[:, i] = VERDICT_LABELS["NOT_RUN"]
            continue
        for j, verdict in enumerate(df[col].tolist()):
            matrix[j, i] = VERDICT_LABELS.get(verdict, VERDICT_LABELS["NOT_RUN"])
    return matrix, months


def _plot_verdict_matrices(validation_root: Path, output_path: Path) -> None:
    summary_path = validation_root / "validation_summary.json"
    summary = json.loads(summary_path.read_text())
    n_values = summary["n_values"]
    subset_picks = summary["subset_picks"]
    tick_fontsize = 10
    axis_label_fontsize = 11
    panel_title_fontsize = 12
    legend_fontsize = 11
    figure_title_fontsize = 14

    # 29 sub-tests per panel; wide figure so the x-axis labels stay legible.
    fig, axes = plt.subplots(4, 1, figsize=(13.5, 19.5))
    axes = axes.flatten()

    for idx, n in enumerate(n_values):
        ax = axes[idx]
        n_dir = validation_root / f"n{n}"
        matrix, months = _load_verdict_matrix(n_dir)
        pick = subset_picks[str(n)]
        ax.imshow(
            matrix,
            cmap=VERDICT_COLOURS,
            vmin=0,
            vmax=3,
            aspect="auto",
            interpolation="nearest",
        )
        ax.set_xticks(range(len(SUB_TESTS)))
        ax.set_xticklabels(
            SUB_TEST_LABELS, rotation=45, ha="right", fontsize=tick_fontsize
        )
        ax.set_yticks(range(len(months)))
        ax.set_yticklabels(months, fontsize=tick_fontsize)
        if idx == len(n_values) - 1:
            ax.set_xlabel("sub-test", fontsize=axis_label_fontsize)
        ax.set_ylabel("validation month", fontsize=axis_label_fontsize)
        ax.set_title(
            f"n={n}: {_short_subset(pick['subset'])}  "
            f"ell*={pick['ell_star_n']}  "
            f"selected output offset={pick['witness_offset']}",
            fontsize=panel_title_fontsize,
        )
        # Optionally annotate FAIL cells with pass_rate from the CSV
        per_month_csv = pd.read_csv(n_dir / "per_month_verdict_matrix.csv").sort_values(
            "month"
        )
        for j_month in range(len(months)):
            for i_test, sub in enumerate(SUB_TESTS):
                code = matrix[j_month, i_test]
                if code == 1:
                    rate = per_month_csv.iloc[j_month][f"{sub}_pass_rate"]
                    if pd.notna(rate):
                        ax.text(
                            i_test,
                            j_month,
                            f"{rate:.2f}",
                            ha="center",
                            va="center",
                            fontsize=10,
                            color="white",
                        )

    # Hide unused axes if n_values has fewer than 4 entries
    for k in range(len(n_values), len(axes)):
        axes[k].axis("off")

    handles = [
        Patch(facecolor="#e8f1fa", edgecolor="#aaaaaa", label="PASS (>=80% offsets)"),
        Patch(facecolor="#08306b", edgecolor="none", label="FAIL"),
        Patch(facecolor="#bdc7d1", edgecolor="none", label="INVALID (sanity)"),
        Patch(
            facecolor="#ffffff",
            edgecolor="#888888",
            linewidth=0.5,
            label="NOT_RUN (TestU01 length-skip)",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.01),
        fontsize=legend_fontsize,
    )
    fig.suptitle(
        "Experiment 4 validation — cell-level verdict per sub-test "
        f"(6 months × {len(SUB_TESTS)} sub-tests, throughput-best subset per n)",
        fontsize=figure_title_fontsize,
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.975))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {output_path}")


def _gather_tradeoff_data(
    validation_root: Path, calib_summary_path: Path
) -> pd.DataFrame:
    """One row per n with calibration + validation summary stats."""
    summary = json.loads((validation_root / "validation_summary.json").read_text())
    n_values = summary["n_values"]
    picks = summary["subset_picks"]
    per_n_summary = summary["per_n_summary"]

    calib_df = pd.read_csv(calib_summary_path)
    rows: list[dict] = []
    for n in n_values:
        pick = picks[str(n)]
        per_n = per_n_summary[str(n)]
        subset_label = "-".join(pick["subset"])
        calib_row = calib_df[
            (calib_df["n"] == n) & (calib_df["subset"] == subset_label)
        ]
        calib_bits = (
            float(calib_row["estimated_bits_per_month"].iloc[0])
            if not calib_row.empty
            else float("nan")
        )

        per_month_throughput = pd.read_csv(
            validation_root / f"n{n}" / "per_month_throughput.csv"
        )
        per_month_verdict = pd.read_csv(
            validation_root / f"n{n}" / "per_month_verdict_matrix.csv"
        )
        rows.append(
            {
                "n": n,
                "subset": _short_subset(pick["subset"]),
                "ell_star_n": pick["ell_star_n"],
                "calib_bits_per_month": calib_bits,
                "val_bits_median": float(per_month_throughput["output_bits"].median()),
                "val_bits_min": float(per_month_throughput["output_bits"].min()),
                "val_bits_max": float(per_month_throughput["output_bits"].max()),
                "val_hours_per_256_median": per_n["hours_per_256_bits_median"],
                "val_fused_p1_median": float(per_month_verdict["fused_p1"].median()),
                "val_fused_p1_min": float(per_month_verdict["fused_p1"].min()),
                "val_fused_p1_max": float(per_month_verdict["fused_p1"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values("n").reset_index(drop=True)


def _plot_tradeoff(
    validation_root: Path,
    calib_summary_path: Path,
    output_path: Path,
) -> None:
    df = _gather_tradeoff_data(validation_root, calib_summary_path)
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 12.0), constrained_layout=True)

    # ---- Panel (a): throughput ----
    ax = axes[0]
    x = df["n"].to_numpy()
    width = 0.35
    ax.bar(
        x - width / 2,
        df["calib_bits_per_month"],
        width=width,
        label="calibration estimate",
        color="#9ecae1",
        edgecolor="#3182bd",
    )
    ax.bar(
        x + width / 2,
        df["val_bits_median"],
        width=width,
        yerr=[
            df["val_bits_median"] - df["val_bits_min"],
            df["val_bits_max"] - df["val_bits_median"],
        ],
        capsize=4,
        label="validation median [min, max]",
        color="#3182bd",
        edgecolor="#08519c",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"n={n}\n{sub}" for n, sub in zip(df["n"], df["subset"])],
        fontsize=8,
    )
    ax.set_ylabel("bits / month")
    ax.set_title("(a) throughput per n")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # ---- Panel (b): ell* vs n ----
    ax = axes[1]
    ax.plot(
        df["n"],
        df["ell_star_n"],
        marker="o",
        markersize=10,
        linewidth=2,
        color="#d62728",
    )
    for _, row in df.iterrows():
        ax.annotate(
            f"  ell*={int(row['ell_star_n'])}",
            (row["n"], row["ell_star_n"]),
            fontsize=9,
            va="center",
        )
    ax.set_xticks(df["n"])
    ax.set_xticklabels(
        [f"n={n}" for n in df["n"]],
        fontsize=8,
    )
    ax.set_ylabel(r"$\ell^*_n$")
    ax.set_title("(b) selected aggregation level (odd-n effect)")
    ax.grid(linestyle=":", alpha=0.5)
    # Highlight odd vs even with shaded background
    for _, row in df.iterrows():
        if row["n"] % 2 == 1:
            ax.axvspan(row["n"] - 0.4, row["n"] + 0.4, alpha=0.08, color="#2ca02c")
    ax.set_ylim(0, max(df["ell_star_n"]) * 1.3 + 1)

    # ---- Panel (c): combined p(1) vs n ----
    ax = axes[2]
    ax.errorbar(
        df["n"],
        df["val_fused_p1_median"],
        yerr=[
            df["val_fused_p1_median"] - df["val_fused_p1_min"],
            df["val_fused_p1_max"] - df["val_fused_p1_median"],
        ],
        marker="o",
        markersize=10,
        capsize=4,
        linewidth=2,
        color="#3182bd",
        label="combined p(1) median [min, max]",
    )
    ax.axhline(0.5, linestyle="--", color="gray", linewidth=1, label="0.5 (uniform)")
    ax.set_xticks(df["n"])
    ax.set_xticklabels([f"n={n}" for n in df["n"]], fontsize=8)
    ax.set_ylabel("combined stream p(1)")
    ax.set_title("(c) marginal bias (moment-cancellation)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(linestyle=":", alpha=0.5)
    for _, row in df.iterrows():
        if row["n"] % 2 == 1:
            ax.axvspan(row["n"] - 0.4, row["n"] + 0.4, alpha=0.08, color="#2ca02c")
    ax.set_ylim(0.20, 0.55)

    fig.suptitle(
        "Experiment 4 validation — trade-offs across combination size",
        fontsize=12,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {output_path}")

    # Also print the underlying table to console for the user.
    print()
    print("=== trade-off data ===")
    print(df.to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot Experiment 4 validation verdict + trade-off figures."
    )
    parser.add_argument(
        "--validation-root",
        default=str(DEFAULT_VALIDATION_ROOT),
        help=f"(default: {DEFAULT_VALIDATION_ROOT})",
    )
    parser.add_argument(
        "--calibration-summary",
        default=str(DEFAULT_CALIB_SUMMARY),
        help=f"(default: {DEFAULT_CALIB_SUMMARY})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_FIGURES_DIR),
        help=f"(default: {DEFAULT_FIGURES_DIR})",
    )
    args = parser.parse_args()

    validation_root = Path(args.validation_root)
    calib_summary = Path(args.calibration_summary)
    output_dir = Path(args.output_dir)

    if not (validation_root / "validation_summary.json").exists():
        print(f"[fatal] missing {validation_root / 'validation_summary.json'}")
        return 1
    if not calib_summary.exists():
        print(f"[fatal] missing {calib_summary}")
        return 1

    _plot_verdict_matrices(validation_root, output_dir / "exp4_validation_verdict.png")
    _plot_tradeoff(
        validation_root,
        calib_summary,
        output_dir / "exp4_validation_tradeoff.png",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
