"""
Experiment 4 — validation visualisation.

Produces two thesis-ready figures from the validation outputs:

  Figure 1 — exp4_validation_verdict.png
    2x2 panel of cell-level verdict matrices, one panel per n.
    Each panel is 6 validation months (rows) x 12 sub-tests (cols),
    colour-coded PASS (green) / FAIL (red) / INVALID (grey).
    Panel title carries n + subset + ell* + witness offset.

  Figure 2 — exp4_validation_tradeoff.png
    1x3 panel of n-axis trade-offs:
      (a) bits/month — calibration estimate vs validation median
      (b) ell*_n      — exposes the odd/even-n effect
      (c) fused_p1 median — confirms the moment-cancellation result
                            (odd n at 0.5, even n drifts)

Reads:
  data/processed/experiment4/validation/validation_summary.json
  data/processed/experiment4/validation/n{N}/per_month_verdict_matrix.csv
  data/processed/experiment4/validation/n{N}/per_month_throughput.csv
  data/processed/experiment4/calibration_all_subsets/all_subsets_summary.csv

Outputs:
  data/processed/experiment4/figures/exp4_validation_verdict.png
  data/processed/experiment4/figures/exp4_validation_tradeoff.png

Run from the project root after runner_exp4_validation.py has finished:
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

SUB_TESTS = [
    "D_adaptive",
    "D_k2",
    "Monobit",
    "Runs",
    "ApEn",
    "BlockFrequency",
    "CumSum_forward",
    "CumSum_backward",
    "LongestRun",
    "DFT",
    "Serial_m",
    "Serial_m_minus_1",
]
SUB_TEST_LABELS = [
    "D_adp",
    "D_k=2",
    "Mono",
    "Runs",
    "ApEn",
    "BlockF",
    "CSum_F",
    "CSum_B",
    "LRun",
    "DFT",
    "Ser_m",
    "Ser_m-1",
]

DISPLAY_ASSET_NAME = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BNBUSDT": "BNB",
    "SOLUSDT": "SOL",
    "DOGEUSDT": "DOGE",
}

# Verdict colour mapping: 0=PASS, 1=FAIL, 2=INVALID
VERDICT_COLOURS = ListedColormap(["#2ca02c", "#d62728", "#cccccc"])
VERDICT_LABELS = {"PASS": 0, "FAIL": 1, "INVALID": 2}


def _short_subset(subset: list[str]) -> str:
    return "+".join(DISPLAY_ASSET_NAME.get(a, a) for a in subset)


def _load_verdict_matrix(n_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    """Return (verdict matrix months × sub_tests with 0/1/2 codes,
    month labels)."""
    df = pd.read_csv(n_dir / "per_month_verdict_matrix.csv").sort_values("month")
    months = df["month"].tolist()
    matrix = np.zeros((len(months), len(SUB_TESTS)), dtype=np.int8)
    for i, sub in enumerate(SUB_TESTS):
        col = f"{sub}_verdict"
        for j, verdict in enumerate(df[col].tolist()):
            matrix[j, i] = VERDICT_LABELS.get(verdict, 2)
    return matrix, months


def _plot_verdict_matrices(validation_root: Path, output_path: Path) -> None:
    summary_path = validation_root / "validation_summary.json"
    summary = json.loads(summary_path.read_text())
    n_values = summary["n_values"]
    subset_picks = summary["subset_picks"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
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
            vmax=2,
            aspect="auto",
            interpolation="nearest",
        )
        ax.set_xticks(range(len(SUB_TESTS)))
        ax.set_xticklabels(SUB_TEST_LABELS, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(months)))
        ax.set_yticklabels(months, fontsize=8)
        ax.set_xlabel("sub-test")
        ax.set_ylabel("validation month")
        ax.set_title(
            f"n={n}: {_short_subset(pick['subset'])}  "
            f"ell*={pick['ell_star_n']}  "
            f"witness={pick['witness_offset']}",
            fontsize=10,
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
                            fontsize=6,
                            color="white",
                        )

    # Hide unused axes if n_values has fewer than 4 entries
    for k in range(len(n_values), len(axes)):
        axes[k].axis("off")

    handles = [
        Patch(facecolor="#2ca02c", edgecolor="none", label="PASS (>=80% offsets)"),
        Patch(facecolor="#d62728", edgecolor="none", label="FAIL"),
        Patch(facecolor="#cccccc", edgecolor="none", label="INVALID (sanity)"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(
        "Experiment 4 validation — cell-level verdict per sub-test "
        "(6 months × 12 sub-tests, throughput-best subset per n)",
        fontsize=12,
    )
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
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True)

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

    # ---- Panel (c): fused_p1 vs n ----
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
        label="fused p(1) median [min, max]",
    )
    ax.axhline(0.5, linestyle="--", color="gray", linewidth=1, label="0.5 (uniform)")
    ax.set_xticks(df["n"])
    ax.set_xticklabels([f"n={n}" for n in df["n"]], fontsize=8)
    ax.set_ylabel("fused stream p(1)")
    ax.set_title("(c) marginal bias (moment-cancellation)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(linestyle=":", alpha=0.5)
    for _, row in df.iterrows():
        if row["n"] % 2 == 1:
            ax.axvspan(row["n"] - 0.4, row["n"] + 0.4, alpha=0.08, color="#2ca02c")
    ax.set_ylim(0.20, 0.55)

    fig.suptitle(
        "Experiment 4 validation — trade-offs across fusion size",
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
