from __future__ import annotations

"""
Sanity check runner for Experiment 3 (extended battery, incl. TestU01 Alphabit).

Generates K random bit streams from /dev/urandom at each sanity bracket
(5K / 10K / 25K / 50K / 100K), runs full_battery() on each, and tallies the
per-(sub_test, bracket) outcome into the sanity validity matrix.

THREE-STATE OUTCOME. The previous runner only counted
sub-tests that FAILED (p < alpha). That silently mishandled TestU01 Alphabit:
TestU01 skips its longer-block sub-tests at short lengths (11 of the 17
Alphabit sub-tests run at 5K bits, 16 at 10K-50K, 17 at 100K). A skipped
sub-test never appeared in any trial's results, so its fail count stayed 0,
its type-I rate computed to 0, and it was wrongly marked "passed sanity". The
12 fixed sub-tests (stats.py + nistrng) always run, so they were unaffected;
only Alphabit exposed the bug.

Each (sub_test, bracket) cell now gets a `status`:
    not_run  -- the sub-test ran in 0 trials at this bracket (TestU01 length
                eligibility). This is NOT a sanity pass.
    passed   -- ran in every trial; type-I rate <= TYPE_I_THRESHOLD.
    failed   -- ran in every trial; type-I rate above the threshold.
`passed_sanity` is kept as a bool column (for the downstream join in
runner_exp3_battery.py) and is True iff status == "passed".

PER-BRACKET CAVEAT. Each bracket is probed at its LOWER BOUND length (5000,
10000, ...). Alphabit's eligibility steps fall *inside* brackets (e.g.
MultinomialBitsOver L=16 switches on somewhere in (5000, 10000)). Probing the
lower bound is the conservative choice: a real Exp 3 cell in the upper part of
a bracket may run a sub-test this matrix marks "not_run", so that cell's data
for the sub-test is discarded -- conservative, never the reverse.

Alphabit is batched: each worker task runs run_alphabit_batch() once for its
whole chunk of trials (a single alphabit_driver subprocess), then
full_battery(..., alphabit_pvals=...) per stream. Requires tools/alphabit_driver
(build: `bash tools/build_testu01.sh && make -C tools`); override its path with
the ALPHABIT_DRIVER environment variable.

PROCESS ISOLATION PER BRACKET. Running all 5 brackets in a single
Python process accumulated something across brackets that reliably SIGKILLed
on 100K (driver / TestU01 / Python wrapper state leak). The default entry-point
fixes this by spawning ONE fresh Python subprocess per bracket and
concatenating the per-bracket CSVs. Each subprocess gets a clean slate, so no
inter-bracket carry-over is possible.

Run from project root:
    python scripts/runner_exp3_sanity_check.py                  # all brackets
    python scripts/runner_exp3_sanity_check.py --bracket 100K   # one bracket
    python scripts/runner_exp3_sanity_check.py --force          # ignore cache

Resume: a bracket whose per-bracket CSV already exists is SKIPPED, so a re-run
after a partial failure only redoes the missing bracket(s) and then
concatenates; --force recomputes every bracket. All outputs (the final matrix
and the per-bracket partials) go to data/processed/experiment3/sanity_check/.

Quick smoke pass (~1 min): SANITY_K=10 python scripts/runner_exp3_sanity_check.py
"""

# BLAS thread limits must be set BEFORE numpy is imported, otherwise the outer
# ProcessPool x inner BLAS threads oversubscribe the CPU. Workers inherit them.
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")  # macOS Accelerate

import argparse
import secrets
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.battery import ALL_SUB_TESTS, SANITY_BRACKETS, full_battery
from src.testu01_alphabit import run_alphabit_batch

# Label -> bit count, used for argparse choices and bracket lookup.
_BRACKET_BY_LABEL: dict[str, int] = {lab: n for n, lab in SANITY_BRACKETS}

# Configuration
MAX_WORKERS = 5
# K is the trials per bracket. Override with SANITY_K for a quick smoke pass;
# the value is embedded in the output filename so a smoke run (e.g. K=10) does
# not overwrite the full K=1000 matrix.
K = int(os.environ.get("SANITY_K", "1000"))
ALPHA = 0.01
TYPE_I_THRESHOLD = 0.02
# Trials per worker task = streams per Alphabit driver subprocess. Batching
# this many trials amortises driver process startup while keeping enough
# tasks (K / TRIALS_PER_CHUNK) to spread across MAX_WORKERS.
TRIALS_PER_CHUNK = 50
OUTPUT_DIR = Path("data/processed/experiment3/sanity_check")
FINAL_OUTPUT_PATH = OUTPUT_DIR / f"sanity_validity_matrix-k{K}.csv"


def _per_bracket_path(label: str) -> Path:
    """Per-bracket partial CSV; concatenated at the end into FINAL_OUTPUT_PATH."""
    return OUTPUT_DIR / f"sanity_validity_matrix-k{K}_{label}.csv"


def sample_urandom_bits(n: int) -> np.ndarray:
    """Get n bits from /dev/urandom as a uint8 ndarray of {0, 1}."""
    raw = secrets.token_bytes((n + 7) // 8)
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:n].astype(np.uint8)


def _run_chunk(args: tuple[int, int]) -> tuple[dict[str, int], dict[str, int]]:
    """Worker: run `n_trials` sanity trials at `n_bits`.

    Alphabit is run once for the whole chunk (one driver subprocess) via
    run_alphabit_batch(); the 12 fixed sub-tests run per stream.

    Returns (ran_counts, fail_counts): for each sub_test, how many of the
    chunk's trials it ran in, and how many of those it failed (p < ALPHA).
    A sub-test absent from a trial's full_battery() result (TestU01 did not
    run it) is simply not counted in `ran` -- that is how "not_run" is
    detected at the bracket level.
    """
    n_bits, n_trials = args
    streams = {f"t{i}": sample_urandom_bits(n_bits) for i in range(n_trials)}
    alpha_batch = run_alphabit_batch(streams)  # single driver subprocess

    ran: Counter = Counter()
    fail: Counter = Counter()
    for tid, bits in streams.items():
        result = full_battery(bits, alphabit_pvals=alpha_batch[tid])
        for name, (p, _valid) in result.items():
            ran[name] += 1
            if p < ALPHA:
                fail[name] += 1
    return dict(ran), dict(fail)


def _split_into_chunks(total: int, size: int) -> list[int]:
    """Split `total` trials into chunk sizes of at most `size`."""
    n_full, rem = divmod(total, size)
    return [size] * n_full + ([rem] if rem else [])


def _preflight_driver() -> None:
    """Fail fast with a clear message if alphabit_driver is missing."""
    print("[preflight] checking alphabit_driver ...", end=" ", flush=True)
    try:
        run_alphabit_batch({"_preflight": sample_urandom_bits(2000)})
    except FileNotFoundError as exc:
        print("FAILED")
        print(f"\n{exc}", file=sys.stderr)
        sys.exit(1)
    print("OK")


def run_one_bracket(label: str) -> Path:
    """Run K trials at the given bracket and write the per-bracket CSV.

    Always invoked in its own fresh Python process (either directly via
    `--bracket`, or as a subprocess from the top-level dispatcher).
    """
    project_root = Path(__file__).resolve().parent.parent
    if label not in _BRACKET_BY_LABEL:
        sys.exit(f"unknown bracket {label!r}; valid: {list(_BRACKET_BY_LABEL)}")
    n_bits = _BRACKET_BY_LABEL[label]
    out_path = project_root / _per_bracket_path(label)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[config] K={K}  alpha={ALPHA}  type-I<={TYPE_I_THRESHOLD}  "
        f"workers={MAX_WORKERS}  chunk={TRIALS_PER_CHUNK}\n"
        f"[config] bracket={label} (n={n_bits})  "
        f"sub-tests={len(ALL_SUB_TESTS)}\n"
        f"[config] -> {out_path}"
    )

    _preflight_driver()

    chunk_sizes = _split_into_chunks(K, TRIALS_PER_CHUNK)
    tasks = [(n_bits, c) for c in chunk_sizes]
    print(f"\n[{label}] K={K} trials at n={n_bits}, {len(tasks)} chunk(s)")
    bracket_start = time.perf_counter()

    ran_total: Counter = Counter()
    fail_total: Counter = Counter()
    done_trials = 0
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for chunk_size, (ran, fail) in zip(
            chunk_sizes, executor.map(_run_chunk, tasks)
        ):
            ran_total.update(ran)
            fail_total.update(fail)
            done_trials += chunk_size
            elapsed = time.perf_counter() - bracket_start
            rate = done_trials / elapsed if elapsed > 0 else 0.0
            eta = (K - done_trials) / rate if rate > 0 else 0.0
            print(
                f"  [{label}] {done_trials}/{K}  "
                f"({elapsed/60:.1f}min elapsed, ~{eta/60:.1f}min remaining)"
            )

    bracket_elapsed = time.perf_counter() - bracket_start
    print(f"[{label}] done in {bracket_elapsed/60:.1f}min")

    rows: list[dict] = []
    for st in ALL_SUB_TESTS:
        n_ran = ran_total.get(st, 0)
        n_fail = fail_total.get(st, 0)
        if n_ran == 0:
            status, type_I = "not_run", float("nan")
        else:
            type_I = n_fail / n_ran
            status = "passed" if type_I <= TYPE_I_THRESHOLD else "failed"
            # Eligibility is deterministic in n_bits, so a sub-test should
            # run in all K trials or none. Anything else is unexpected.
            if n_ran != K:
                print(
                    f"  [WARN] {st} @ {label}: ran in {n_ran}/{K} trials "
                    f"(expected 0 or {K}); type-I computed over {n_ran}."
                )
        rows.append(
            {
                "sub_test": st,
                "bracket": label,
                "status": status,
                "n_ran": n_ran,
                "n_fail": n_fail,
                "type_I_rate": type_I,
                "passed_sanity": status == "passed",
            }
        )
    counts = Counter(r["status"] for r in rows)
    print(
        f"[{label}] passed={counts['passed']}  failed={counts['failed']}  "
        f"not_run={counts['not_run']}"
    )

    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"[saved] {out_path}")
    return out_path


def run_all_brackets(force: bool = False) -> None:
    """Spawn one fresh Python subprocess per bracket, then concat results.

    Fresh-process-per-bracket is the workaround for the (unidentified)
    cumulative-state SIGKILL at 100K when 5 brackets ran in one process. Each
    subprocess gets a clean slate.

    Resume: a bracket whose per-bracket CSV already exists is SKIPPED and its
    earlier result reused. So after a partial failure, just re-run -- only the
    missing bracket(s) are recomputed, then everything is concatenated. Pass
    `force=True` (--force) to ignore existing CSVs and recompute every bracket.
    """
    project_root = Path(__file__).resolve().parent.parent
    final_path = project_root / FINAL_OUTPUT_PATH
    final_path.parent.mkdir(parents=True, exist_ok=True)

    bracket_labels = [label for _, label in SANITY_BRACKETS]
    print(
        f"[dispatch] {len(bracket_labels)} brackets, one subprocess each: "
        f"{bracket_labels}  (force={force})"
    )
    print(f"[dispatch] final concat -> {final_path}\n")

    total_start = time.perf_counter()
    per_bracket_paths: list[Path] = []
    for label in bracket_labels:
        bracket_csv = project_root / _per_bracket_path(label)
        if bracket_csv.exists() and not force:
            print(
                f"========== bracket {label}: SKIP "
                f"(per-bracket CSV exists; --force to redo) ==========\n"
            )
            per_bracket_paths.append(bracket_csv)
            continue
        print(f"========== bracket {label} ==========")
        cmd = [sys.executable, str(Path(__file__).resolve()), "--bracket", label]
        # child inherits the environment (SANITY_K, ALPHABIT_DRIVER, ...)
        proc = subprocess.run(cmd, env={**os.environ})
        if proc.returncode != 0:
            sys.exit(
                f"[FATAL] subprocess for bracket {label} exited "
                f"with code {proc.returncode}"
            )
        per_bracket_paths.append(bracket_csv)
        print()

    # Concat per-bracket CSVs into FINAL_OUTPUT_PATH.
    dfs = [pd.read_csv(p) for p in per_bracket_paths]
    df = pd.concat(dfs, ignore_index=True)
    df.to_csv(final_path, index=False)
    print(f"[saved] {final_path}  ({len(df)} rows)")

    total_elapsed = time.perf_counter() - total_start
    print(f"[time] total: {total_elapsed/60:.1f}min")

    print("\nStatus (sub-test x bracket):")
    pivot = df.pivot(index="sub_test", columns="bracket", values="status").reindex(
        ALL_SUB_TESTS
    )[bracket_labels]
    print(pivot.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run /dev/urandom sanity trials at each bracket; produce "
        "the three-state (sub_test x bracket) validity matrix."
    )
    parser.add_argument(
        "--bracket",
        choices=list(_BRACKET_BY_LABEL),
        help="run only this bracket; writes a per-bracket CSV. Without this "
        "flag the runner dispatches one subprocess per bracket and "
        "concatenates the partial CSVs into the final matrix.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recompute every bracket even if its per-bracket CSV already "
        "exists (default: reuse existing per-bracket CSVs).",
    )
    args = parser.parse_args()
    if args.bracket is not None:
        run_one_bracket(args.bracket)
    else:
        run_all_brackets(force=args.force)


if __name__ == "__main__":
    main()
