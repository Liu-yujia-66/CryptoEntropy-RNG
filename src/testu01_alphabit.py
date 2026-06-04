from __future__ import annotations

"""
TestU01 Alphabit wrapper (Experiment 3 / Experiment 4 extended battery).

Bridges the project's Python pipeline to the official TestU01 1.2.3 Alphabit
battery, via the compiled C batch driver at ``tools/alphabit_driver``.

Why a real C driver + subprocess, not a Python reimplementation: the value of
Alphabit as a cross-battery check is that it is an *external, independently
validated* implementation. A reimplementation would share this project's code
and lose that independence.

Pipeline per call:

    bit arrays  --numpy.packbits-->  packed .bin files  +  TSV manifest
                --subprocess------>  tools/alphabit_driver  -->  CSV
                --parse / map----->  {stream_id: {schema_name: p_value}}

Alphabit emits 17 p-values: TestU01 reports
RandomWalk1 as five statistics (H/M/J/R/C) per length, so the 9 Alphabit
"tests" of Onofri et al. (2025) expand to 4 + 2 + 1 + 5 + 5 = 17 result rows.
The 17 stable schema names are exported as ``ALPHABIT_SUB_TESTS``.

Bit format: input arrays hold values in {0, 1} (the same format as
``src/bitstream.py`` output). Do NOT pass -1/+1.

Driver location: ``<repo>/tools/alphabit_driver``, overridable with the
``ALPHABIT_DRIVER`` environment variable. Build it once with:

    bash tools/build_testu01.sh && make -C tools

Smoke test (needs the driver built):

    python src/testu01_alphabit.py
"""

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DRIVER = _REPO_ROOT / "tools" / "alphabit_driver"

# Raw TestU01 ``bbattery_TestNames`` strings -> CSV-friendly schema names.
# The raw strings are verbatim from TestU01 1.2.3. If TestU01's naming ever
# changes, _schema_name() flags the mismatch rather than dropping the result
# silently.
_RAW_TO_SCHEMA: dict[str, str] = {
    "MultinomialBitsOver, L = 2":  "Alphabit_MultinomialBitsOver_L2",
    "MultinomialBitsOver, L = 4":  "Alphabit_MultinomialBitsOver_L4",
    "MultinomialBitsOver, L = 8":  "Alphabit_MultinomialBitsOver_L8",
    "MultinomialBitsOver, L = 16": "Alphabit_MultinomialBitsOver_L16",
    "HammingIndep, L = 16":        "Alphabit_HammingIndep_L16",
    "HammingIndep, L = 32":        "Alphabit_HammingIndep_L32",
    "HammingCorr, L = 32":         "Alphabit_HammingCorr_L32",
    "RandomWalk1 H (L = 64)":      "Alphabit_RandomWalk1_L64_H",
    "RandomWalk1 M (L = 64)":      "Alphabit_RandomWalk1_L64_M",
    "RandomWalk1 J (L = 64)":      "Alphabit_RandomWalk1_L64_J",
    "RandomWalk1 R (L = 64)":      "Alphabit_RandomWalk1_L64_R",
    "RandomWalk1 C (L = 64)":      "Alphabit_RandomWalk1_L64_C",
    "RandomWalk1 H (L = 320)":     "Alphabit_RandomWalk1_L320_H",
    "RandomWalk1 M (L = 320)":     "Alphabit_RandomWalk1_L320_M",
    "RandomWalk1 J (L = 320)":     "Alphabit_RandomWalk1_L320_J",
    "RandomWalk1 R (L = 320)":     "Alphabit_RandomWalk1_L320_R",
    "RandomWalk1 C (L = 320)":     "Alphabit_RandomWalk1_L320_C",
}

# Canonical ordered list of the 17 Alphabit schema names. src/battery.py
# extends ALL_SUB_TESTS with this list (alongside the stats.py / nistrng
# slices).
ALPHABIT_SUB_TESTS: list[str] = list(_RAW_TO_SCHEMA.values())

# Alphabit's result count is a DETERMINISTIC function of the bit count
# (independent of the data): TestU01 itself skips its longer-block sub-tests
# at shorter lengths. Measured on TestU01 1.2.3:
#
#     bit count            results   sub-tests TestU01 skips
#     2000, 5000              11      MultinomialBitsOver_L16
#                                     + RandomWalk1_L320 (its 5 H/M/J/R/C stats)
#     10000, 25000, 50000     16      MultinomialBitsOver_L16
#     100000, 250000          17      -- (full battery)
#
# So a result dict with 11 or 16 entries is NORMAL length eligibility, not a
# driver error.

# Crash guard, NOT a policy floor. TestU01's Alphabit rounds the bit count
# down to a multiple of 32 and aborts the whole process if the result is 0
# (i.e. nb < 32). Streams shorter than this are skipped here so that one tiny
# stream cannot kill a whole batch. This is deliberately distinct from the
# framework floor (MIN_BIT_COUNT = 2000, enforced by the runners): this
# wrapper is a low-level tool and does not bake in framework policy.
_MIN_SAFE_BITS = 64


def _driver_path() -> Path:
    """Resolve the alphabit_driver binary; ALPHABIT_DRIVER env var overrides."""
    env = os.environ.get("ALPHABIT_DRIVER")
    return Path(env) if env else _DEFAULT_DRIVER


def _schema_name(raw: str) -> str:
    """Map a raw TestU01 test name to this project's schema name.

    Unknown names (e.g. from a different TestU01 version) are not dropped:
    they are sanitised, prefixed ``Alphabit_UNKNOWN_``, and flagged on stderr.
    """
    name = _RAW_TO_SCHEMA.get(raw)
    if name is not None:
        return name
    safe = "".join(c if c.isalnum() else "_" for c in raw).strip("_")
    print(f"[testu01_alphabit] WARNING: unrecognised TestU01 test name "
          f"{raw!r} -- check the TestU01 version.", file=sys.stderr)
    return f"Alphabit_UNKNOWN_{safe}"


def run_alphabit_batch(
    streams: dict[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    """Run the TestU01 Alphabit battery on many bit streams in one driver call.

    Batching matters: the driver pays the process-startup / library-load cost
    once for the whole batch instead of once per stream. Pass a whole Exp 3
    cell (its offset streams) or an Exp 4 fused-stream set at once.

    Parameters
    ----------
    streams:
        Mapping ``{stream_id -> bit array}``. Each array is 1-D with values in
        {0, 1} (any integer dtype). ``stream_id`` is used only as the result
        key -- it may contain commas, tabs, spaces, etc., because the manifest
        handed to the driver uses separate tab-free internal ids.

    Returns
    -------
    dict ``{stream_id -> {schema_name -> p_value}}``.
    Every input stream_id appears in the result. The inner dict has one of
    three shapes -- a downstream aggregator must treat shapes 2 and 3 as
    NORMAL, not as a driver error:

      1. empty {}          -- the stream was shorter than _MIN_SAFE_BITS and
                              was never handed to the driver.
      2. 11 or 16 entries  -- a normal stream: TestU01 itself skips its
                              longer-block sub-tests at shorter lengths
                              (length eligibility; see the measured table
                              above ALPHABIT_SUB_TESTS). 11 below ~10k bits,
                              16 below ~100k bits.
      3. 17 entries        -- a long stream (>= ~100k bits): the full battery.

    A p-value < 0 means TestU01 did not run that test; such rows are dropped
    here, which is what produces shape 2. This length eligibility is
    TestU01's own behaviour, not a bug.

    Raises
    ------
    FileNotFoundError
        if the alphabit_driver binary is missing.
    RuntimeError
        if the driver exits with an error, times out, or writes no output.
    """
    driver = _driver_path()
    if not driver.exists():
        raise FileNotFoundError(
            f"alphabit_driver not found at: {driver}\n"
            f"Build it once with:\n"
            f"  bash tools/build_testu01.sh && make -C tools\n"
            f"or set the ALPHABIT_DRIVER environment variable."
        )

    results: dict[str, dict[str, float]] = {sid: {} for sid in streams}
    if not streams:
        return results

    with tempfile.TemporaryDirectory(prefix="alphabit_") as td:
        tmp = Path(td)
        manifest = tmp / "manifest.tsv"
        out_csv = tmp / "out.csv"

        # Internal ids (s0, s1, ...) are tab/comma-free, so any caller key is
        # safe. id_map translates the driver's output back to caller keys.
        id_map: dict[str, str] = {}
        manifest_lines: list[str] = []
        for i, (sid, bits) in enumerate(streams.items()):
            arr = np.asarray(bits).ravel()
            n = int(arr.size)
            if n < _MIN_SAFE_BITS:
                continue  # results[sid] stays {}
            internal = f"s{i}"
            id_map[internal] = sid
            packed = np.packbits(arr.astype(np.uint8))
            bin_path = tmp / f"{internal}.bin"
            packed.tofile(bin_path)
            manifest_lines.append(f"{internal}\t{bin_path}\t{n}")

        if not manifest_lines:
            return results  # nothing long enough to test

        manifest.write_text("\n".join(manifest_lines) + "\n")

        # Defensive timeout. A legitimate batch finishes in well under 1 s per
        # stream even for the longest streams, so this budget leaves a wide
        # margin while still catching a genuine TestU01 hang (TestU01 can loop
        # on some pathological inputs).
        timeout_sec = 60.0 + 10.0 * len(manifest_lines)
        try:
            proc = subprocess.run(
                [str(driver), str(manifest), str(out_csv)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"alphabit_driver timed out after {timeout_sec:.0f}s on "
                f"{len(manifest_lines)} stream(s) -- possible TestU01 hang."
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"alphabit_driver exited with code {proc.returncode}:\n"
                f"{proc.stderr.strip()}"
            )
        if not out_csv.exists():
            raise RuntimeError("alphabit_driver produced no output CSV.")

        with out_csv.open(newline="") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # skip the "stream_id,test_name,p_value" header
            for row in reader:
                if len(row) != 3:
                    continue
                internal, raw_name, pval_str = row
                sid = id_map.get(internal)
                if sid is None:
                    continue
                try:
                    pval = float(pval_str)
                except ValueError:
                    continue
                results[sid][_schema_name(raw_name)] = pval

    return results


def run_alphabit(bits: np.ndarray) -> dict[str, float]:
    """Run Alphabit on a single bit stream.

    Convenience wrapper over :func:`run_alphabit_batch`. Returns
    ``{schema_name -> p_value}`` (empty if the stream was too short or
    untestable). For many streams, call :func:`run_alphabit_batch` directly
    so the driver runs once for the whole batch.
    """
    return run_alphabit_batch({"_single": bits})["_single"]


# Smoke test (run: python src/testu01_alphabit.py)
def _smoke_test() -> int:
    """Self-contained smoke test. Returns 0 on success, 1 on failure/skip."""
    driver = _driver_path()
    print("=" * 70)
    print("src/testu01_alphabit.py smoke test")
    print(f"driver: {driver}")
    print("=" * 70)

    if not driver.exists():
        print("[SKIP] alphabit_driver not built. Build it with:")
        print("  bash tools/build_testu01.sh && make -C tools")
        return 1

    rng = np.random.default_rng(20260521)
    streams = {
        "rand_a": rng.integers(0, 2, 100_000).astype(np.uint8),
        "rand_b": rng.integers(0, 2, 50_000).astype(np.uint8),
        "periodic": np.tile([0, 1], 50_000).astype(np.uint8),
        "too_short": rng.integers(0, 2, 10).astype(np.uint8),
    }
    res = run_alphabit_batch(streams)
    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> int:
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))
        return 0 if ok else 1

    # [1] every input id present
    failures += check("all stream ids returned",
                       set(res) == set(streams))

    # [2] random stream -> 17 results, all named, p in [0, 1]
    a = res["rand_a"]
    failures += check("rand_a has 17 results", len(a) == 17,
                      f"got {len(a)}")
    failures += check("rand_a names all in ALPHABIT_SUB_TESTS",
                      set(a).issubset(ALPHABIT_SUB_TESTS))
    failures += check("rand_a p-values in [0, 1]",
                      all(0.0 <= p <= 1.0 for p in a.values()),
                      f"range [{min(a.values()):.4f}, {max(a.values()):.4f}]"
                      if a else "empty")

    # [3] periodic stream -> rejected (most p-values ~ 0)
    per = res["periodic"]
    n_zero = sum(1 for p in per.values() if p < 1e-6)
    failures += check("periodic stream mostly rejected", n_zero >= 12,
                      f"{n_zero}/{len(per)} p-values ~ 0")

    # [4] too-short stream skipped -> empty dict
    failures += check("too_short -> empty dict", res["too_short"] == {})

    # [5] single-stream convenience entry point. The result count is
    #     n-dependent -- TestU01 drops its long-L tests on shorter streams
    #     (rand_b is 50k bits) -- so this checks structure, not an exact count.
    one = run_alphabit(streams["rand_b"])
    failures += check("run_alphabit single stream returns valid results",
                      1 <= len(one) <= 17
                      and set(one).issubset(ALPHABIT_SUB_TESTS),
                      f"{len(one)} results (count is n-dependent)")

    print("=" * 70)
    print("Smoke test PASSED" if failures == 0
          else f"Smoke test FAILED -- {failures} check(s) failed")
    print("=" * 70)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(_smoke_test())
