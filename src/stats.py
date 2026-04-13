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
    bits: np.ndarray, block_size: int = 5
) -> tuple[float, float]:
    """NIST approximate entropy test. Returns (approx_entropy, p_value).

    block_size defaults to 5 per Onofri, Shternshis & Marmi (2025) Table 4.
    Requires n >= 2^(block_size + 2) roughly; safe for n >= MIN_BIT_COUNT=2000.
    """
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
    bits_ext = np.concatenate([bits, bits[: m - 1]]).astype(np.int64)
    patterns = np.zeros(n, dtype=np.int64)
    for j in range(m):
        patterns = (patterns << 1) | bits_ext[j : j + n]
    return np.bincount(patterns, minlength=2**m).astype(float)


# ---------------------------------------------------------------------------
# Shannon entropy bias test (Paper Lemma 1, non-overlapping blocks)
# ---------------------------------------------------------------------------

def shannon_bias_test(
    bits: np.ndarray, block_length: int
) -> tuple[float, float, float]:
    """
    Shannon entropy bias test from Shternshis & Marmi (2025) Lemma 1.

    Partitions the bitstream into floor(n/k) non-overlapping k-blocks, computes
    the plug-in entropy estimate H_hat, and returns the bias statistic
        B = 2 * n_b * (k * ln(2) - H_hat)
    which under H_0 (i.i.d. equiprobable symbols) follows chi^2 with
    2^k - 1 degrees of freedom.

    Unlike the KL/NP statistic D (which is valid for unequal symbol
    probabilities), B assumes symbol equiprobability — it will over-reject
    when p(0) != p(1). Interpret together with a monobit check.

    Returns (B, entropy_hat_nats, p_value).
    """
    n = int(bits.size)
    k = int(block_length)
    if k < 1:
        raise ValueError("block_length must be >= 1")
    n_b = n // k
    if n_b < 2:
        return float("nan"), float("nan"), float("nan")

    trimmed = bits[: n_b * k].astype(np.int64).reshape(n_b, k)
    # Pack each k-bit row into a base-2 integer 0..2^k - 1.
    weights = (1 << np.arange(k - 1, -1, -1, dtype=np.int64))
    block_ids = trimmed @ weights
    counts = np.bincount(block_ids, minlength=2**k).astype(float)

    probs = counts / n_b
    nonzero = probs > 0
    entropy_hat = float(-np.sum(probs[nonzero] * np.log(probs[nonzero])))  # nats
    bias = float(2.0 * n_b * (k * math.log(2) - entropy_hat))

    dof = (2**k) - 1
    if dof <= 0:
        return bias, entropy_hat, float("nan")
    p_value = float(1.0 - chi2.cdf(bias, dof))
    return bias, entropy_hat, p_value


# ---------------------------------------------------------------------------
# Predictability test
# ---------------------------------------------------------------------------

def entropy_predictability_test(
    bits: np.ndarray, history_length: int = 1
) -> tuple[float, float, float]:
    """
    NP / KL-divergence predictability test (Shternshis & Marmi 2025, Eq. 3-4).

    Notation map (Paper ↔ code, binary alphabet s=2):
        Paper k  (block length)              = history_length + 1
        Paper k-1 (context length)           = history_length
        Paper n - k + 1 (overlapping blocks) = n_blocks
        Paper s^(k-1)  (number of contexts)  = num_contexts = 2 ** history_length
        Paper (s^(k-1) - 1)(s - 1)  (DOF)    = num_contexts - 1

    The parameter is named `history_length` (rather than k) because that is the
    quantity directly meaningful to callers: how many past bits form the
    context. Internally we use the Paper's k = history_length + 1 wherever the
    Paper's formulae are referenced.

    Returns (mutual_information_bits, g_stat, p_value).
    """
    n = bits.size
    history_length = int(history_length)
    if history_length < 1:
        raise ValueError("history_length must be >= 1")
    k = history_length + 1  # Paper's block length
    if n < k + 1:
        return float("nan"), float("nan"), float("nan")

    n_blocks = n - history_length          # Paper: n - k + 1
    num_contexts = 2 ** history_length     # Paper: s^(k-1) = 2^(k-1)

    # Pre-convert once so that loop slices are zero-copy views instead of
    # allocating a new int64 array on every iteration.
    bits_int64 = bits.astype(np.int64)

    # Build the (k-1)-bit context integer for every position via sliding
    # bit-shift accumulation — O((k-1) * n_blocks) array ops, no Python loops
    # over individual elements.
    contexts = np.zeros(n_blocks, dtype=np.int64)
    for j in range(history_length):
        contexts = (contexts << 1) | bits_int64[j : j + n_blocks]
    next_bits = bits_int64[history_length:]

    context_counts = np.bincount(contexts, minlength=num_contexts).astype(float)
    next_counts = np.bincount(next_bits, minlength=2).astype(float)
    joint_index = (contexts << 1) | next_bits
    joint_counts = (
        np.bincount(joint_index, minlength=num_contexts * 2)
        .astype(float)
        .reshape(num_contexts, 2)
    )

    p_next = next_counts / n_blocks

    # Unconditional entropy H(Y)
    with np.errstate(divide="ignore", invalid="ignore"):
        unconditional_entropy = float(
            -np.sum(p_next * np.where(p_next > 0, np.log2(p_next), 0.0))
        )

    # Conditional entropy H(Y | context)
    active = context_counts > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        probs = np.where(
            active[:, None],
            joint_counts / np.where(active[:, None], context_counts[:, None], 1.0),
            0.0,
        )
        h_contexts = -np.sum(probs * np.where(probs > 0, np.log2(probs), 0.0), axis=1)
    conditional_entropy = float(
        np.sum((context_counts / n_blocks) * np.where(active, h_contexts, 0.0))
    )

    mutual_information_bits = float(unconditional_entropy - conditional_entropy)

    # NP-statistics / G-test (Paper Eq. 3):
    #   D = 2 Σ f_{i,j} ln( (n - k + 1) * f_{i,j} / (f_{i·} * f_{·j}) )
    # With expected_{i,j} = f_{i·} * f_{·j} / (n - k + 1) = context_counts * p_next,
    # the term inside the log is f_{i,j} / expected_{i,j}.
    expected = context_counts[:, None] * p_next[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        g_terms = np.where(
            (joint_counts > 0) & (expected > 0),
            2.0 * joint_counts * np.log(joint_counts / expected),
            0.0,
        )
    g_stat = float(np.sum(g_terms))

    # DOF (Paper Lemma 2 / Billingsley 1961 Thm 4.1):
    #   (s^(k-1) - 1)(s - 1) = num_contexts - 1   for binary (s=2)
    degrees_of_freedom = num_contexts - 1
    if degrees_of_freedom <= 0:
        return mutual_information_bits, float("nan"), float("nan")

    p_value = float(1.0 - chi2.cdf(g_stat, degrees_of_freedom))
    return mutual_information_bits, float(g_stat), float(p_value)


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def _adaptive_k(n: int) -> int:
    """
    Adaptive block length k = floor(0.5 * log2(n)), clamped to >= 2.

    Per Shternshis & Marmi (2025) Section 2.2 and Onofri, Shternshis & Marmi
    (2025) Section 2.1.1: k = [0.5 * log_s(n)] for alphabet size s (binary: s=2).
    history_length = k - 1 (k-1 past bits form the context for the NP-statistics).
    """
    if n < 2:
        return 2
    return max(2, math.floor(0.5 * math.log2(n)))


def summarize_bits_full(
    bits: np.ndarray,
    metadata: dict[str, object],
) -> dict[str, object]:
    """Run all statistical tests on a bitstream and return a flat result dict.

    The predictability test uses adaptive block length k = floor(0.5 * log2(n))
    per Shternshis & Marmi (2025), with history_length = k - 1.
    In Experiment 2 this means changing aggregation level ell also changes the
    effective sample size n, so the internal predictability order can drift even
    when the plotted x-axis shows only ell.
    """
    n = int(bits.size)
    k = _adaptive_k(n)
    history_length = k - 1  # = k - 1 past bits used as context

    p1 = float(bits.mean()) if n else float("nan")
    p0 = float(1.0 - p1) if n else float("nan")
    entropy = shannon_entropy_from_bits(bits)
    lag1 = lag_autocorrelation(bits, 1)
    monobit_z, monobit_p = monobit_test(bits)
    runs_z, runs_p = runs_test(bits)
    approx_entropy, approx_entropy_p = approximate_entropy_test(bits)
    predictability_mi, predictability_g, predictability_p = entropy_predictability_test(
        bits, history_length=history_length
    )
    shannon_bias_b, shannon_bias_h, shannon_bias_p = shannon_bias_test(
        bits, block_length=k
    )

    return {
        **metadata,
        "bit_count": n,
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
        "predictability_k": k,
        "predictability_mutual_information_bits": predictability_mi,
        "predictability_g_stat": predictability_g,
        "predictability_pvalue": predictability_p,
        "shannon_bias_b": shannon_bias_b,
        "shannon_bias_entropy_nats": shannon_bias_h,
        "shannon_bias_pvalue": shannon_bias_p,
    }
