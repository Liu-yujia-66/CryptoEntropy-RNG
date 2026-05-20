"""
Experiment 4 — min-entropy assessment of the validation fused streams.

Reads the 24 deployment streams written by runner_exp4_validation.py
(validation/n{N}/{month}/fused_stream.bin, one witness-offset stream
per (n, validation month)) and runs the NIST SP 800-90B two-estimator
subset from src.min_entropy: Most Common Value (Sec 6.3.1) and Markov
(Sec 6.3.3). Per-bit min-entropy H_inf = min(MCV, Markov).

Why this matters: HKDF-Extract produces a key indistinguishable from
uniform at a security level equal to the IKM min-entropy, NOT at a
level implied by statistical-test pass rates. A fused stream can pass
the +Runs gate yet carry less than 1 bit of min-entropy per bit; this
runner quantifies that gap and derives the IKM byte length the
Prototype needs so a 256-bit-strength password is achievable.

Outputs land under data/processed/experiment4/min_entropy/:

  min_entropy_per_cell.csv   one row per (n, month): H_inf MCV / Markov
                             / min, fused-stream length, derived IKM
                             bytes for 256-bit security
  min_entropy_summary.json   per-n median H_inf + recommended IKM
                             length + the binding estimator

Run from the project root after runner_exp4_validation.py:
    python scripts/runner_exp4_min_entropy.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.min_entropy import estimate_min_entropy, ikm_bytes_for_security


DEFAULT_VALIDATION_ROOT = Path("data/processed/experiment4/validation")
DEFAULT_OUTPUT_ROOT = Path("data/processed/experiment4/min_entropy")
TARGET_SECURITY_BITS = 256


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_fused_stream(path: Path) -> np.ndarray:
    """Load a fused_stream.bin written via numpy uint8 .tobytes()."""
    bits = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    # Defensive: the file should hold only {0, 1}.
    if bits.size and bits.max() > 1:
        raise ValueError(
            f"{path}: contains values > 1 (max={bits.max()}); "
            "expected a {0,1} bit stream"
        )
    return bits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experiment 4 min-entropy assessment (NIST SP 800-90B "
        "MCV + Markov) on the validation fused streams."
    )
    parser.add_argument(
        "--validation-root",
        default=str(DEFAULT_VALIDATION_ROOT),
        help=f"(default: {DEFAULT_VALIDATION_ROOT})",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=f"(default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--target-security-bits",
        type=int,
        default=TARGET_SECURITY_BITS,
        help=f"(default: {TARGET_SECURITY_BITS})",
    )
    args = parser.parse_args()

    validation_root = Path(args.validation_root)
    summary_path = validation_root / "validation_summary.json"
    if not summary_path.exists():
        print(f"[fatal] missing {summary_path}")
        print("        run scripts/runner_exp4_validation.py first")
        return 1
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    summary = json.loads(summary_path.read_text())
    n_values = summary["n_values"]
    months = summary["validation_months"]
    subset_picks = summary["subset_picks"]

    print("=== exp4 min-entropy assessment ===")
    print(f"validation root : {validation_root}")
    print(f"n values        : {n_values}")
    print(f"months          : {months[0]}..{months[-1]} ({len(months)} months)")
    print(f"target security : {args.target_security_bits} bits")
    print(f"estimators      : NIST SP 800-90B MCV (6.3.1) + Markov (6.3.3)")
    print()

    rows: list[dict] = []
    for n in n_values:
        subset_label = "+".join(subset_picks[str(n)]["subset"])
        for month in months:
            bin_path = validation_root / f"n{n}" / month / "fused_stream.bin"
            if not bin_path.exists():
                print(f"[warn] missing {bin_path}; skipping")
                continue
            bits = _load_fused_stream(bin_path)
            est = estimate_min_entropy(bits)
            h_min = est["h_inf_min"]
            ikm_bytes = ikm_bytes_for_security(h_min, args.target_security_bits)
            binding = (
                "MCV"
                if est["h_inf_mcv"] <= est["h_inf_markov"]
                else "Markov"
            )
            rows.append(
                {
                    "n": n,
                    "subset": subset_label,
                    "month": month,
                    "stream_bits": int(bits.size),
                    "h_inf_mcv": est["h_inf_mcv"],
                    "h_inf_markov": est["h_inf_markov"],
                    "h_inf_min": h_min,
                    "binding_estimator": binding,
                    "total_min_entropy_bits": h_min * bits.size,
                    "ikm_bytes_for_target": ikm_bytes,
                }
            )
            print(
                f"  n={n} {month}: bits={bits.size:>8,}  "
                f"MCV={est['h_inf_mcv']:.4f}  Markov={est['h_inf_markov']:.4f}  "
                f"H_inf={h_min:.4f} ({binding})  "
                f"IKM>={ikm_bytes}B"
            )

    if not rows:
        print("[fatal] no fused streams found")
        return 1

    per_cell = pd.DataFrame(rows)
    per_cell_path = output_root / "min_entropy_per_cell.csv"
    per_cell.to_csv(per_cell_path, index=False)

    # ---- per-n summary ----
    per_n_summary: dict[str, dict] = {}
    for n in n_values:
        sub = per_cell[per_cell["n"] == n]
        if sub.empty:
            continue
        h_min_median = float(sub["h_inf_min"].median())
        h_min_worst = float(sub["h_inf_min"].min())
        # IKM length: size to the WORST month so every month clears 256 bits.
        ikm_bytes_worst = ikm_bytes_for_security(
            h_min_worst, args.target_security_bits
        )
        ikm_bytes_median = ikm_bytes_for_security(
            h_min_median, args.target_security_bits
        )
        per_n_summary[str(n)] = {
            "n": n,
            "subset": "+".join(subset_picks[str(n)]["subset"]),
            "h_inf_mcv_median": float(sub["h_inf_mcv"].median()),
            "h_inf_markov_median": float(sub["h_inf_markov"].median()),
            "h_inf_min_median": h_min_median,
            "h_inf_min_worst_month": h_min_worst,
            "ikm_bytes_median_case": ikm_bytes_median,
            "ikm_bytes_worst_case": ikm_bytes_worst,
            "n_months": int(len(sub)),
        }

    payload = {
        "target_security_bits": args.target_security_bits,
        "estimators": ["NIST SP800-90B 6.3.1 MCV", "NIST SP800-90B 6.3.3 Markov"],
        "h_inf_rule": "min(MCV, Markov) per cell; conservative lower bound",
        "per_n_summary": per_n_summary,
        "overall_h_inf_min_worst": float(per_cell["h_inf_min"].min()),
        "overall_h_inf_min_median": float(per_cell["h_inf_min"].median()),
        "recommended_ikm_bytes_global_worst": ikm_bytes_for_security(
            float(per_cell["h_inf_min"].min()), args.target_security_bits
        ),
    }
    summary_out = output_root / "min_entropy_summary.json"
    summary_out.write_text(json.dumps(payload, indent=2))

    # ---- console summary ----
    print()
    print("=== per-n summary ===")
    print(
        f"  {'n':>2}  {'subset':<26}  {'MCV_med':>8}  {'Mkv_med':>8}  "
        f"{'Hinf_med':>9}  {'Hinf_wst':>9}  {'IKM_med':>8}  {'IKM_wst':>8}"
    )
    print("  " + "-" * 92)
    for n in n_values:
        s = per_n_summary.get(str(n))
        if s is None:
            continue
        print(
            f"  {n:>2}  {s['subset']:<26}  "
            f"{s['h_inf_mcv_median']:>8.4f}  {s['h_inf_markov_median']:>8.4f}  "
            f"{s['h_inf_min_median']:>9.4f}  {s['h_inf_min_worst_month']:>9.4f}  "
            f"{s['ikm_bytes_median_case']:>7}B  {s['ikm_bytes_worst_case']:>7}B"
        )
    print()
    print(
        f"overall worst-month H_inf : {payload['overall_h_inf_min_worst']:.4f} bit/bit"
    )
    print(
        f"global worst-case IKM     : {payload['recommended_ikm_bytes_global_worst']} bytes "
        f"for {args.target_security_bits}-bit security"
    )
    print()
    print(f"outputs:\n  {per_cell_path}\n  {summary_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
