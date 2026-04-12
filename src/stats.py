from __future__ import annotations

"""
Shared statistical test functions for bitstream randomness analysis.

Covers basic NIST-style tests (monobit, runs), entropy measures, autocorrelation,
approximate entropy, and an entropy-based predictability test.
"""

import math
from itertools import groupby

import numpy as np
from scipy.special import gammaincc
from scipy.stats import chi2


# ---------------------------------------------------------------------------
# Basic measures
# ---------------------------------------------------------------------------

def shannon_entropy_from_bits(bits: np.ndarray) -> float:
    """Shannon entropy (bits) of a binary sequence."""
    if bits.size == 0:
        return float("nan")
    p1 = float(bits.mean())
    p0 = float(1.0 - p1)
    entropy = 0.0
    for p in (p0, p1):
        if p > 0:
            entropy -= p * math.log2(p)
    return float(entropy)


def count_runs(bits: np.ndarray) -> int:
    """Count the number of runs (maximal same-value subsequences) in a bitstream."""
    if bits.size == 0:
        return 0
    return 1 + int(np.count_nonzero(bits[1:] != bits[:-1]))


def run_lengths(bits: np.ndarray) -> list[int]:
    """Return the length of each run in a bitstream."""
    return [sum(1 for _ in group) for _, group in groupby(bits)]


def longest_run(bits: np.ndarray, value: int) -> int:
    """Return the length of the longest run of `value` (0 or 1) in a bitstream."""
    if bits.size == 0:
        return 0
    target = (bits == value).astype(np.int8)
    if target.sum() == 0:
        return 0
    padded = np.concatenate(([0], target, [0]))
    changes = np.diff(padded)
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    return int(np.max(ends - starts))


def lag_autocorrelation(bits: np.ndarray, lag: int) -> float:
    """Pearson autocorrelation of a bitstream at a given lag."""
    if lag <= 0 or lag >= bits.size:
        return float("nan")
    x = bits[:-lag].astype(float)
    y = bits[lag:].astype(float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


# ---------------------------------------------------------------------------
# NIST-style tests
# ---------------------------------------------------------------------------

def monobit_test(bits: np.ndarray) -> tuple[float, float]:
    """NIST frequency (monobit) test. Returns (z_score, p_value)."""
    n = bits.size
    if n == 0:
        return float("nan"), float("nan")
    s = 2 * int(bits.sum()) - int(n)
    z_score = float(abs(s) / math.sqrt(n))
    p_value = float(math.erfc(z_score / math.sqrt(2)))
    return float(z_score), float(p_value)


def runs_test(bits: np.ndarray) -> tuple[float, float]:
    """NIST runs test. Returns (z_score, p_value)."""
    n = bits.size
    if n < 2:
        return float("nan"), float("nan")
    n1 = int(bits.sum())
    n0 = n - n1
    if n0 == 0 or n1 == 0:
        return float("nan"), float("nan")

    runs = count_runs(bits)
    expected = float(1 + (2 * n1 * n0) / n)
    variance = float(2 * n1 * n0 * (2 * n1 * n0 - n) / (n**2 * (n - 1)))
    if variance <= 0:
        return float("nan"), float("nan")

    z_score = float((runs - expected) / math.sqrt(variance))
    p_value = float(math.erfc(abs(z_score) / math.sqrt(2)))
    return float(z_score), float(p_value)


def approximate_entropy_test(
    bits: np.ndarray, block_size: int = 2
) -> tuple[float, float]:
    """NIST approximate entropy test. Returns (approx_entropy, p_value)."""
    n = bits.size
    if n < max(16, block_size + 2):
        return float("nan"), float("nan")

    counts_m = _pattern_counts(bits, block_size)
    counts_m1 = _pattern_counts(bits, block_size + 1)

    probs_m = counts_m / n
    probs_m1 = counts_m1 / n
    valid_m = probs_m > 0
    valid_m1 = probs_m1 > 0

    phi_m = float(np.sum(probs_m[valid_m] * np.log(probs_m[valid_m])))
    phi_m1 = float(np.sum(probs_m1[valid_m1] * np.log(probs_m1[valid_m1])))
    ap_en = float(phi_m - phi_m1)
    chi_sq = float(2.0 * n * (math.log(2) - ap_en))
    p_value = float(gammaincc(2 ** (block_size - 1), chi_sq / 2.0))
    return ap_en, p_value


def _pattern_counts(bits: np.ndarray, m: int) -> np.ndarray:
    n = bits.size
    bits_ext = np.concatenate([bits, bits[: m - 1]])
    patterns = np.zeros(n, dtype=np.int64)
    for j in range(m):
        patterns = (patterns << 1) | bits_ext[j : j + n]
    return np.bincount(patterns, minlength=2**m).astype(float)


# ---------------------------------------------------------------------------
# Predictability test
# ---------------------------------------------------------------------------

def entropy_predictability_test(
    bits: np.ndarray, history_length: int = 1
) -> tuple[float, float, float]:
    """
    Entropy-based predictability test using conditional entropy and G-test.

    Returns (mutual_information_bits, g_stat, p_value).
    """
    n = bits.size
    m = history_length
    if m < 1:
        raise ValueError("history_length must be >= 1")
    if n <= m + 1:
        return float("nan"), float("nan"), float("nan")

    total = n - m
    num_contexts = 2**m

    if m == 1:
        contexts = bits[:-1].astype(np.int64)
        next_bits = bits[1:].astype(np.int64)
        context_counts = np.bincount(contexts, minlength=2).astype(float)
        next_counts = np.bincount(next_bits, minlength=2).astype(float)
        joint_index = (contexts << 1) | next_bits
        joint_counts = np.bincount(joint_index, minlength=4).astype(float).reshape(2, 2)
    else:
        context_counts = np.zeros(num_contexts, dtype=float)
        next_counts = np.zeros(2, dtype=float)
        joint_counts = np.zeros((num_contexts, 2), dtype=float)
        for i in range(m, n):
            context = 0
            for j in range(i - m, i):
                context = (context << 1) | int(bits[j])
            bit = int(bits[i])
            context_counts[context] += 1.0
            next_counts[bit] += 1.0
            joint_counts[context, bit] += 1.0

    p_next = next_counts / total

    # unconditional entropy (vectorized)
    with np.errstate(divide="ignore", invalid="ignore"):
        unconditional_entropy = float(
            -np.sum(p_next * np.where(p_next > 0, np.log2(p_next), 0.0))
        )

    # conditional entropy (vectorized)
    active = context_counts > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        probs = np.where(
            active[:, None],
            joint_counts / np.where(active[:, None], context_counts[:, None], 1.0),
            0.0,
        )
        h_contexts = -np.sum(probs * np.where(probs > 0, np.log2(probs), 0.0), axis=1)
    conditional_entropy = float(
        np.sum((context_counts / total) * np.where(active, h_contexts, 0.0))
    )

    mutual_information_bits = float(unconditional_entropy - conditional_entropy)

    # G-test (vectorized)
    expected = context_counts[:, None] * p_next[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        g_terms = np.where(
            (joint_counts > 0) & (expected > 0),
            2.0 * joint_counts * np.log(joint_counts / expected),
            0.0,
        )
    g_stat = float(np.sum(g_terms))

    observed_context_count = int(np.sum(context_counts > 0))
    degrees_of_freedom = (observed_context_count - 1) * (2 - 1)
    if degrees_of_freedom <= 0:
        return mutual_information_bits, float("nan"), float("nan")

    p_value = float(1.0 - chi2.cdf(g_stat, degrees_of_freedom))
    return mutual_information_bits, float(g_stat), float(p_value)


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def summarize_bits_full(
    bits: np.ndarray,
    history_length: int,
    metadata: dict[str, object],
) -> dict[str, object]:
    """Run all statistical tests on a bitstream and return a flat result dict."""
    p1 = float(bits.mean()) if bits.size else float("nan")
    p0 = float(1.0 - p1) if bits.size else float("nan")
    entropy = shannon_entropy_from_bits(bits)
    lag1 = lag_autocorrelation(bits, 1)
    monobit_z, monobit_p = monobit_test(bits)
    runs_z, runs_p = runs_test(bits)
    approx_entropy, approx_entropy_p = approximate_entropy_test(bits)
    predictability_mi, predictability_g, predictability_p = entropy_predictability_test(
        bits, history_length=history_length
    )

    return {
        **metadata,
        "bit_count": int(bits.size),
        "p0": p0,
        "p1": p1,
        "shannon_entropy": entropy,
        "lag1_autocorrelation": lag1,
        "monobit_z": monobit_z,
        "monobit_pvalue": monobit_p,
        "runs_count": count_runs(bits),
        "runs_z": runs_z,
        "runs_pvalue": runs_p,
        "longest_run_0": longest_run(bits, 0),
        "longest_run_1": longest_run(bits, 1),
        "approximate_entropy": approx_entropy,
        "approximate_entropy_pvalue": approx_entropy_p,
        "predictability_mutual_information_bits": predictability_mi,
        "predictability_g_stat": predictability_g,
        "predictability_pvalue": predictability_p,
    }
