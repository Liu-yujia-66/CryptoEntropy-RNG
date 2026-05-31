"""Prototype evaluation -- CryptoEntropy-RNG password generator (plan v3.4 Section 3.3).

Computes the data summary for the password demo and writes:
  - prototype_summary.txt : numbers only (regenerated every run)
  - per_cell_eval.csv     : per-cell chi-square and entropy
  - summary.json          : machine-readable group summary
  - two figures           : position heatmap, group comparison figure

Metrics (master's-scope, descriptive -- no formal hypothesis test):
  A. Pooled chi-square goodness-of-fit to a uniform 70-char distribution,
     per (group, month) cell (16 positions pooled -> 1,600 chars).
  B. Shannon entropy per cell over the same 1,600 characters.

Interpretation, assumptions and the security model are NOT emitted by this
script -- they live in the hand-maintained companion document
data/processed/prototype/evaluation/prototype_analysis.txt.

Usage:
    python scripts/eval_prototype.py
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy import stats  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
import prototype as proto  # noqa: E402

PROTO_DIR = REPO / "data" / "processed" / "prototype"
EVAL_DIR = PROTO_DIR / "evaluation"
FIG_DIR = EVAL_DIR / "figures"
ALPHA = 0.01
DISPLAY_CELL = ("n3", "2026-03")           # selected cell for the position heatmap
GROUP_ORDER = ["n2", "n3", "n5", "b1", "b2"]   # canonical row order everywhere
GROUP_RANK = {g: i for i, g in enumerate(GROUP_ORDER)}
CHAR_INDEX = {c: i for i, c in enumerate(proto.CHARSET)}
MAX_ENTROPY = np.log2(proto.CHARSET_SIZE)  # log2(70) ~= 6.1293

VALIDATION_SUMMARY = (REPO / "data" / "processed" / "experiment4"
                      / "validation" / "validation_summary.json")


def load_upstream_fail_profile() -> dict[str, int]:
    """Read the Exp 4 upstream battery profile from validation_summary.json.

    Returns a dict like {"n2": 4, "n3": 11, "n5": 8}: the number of 29-test
    battery sub-tests that FAIL in at least one of the 6 validation months,
    per market fusion size. Decouples this script from a hardcoded snapshot
    so re-running Exp 4 propagates here automatically.
    """
    with open(VALIDATION_SUMMARY) as fh:
        v = json.load(fh)
    sub_tests = v["gate_config"]["sub_tests"]
    out = {}
    for n_str, s in v["per_n_summary"].items():
        counts = s["sub_test_pass_counts"]
        out[f"n{n_str}"] = sum(1 for st in sub_tests if counts[st]["FAIL"] > 0)
    return out


def load_expand_round_counts() -> Counter:
    """Sum the expand_rounds_histogram across every per-cell metadata.json.

    Counter[1] = N means N passwords completed in 1 HKDF-Expand round;
    Counter[2+] would indicate rejection-sampling exhaustion fallbacks.
    """
    total: Counter = Counter()
    for meta_path in PROTO_DIR.rglob("metadata.json"):
        with open(meta_path) as fh:
            m = json.load(fh)
        for k, v in m.get("expand_rounds_histogram", {}).items():
            total[int(k)] += int(v)
    return total


def load_sample_passwords(group: str, month: str, n: int = 8) -> list[str]:
    """First n passwords of one market cell (for the selected display sample)."""
    pw_path = PROTO_DIR / "market" / group / month / "passwords.txt"
    if not pw_path.exists():
        return []
    return load_passwords(pw_path)[:n]


# --------------------------------------------------------------------------
# Cell discovery and loading
# --------------------------------------------------------------------------
def discover_cells() -> list[dict]:
    """Return the 30 evaluation cells: 18 market + 6 B1 + 6 B2."""
    cells = []
    market = PROTO_DIR / "market"
    for n_dir in sorted(market.glob("n*")):
        for month_dir in sorted(n_dir.iterdir()):
            pw = month_dir / "passwords.txt"
            if pw.exists():
                cells.append({"group": n_dir.name, "kind": "market",
                              "month": month_dir.name, "path": pw})
    for kind, label in (("baseline_b1", "b1"), ("baseline_b2", "b2")):
        base = PROTO_DIR / kind
        for month_dir in sorted(base.iterdir()):
            pw = month_dir / "passwords.txt"
            if pw.exists():
                cells.append({"group": label, "kind": kind,
                              "month": month_dir.name, "path": pw})
    return cells


def load_passwords(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def char_counts(passwords: list[str]) -> np.ndarray:
    """Pooled count of each of the 70 charset characters over all positions."""
    counts = np.zeros(proto.CHARSET_SIZE, dtype=np.int64)
    for pw in passwords:
        for ch in pw:
            counts[CHAR_INDEX[ch]] += 1
    return counts


def pooled_chi_square(counts: np.ndarray) -> tuple[float, float]:
    """Chi-square goodness-of-fit to a uniform distribution over 70 categories."""
    total = int(counts.sum())
    expected = np.full(proto.CHARSET_SIZE, total / proto.CHARSET_SIZE)
    res = stats.chisquare(counts, f_exp=expected)
    return float(res.statistic), float(res.pvalue)


def shannon_entropy(counts: np.ndarray) -> float:
    """Shannon entropy (bits/char) of the pooled character distribution."""
    total = counts.sum()
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def position_frequency(passwords: list[str], length: int) -> np.ndarray:
    """70 x length matrix of character counts per position."""
    mat = np.zeros((proto.CHARSET_SIZE, length), dtype=np.int64)
    for pw in passwords:
        for pos, ch in enumerate(pw):
            mat[CHAR_INDEX[ch], pos] += 1
    return mat


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
def figure_position_heatmap(cells: list[dict]) -> Path | None:
    """70 x 16 position-frequency heatmap for the selected display cell."""
    match = [c for c in cells
             if c["group"] == DISPLAY_CELL[0] and c["month"] == DISPLAY_CELL[1]]
    if not match:
        return None
    passwords = load_passwords(match[0]["path"])
    length = len(passwords[0])
    mat = position_frequency(passwords, length)

    np.savetxt(EVAL_DIR / f"position_freq_{DISPLAY_CELL[0]}_{DISPLAY_CELL[1]}.csv",
               mat, fmt="%d", delimiter=",")

    fig, ax = plt.subplots(figsize=(7, 9))
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_xlabel("character position (0-15)")
    ax.set_ylabel("charset index (0-69)")
    ax.set_title(f"Position-character frequency -- market {DISPLAY_CELL[0]} "
                 f"{DISPLAY_CELL[1]}\n({len(passwords)} passwords, "
                 f"uniform expectation {len(passwords) / proto.CHARSET_SIZE:.2f}/cell)")
    ax.set_xticks(range(length))
    fig.colorbar(im, ax=ax, label="count")
    fig.tight_layout()
    out = FIG_DIR / f"position_heatmap_{DISPLAY_CELL[0]}_{DISPLAY_CELL[1]}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def figure_side_by_side(rows: list[dict]) -> Path:
    """Two-panel vertical comparison: chi-square p-values and entropy per group."""
    order = GROUP_ORDER
    labels = {"n2": "market n=2", "n3": "market n=3", "n5": "market n=5",
              "b1": "B1 ideal-password", "b2": "B2 ideal-IKM"}
    by_group = {g: [r for r in rows if r["group"] == g] for g in order}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 9))
    for x, g in enumerate(order):
        ps = [r["chi2_p"] for r in by_group[g]]
        hs = [r["shannon_entropy"] for r in by_group[g]]
        ax1.scatter([x] * len(ps), ps, s=45, alpha=0.75, color="#3366cc")
        ax2.scatter([x] * len(hs), hs, s=45, alpha=0.75, color="#3366cc")

    ax1.axhline(ALPHA, color="red", ls="--", lw=1, label=f"alpha = {ALPHA}")
    ax1.set_yscale("log")
    ax1.set_ylabel("pooled chi-square p-value (log scale)")
    ax1.set_title("A. charset uniformity (pooled chi-square)")
    ax1.legend(loc="lower right", fontsize=8)

    ax2.axhline(MAX_ENTROPY, color="green", ls="--", lw=1,
                label=f"log2(70) = {MAX_ENTROPY:.4f}")
    ax2.set_ylabel("Shannon entropy (bits/char)")
    ax2.set_title("B. Shannon entropy")
    ax2.legend(loc="lower right", fontsize=8)

    for ax in (ax1, ax2):
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([labels[g] for g in order], rotation=20, ha="right")
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Prototype evaluation -- market n in {2,3,5} vs baselines "
                 "(6 validation months each)")
    fig.tight_layout()
    out = FIG_DIR / "sidebyside_chi2_entropy.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    cells = discover_cells()
    if not cells:
        sys.exit("no prototype cells found -- run scripts/runner_prototype.py first")

    rows = []
    for cell in cells:
        passwords = load_passwords(cell["path"])
        counts = char_counts(passwords)
        chi2_stat, chi2_p = pooled_chi_square(counts)
        entropy = shannon_entropy(counts)
        rows.append({
            "group": cell["group"],
            "kind": cell["kind"],
            "month": cell["month"],
            "n_passwords": len(passwords),
            "n_chars": int(counts.sum()),
            "categories_seen": int((counts > 0).sum()),
            "chi2_stat": round(chi2_stat, 4),
            "chi2_df": proto.CHARSET_SIZE - 1,
            "chi2_p": chi2_p,
            "chi2_pass": bool(chi2_p >= ALPHA),
            "shannon_entropy": round(entropy, 6),
            "shannon_bias": round(MAX_ENTROPY - entropy, 6),
        })

    # ---- per-cell CSV -------------------------------------------------------
    csv_path = EVAL_DIR / "per_cell_eval.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (GROUP_RANK[r["group"]],
                                             r["month"])):
            writer.writerow(r)

    # ---- 5-group summary ----------------------------------------------------
    order = GROUP_ORDER
    labels = {"n2": "market n=2", "n3": "market n=3", "n5": "market n=5",
              "b1": "B1 ideal-password", "b2": "B2 ideal-IKM"}
    summary = {}
    for g in order:
        grp = [r for r in rows if r["group"] == g]
        ents = [r["shannon_entropy"] for r in grp]
        ps = [r["chi2_p"] for r in grp]
        n_pass = sum(r["chi2_pass"] for r in grp)
        summary[g] = {
            "label": labels[g],
            "cells": len(grp),
            "chi2_pass": n_pass,
            "chi2_p_min": min(ps) if ps else None,
            "chi2_p_max": max(ps) if ps else None,
            "entropy_median": round(statistics.median(ents), 6) if ents else None,
            "entropy_min": round(min(ents), 6) if ents else None,
            "entropy_max": round(max(ents), 6) if ents else None,
        }

    with open(EVAL_DIR / "summary.json", "w") as fh:
        json.dump({"alpha": ALPHA, "max_entropy": MAX_ENTROPY,
                   "groups": summary}, fh, indent=2)

    # ---- precompute the figures used by the data summary -------------------
    all_pass = sum(s["chi2_pass"] for s in summary.values())
    all_cells = sum(s["cells"] for s in summary.values())
    ent_lo = min(s["entropy_min"] for s in summary.values())
    ent_hi = max(s["entropy_max"] for s in summary.values())
    fails = [r for r in rows if not r["chi2_pass"]]
    n_chars = rows[0]["n_chars"]
    pw_per_cell = rows[0]["n_passwords"]
    pw_length = n_chars // pw_per_cell
    market_cells = sum(s["cells"] for g, s in summary.items() if g.startswith("n"))
    market_total = market_cells * pw_per_cell
    b1_total = summary["b1"]["cells"] * pw_per_cell
    b2_total = summary["b2"]["cells"] * pw_per_cell
    pw_total = market_total + b1_total + b2_total
    ent_theo_per_pw = MAX_ENTROPY * pw_length
    median_ent_per_char = statistics.median(r["shannon_entropy"] for r in rows)
    ent_obs_per_pw = median_ent_per_char * pw_length
    upstream = load_upstream_fail_profile()
    expand_rounds = load_expand_round_counts()
    samples = load_sample_passwords(DISPLAY_CELL[0], DISPLAY_CELL[1], n=8)

    # B1 records 0 rounds (no HKDF); only market + B2 run rejection sampling.
    hkdf_pw_total = market_total + b2_total
    n_fallback = sum(v for k, v in expand_rounds.items() if k > 1)
    hkdf_hist = ", ".join(f"{k} round{'s' if k > 1 else ''}: {v}"
                          for k, v in sorted(expand_rounds.items()) if k >= 1)
    if fails:
        flist = "; ".join(f"{r['group']} {r['month']} (p={r['chi2_p']:.4f})"
                          for r in fails)
        market_fails = [r for r in fails if r["group"].startswith("n")]
        fail_tag = (f"includes {len(market_fails)} market cell(s)" if market_fails
                    else f"all on baseline cells; 0 of {market_cells} "
                         f"market cells failed")
    else:
        flist, fail_tag = "none", ""

    # ---- data summary (numbers only; interpretation -> prototype_analysis.txt)
    lines = []
    lines.append("Prototype evaluation -- data summary")
    lines.append("=" * 78)
    lines.append("Numbers only -- regenerated by scripts/eval_prototype.py on "
                 "every run.")
    lines.append("Interpretation, assumptions and security model: "
                 "prototype_analysis.txt")
    lines.append("Per-cell numbers: per_cell_eval.csv    "
                 "Full parameters: ../config.json")
    lines.append("")
    lines.append("Configuration")
    lines.append("-" * 78)
    lines.append("charset      : 70 = [a-z] + [A-Z] + [0-9] + !@#$%^&*")
    lines.append(f"password     : length = {pw_length} chars  "
                 f"(entropy = length x log2(70) ~= "
                 f"{int(round(ent_theo_per_pw))} bits)")
    lines.append(f"pipeline     : HKDF-SHA256 RFC 5869, per-password Extract, "
                 f"IKM = {proto.IKM_BYTES} bytes/password")
    lines.append(f"total output : {pw_total:,} passwords across {all_cells} cells "
                 f"({market_total:,} market + {b1_total} B1 + {b2_total} B2)")
    lines.append(f"alpha = {ALPHA}    theoretical entropy log2(70) = "
                 f"{MAX_ENTROPY:.4f} bits/char")
    lines.append("groups       : market n in {2,3,5} + B1 ideal-password "
                 "(no HKDF) + B2 ideal-IKM")
    lines.append(f"cell layout  : 6 validation months (2025-10..2026-03) "
                 f"x {pw_per_cell} passwords/cell")
    lines.append("")
    header = (f"{'group':<22}{'cells':>6}{'chi2 pass':>11}"
              f"{'chi2 p-value range':>24}{'entropy median [min,max]':>30}")
    lines.append(header)
    lines.append("-" * len(header))
    for g in order:
        s = summary[g]
        prange = f"[{s['chi2_p_min']:.3g}, {s['chi2_p_max']:.3g}]"
        erange = (f"{s['entropy_median']:.4f} "
                  f"[{s['entropy_min']:.4f}, {s['entropy_max']:.4f}]")
        lines.append(f"{s['label']:<22}{s['cells']:>6}"
                     f"{str(s['chi2_pass']) + '/' + str(s['cells']):>11}"
                     f"{prange:>24}{erange:>30}")
    lines.append("-" * len(header))
    lines.append("")
    lines.append("Results (computed this run)")
    lines.append("-" * 78)
    lines.append(f"chi-square      : {all_pass}/{all_cells} cells pass "
                 f"at alpha = {ALPHA}")
    lines.append(f"  failure(s)    : {flist}"
                 + (f"   [{fail_tag}]" if fail_tag else ""))
    lines.append(f"Shannon entropy : per-char median {median_ent_per_char:.4f}, "
                 f"range [{ent_lo:.4f}, {ent_hi:.4f}]")
    lines.append(f"                  per {pw_length}-char password "
                 f"~{ent_obs_per_pw:.1f} bits "
                 f"(theoretical {ent_theo_per_pw:.2f})")
    lines.append(f"expand fallback : {n_fallback}/{hkdf_pw_total} HKDF passwords "
                 f"(histogram -- {hkdf_hist})")
    lines.append(f"Exp 4 cross-ref : sub-tests failing >=1 month   "
                 f"n2 {upstream['n2']}/29  n3 {upstream['n3']}/29  "
                 f"n5 {upstream['n5']}/29")
    lines.append(f"                  prototype chi-square pass     "
                 f"n2 {summary['n2']['chi2_pass']}/6  "
                 f"n3 {summary['n3']['chi2_pass']}/6  "
                 f"n5 {summary['n5']['chi2_pass']}/6  "
                 f"B1 {summary['b1']['chi2_pass']}/6  "
                 f"B2 {summary['b2']['chi2_pass']}/6")
    lines.append("")
    if samples:
        lines.append(f"Sample passwords (market {DISPLAY_CELL[0]}, "
                     f"{DISPLAY_CELL[1]} -- first {len(samples)} of "
                     f"{pw_per_cell}):")
        for pw in samples:
            lines.append(f"  {pw}")
        lines.append("")
    summary_txt = "\n".join(lines) + "\n"
    (EVAL_DIR / "prototype_summary.txt").write_text(summary_txt)

    # ---- figures ------------------------------------------------------------
    heatmap = figure_position_heatmap(cells)
    sidebyside = figure_side_by_side(rows)

    print(summary_txt)
    print(f"per-cell CSV : {csv_path.relative_to(REPO)}")
    print(f"summary      : {(EVAL_DIR / 'prototype_summary.txt').relative_to(REPO)}")
    print(f"analysis     : {(EVAL_DIR / 'prototype_analysis.txt').relative_to(REPO)}"
          f"  (hand-maintained -- not regenerated)")
    if heatmap:
        print(f"heatmap      : {heatmap.relative_to(REPO)}")
    print(f"eval figure  : {sidebyside.relative_to(REPO)}")


if __name__ == "__main__":
    main()
