from __future__ import annotations

"""
Sanity check runner for Experiment 3.

Generates K random bit streams from /dev/urandom at each sanity bracket
(5K / 10K / 25K / 50K / 100K), runs `full_battery()` on each, and tallies
the per-(sub_test, bracket) type-I error rate at α = 0.01.

A (sub_test, bracket) cell is `passed_sanity = True` iff its measured
type-I rate stays ≤ 2 % (threshold from plan §1.4, aligned with Onofri).
This matrix is then joined by the Exp 3 main runner to mark verdicts as
N/A on cells where the sub-test isn't trustworthy at that length.

Run from project root:
    python scripts/runner_exp3_sanity_check.py

Configuration is the UPPERCASE constants at the top. To do a quick
smoke pass (~1 minute), edit `K = 10` and re-run.

Parallelism: trials within a bracket run on a ProcessPool of MAX_WORKERS
processes. Brackets are processed sequentially so the 100K bracket can
saturate all cores without contending with shorter brackets.

Expected wall-clock for K = 1000, MAX_WORKERS = 5 (≈4.5x single-thread):
    5K   ≈ 0.3 min
    10K  ≈ 0.5 min
    25K  ≈ 1.2 min
    50K  ≈ 2.5 min
    100K ≈ 5 min
    ---- total ≈ 9.5 min
"""

# BLAS thread limits must be set BEFORE numpy is imported, otherwise the
# outer ProcessPool × inner BLAS threads oversubscribe the CPU and slow
# everything down. Workers inherit these env vars.
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")  # macOS Accelerate

import secrets
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nist_extended import (
    ALL_SUB_TESTS,
    SANITY_BRACKETS,
    full_battery,
)

MAX_WORKERS = 5
CHUNKSIZE = 50  # Tune for better progress reporting (smaller = more frequent updates, but more overhead)

# Configuration
K = 1000
ALPHA = 0.01
TYPE_I_THRESHOLD = 0.02
OUTPUT_PATH = Path(f"data/processed/experiment3/sanity_check_validity_matrix-k{K}.csv")


def sample_urandom_bits(n: int) -> np.ndarray:
    """Get n bits from /dev/urandom as a uint8 ndarray of {0, 1}."""
    raw = secrets.token_bytes((n + 7) // 8)
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:n].astype(np.uint8)


def _run_one_trial(n_bits: int) -> list[str]:
    """Worker: one trial. Returns names of sub-tests whose p < ALPHA."""
    bits = sample_urandom_bits(n_bits)
    result = full_battery(bits)
    return [name for name, (p, _) in result.items() if p < ALPHA]


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[config] K={K}, α={ALPHA}, type-I threshold={TYPE_I_THRESHOLD}")
    print(f"[config] workers={MAX_WORKERS}, chunksize={CHUNKSIZE}")
    print(f"[config] brackets: {[label for _, label in SANITY_BRACKETS]}")
    print(f"[config] sub-tests ({len(ALL_SUB_TESTS)}): {ALL_SUB_TESTS}")
    print(f"[config] output: {output_path}")

    rows: list[dict] = []
    total_start = time.perf_counter()

    for n_bits, label in SANITY_BRACKETS:
        print(f"\n[{label}] starting K={K} trials at n={n_bits}")
        fail_counts = {sub_test: 0 for sub_test in ALL_SUB_TESTS}
        bracket_start = time.perf_counter()

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            iterator = executor.map(
                _run_one_trial,
                [n_bits] * K,
                chunksize=CHUNKSIZE,
            )
            for k, failed in enumerate(iterator):
                for sub_test in failed:
                    fail_counts[sub_test] += 1

                if (k + 1) % 100 == 0:
                    elapsed = time.perf_counter() - bracket_start
                    rate = (k + 1) / elapsed
                    eta = (K - k - 1) / rate if rate > 0 else 0.0
                    print(
                        f"  [{label}] {k+1}/{K}  "
                        f"({elapsed/60:.1f}min elapsed, ~{eta/60:.1f}min remaining)"
                    )

        bracket_elapsed = time.perf_counter() - bracket_start
        print(f"[{label}] done in {bracket_elapsed/60:.1f}min")

        for sub_test in ALL_SUB_TESTS:
            type_I_rate = fail_counts[sub_test] / K
            rows.append(
                {
                    "sub_test": sub_test,
                    "bracket": label,
                    "type_I_rate": type_I_rate,
                    "passed_sanity": type_I_rate <= TYPE_I_THRESHOLD,
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\n[saved] {output_path}")

    total_elapsed = time.perf_counter() - total_start
    print(f"[time] total: {total_elapsed/60:.1f}min")

    # Pivot for visual inspection
    print("\nPassed sanity (sub-test × bracket):")
    pivot = df.pivot(
        index="sub_test", columns="bracket", values="passed_sanity"
    ).reindex(ALL_SUB_TESTS)[[label for _, label in SANITY_BRACKETS]]
    print(pivot.to_string())


if __name__ == "__main__":
    main()
