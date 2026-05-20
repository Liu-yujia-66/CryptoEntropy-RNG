"""
Experiment 4 smoke test: src.fusion XOR-then-aggregate sanity check.

Builds the n=2 fused stream for DOGEUSDT + ETHUSDT on 2025-01, prints
the diagnostic dict, hand-verifies a few XOR positions, and asserts
loose sanity bounds. Override subset / month from the CLI to spot-check
any single (subset, month) cell.

Run from the project root (where INPUT_ROOT resolves by default, same
convention as runner_exp2_all_offset_1sbars.py):
    python scripts/smoke_exp4_fusion.py

Override examples:
    python scripts/smoke_exp4_fusion.py --subset DOGEUSDT,ETHUSDT,SOLUSDT --month 2025-06
    CRYPTOENTROPY_INPUT_ROOT=/path/to/aggTrades python scripts/smoke_exp4_fusion.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.fusion import build_fused_stream, build_per_asset_signs


DEFAULT_INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument(
        "--subset",
        default="DOGEUSDT,ETHUSDT",
        help="comma-separated asset list (default: DOGEUSDT,ETHUSDT)",
    )
    parser.add_argument(
        "--month",
        default="2025-01",
        help="YYYY-MM month label (default: 2025-01)",
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help=f"aggTrades root (default: {DEFAULT_INPUT_ROOT})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="optional aggTrades row cap per file (default: full month)",
    )
    args = parser.parse_args()

    subset = [s.strip() for s in args.subset.split(",") if s.strip()]
    if len(subset) < 2:
        print(f"[fatal] need at least 2 assets, got {subset}")
        return 1

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"[fatal] input root does not exist: {input_root}")
        print(
            "        set CRYPTOENTROPY_INPUT_ROOT or pass --input-root to override"
        )
        return 1

    print(f"=== smoke: n={len(subset)} subset={subset} month={args.month} ===")
    print(f"input_root: {input_root}")
    print()

    # Run fusion
    fused = build_fused_stream(
        subset=subset,
        month_label=args.month,
        input_root=input_root,
        max_rows=args.max_rows,
    )

    print("--- diagnostic dict ---")
    print(f"raw_seconds:                       {fused.raw_seconds:>10,}")
    print(f"kept_seconds:                      {fused.kept_seconds:>10,}")
    print(f"survival_rate:                     {fused.survival_rate:>10.4f}")
    print(f"naive_baseline (0.85^n):           {fused.naive_baseline:>10.4f}")
    print(
        f"empirical_independent_baseline:    {fused.empirical_independent_baseline:>10.4f}"
    )
    print(
        f"survival_vs_naive_ratio:           {fused.survival_vs_naive_ratio:>10.4f}"
    )
    print(
        f"survival_vs_empirical_ratio:       {fused.survival_vs_empirical_ratio:>10.4f}"
    )
    print(f"fused_bits.size:                   {fused.fused_bits.size:>10,}")
    print(f"fused_bits.dtype:                  {str(fused.fused_bits.dtype):>10}")
    if fused.fused_bits.size > 0:
        print(f"p(1):                              {fused.fused_bits.mean():>10.4f}")
    print()

    print("--- per_asset_zero_delta_rate (on intersection) ---")
    for asset, rate in fused.per_asset_zero_delta_rate.items():
        print(f"  {asset:<10}  {rate:.4f}")
    print()

    print("--- per_asset_coverage (full asset range, NOT intersection) ---")
    for asset, cov in fused.per_asset_coverage.items():
        print(f"  {asset:<10}  {cov:.4f}")
    print()

    print("--- per_asset_p1 (P(sign=+1 | kept), the marginal XOR input bias) ---")
    for asset, p1 in fused.per_asset_p1.items():
        print(f"  {asset:<10}  {p1:.4f}")
    print()

    print("--- pairwise correlation / 1-bit MI on kept positions ---")
    print(f"  {'pair':<22}  {'rho':>8}  {'MI (bits)':>10}")
    for pair, rho in fused.pairwise_correlation.items():
        mi = fused.pairwise_mi_1bit[pair]
        label = f"{pair[0]} / {pair[1]}"
        print(f"  {label:<22}  {rho:>8.4f}  {mi:>10.5f}")
    print()

    # Hand-verify XOR on a few positions
    print("--- hand-verified XOR (first 10 kept positions) ---")
    per_asset = [
        build_per_asset_signs(asset, args.month, input_root, max_rows=args.max_rows)
        for asset in subset
    ]
    start_s = max(int(p.epoch_s[0]) for p in per_asset)
    sliced_bits_per_asset: list[np.ndarray] = []
    for p in per_asset:
        offset = start_s - int(p.epoch_s[0])
        sliced = p.signs[offset : offset + fused.raw_seconds]
        sliced_bits_per_asset.append((sliced[fused.keep_mask] > 0).astype(np.uint8))

    n_check = min(10, fused.fused_bits.size)
    header = "idx | " + " ".join(f"{a[:6]:>6}" for a in subset) + " | XOR | fused"
    print(header)
    print("-" * len(header))
    all_match = True
    for i in range(n_check):
        bits_at_i = [int(arr[i]) for arr in sliced_bits_per_asset]
        manual_xor = 0
        for b in bits_at_i:
            manual_xor ^= b
        fused_at_i = int(fused.fused_bits[i])
        match = manual_xor == fused_at_i
        if not match:
            all_match = False
        line = (
            f"{i:>3} | "
            + " ".join(f"{b:>6}" for b in bits_at_i)
            + f" | {manual_xor:>3} | {fused_at_i:>5}"
            + ("" if match else "  <-- MISMATCH")
        )
        print(line)
    print()

    # Assertions
    print("--- sanity assertions ---")
    checks = []

    checks.append(
        ("fused_bits.size == kept_seconds", fused.fused_bits.size == fused.kept_seconds)
    )
    checks.append(("fused_bits.dtype == uint8", fused.fused_bits.dtype == np.uint8))
    checks.append(
        (
            f"survival_rate in [0.30, 0.95] (got {fused.survival_rate:.4f})",
            0.30 <= fused.survival_rate <= 0.95,
        )
    )
    if fused.fused_bits.size > 0:
        p1 = float(fused.fused_bits.mean())
        # The XOR output p(1) drifts from 0.5 whenever the inputs are biased
        # or correlated; the wide [0.20, 0.80] band only flags gross failures
        # like all-zero / all-one output. Read per_asset_p1 and
        # pairwise_correlation above to diagnose any drift from 0.5.
        checks.append(
            (
                f"p(1) in [0.20, 0.80] (got {p1:.4f})",
                0.20 <= p1 <= 0.80,
            )
        )
    checks.append(("hand-verified XOR matches fused_bits", all_match))

    failed = 0
    for label, ok in checks:
        marker = "[OK] " if ok else "[FAIL]"
        print(f"  {marker} {label}")
        if not ok:
            failed += 1

    print()
    if failed == 0:
        print("smoke test passed")
        return 0
    print(f"smoke test FAILED: {failed} of {len(checks)} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
