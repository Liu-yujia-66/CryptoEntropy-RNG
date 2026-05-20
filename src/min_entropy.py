"""
NIST SP 800-90B min-entropy estimators (two-estimator subset).

Implements two of the ten non-IID-track estimators from NIST
SP 800-90B Section 6.3:

  mcv_min_entropy    -- Sec 6.3.1 Most Common Value. Bounds per-bit
                        min-entropy from the marginal frequency of the
                        most common symbol (upper 99% confidence bound).
  markov_min_entropy -- Sec 6.3.3 Markov. Bounds per-bit min-entropy
                        from a first-order Markov model, accounting for
                        lag-1 dependence; most-likely length-128 path
                        via a Viterbi recursion.

estimate_min_entropy reports H_inf = min(MCV, Markov) as a
conservative per-bit lower bound, following the NIST "take the minimum
across estimators" rule.

Why this two-estimator subset (documented for the thesis): the full
SP 800-90B non-IID track runs ten estimators through the NIST
reference C tool. The XOR-fused crypto streams of Experiment 4 lose
entropy through two mechanisms only -- residual marginal bias
(even-n fusion) and first-order dependence -- which MCV and Markov
respectively target. The remaining eight estimators (collision,
compression, t-tuple, LRS, and the four predictors) target
longer-range structure already probed by the D-test and Serial
sub-tests of the Section 4.5 battery. Point estimates are used for
the transition probabilities (no per-cell confidence widening beyond
MCV's), which the thesis notes as a mild optimism relative to the
full NIST procedure.
"""

from __future__ import annotations

import math

import numpy as np


# One-sided 99% normal quantile (NIST SP 800-90B Sec 6.3.1 uses 2.576).
_Z_99 = 2.5758

# NIST SP 800-90B Sec 6.3.3 fixes the most-likely-sequence length at 128.
_MARKOV_SEQ_LEN = 128


def mcv_min_entropy(bits: np.ndarray, z: float = _Z_99) -> dict:
    """Most Common Value min-entropy estimate (NIST SP 800-90B Sec 6.3.1).

    Returns a dict with the per-bit ``h_inf`` plus the intermediate
    p_hat / p_u quantities for traceability.
    """
    n = int(bits.size)
    if n == 0:
        return {"h_inf": 0.0, "p_hat": float("nan"), "p_u": float("nan"), "n": 0}
    ones = int(np.count_nonzero(bits))
    c_max = max(ones, n - ones)
    p_hat = c_max / n
    p_u = min(1.0, p_hat + z * math.sqrt(p_hat * (1.0 - p_hat) / n))
    h_inf = -math.log2(p_u) if p_u > 0 else 0.0
    return {"h_inf": float(h_inf), "p_hat": float(p_hat), "p_u": float(p_u), "n": n}


def markov_min_entropy(bits: np.ndarray, seq_len: int = _MARKOV_SEQ_LEN) -> dict:
    """Markov min-entropy estimate for a binary stream (NIST SP 800-90B
    Sec 6.3.3).

    Builds a first-order Markov model and finds the probability of the
    most likely length-``seq_len`` output via a Viterbi recursion; the
    per-bit min-entropy is ``-log2(p_max) / seq_len`` capped at 1.
    """
    n = int(bits.size)
    if n < 2:
        return {"h_inf": 0.0, "n": n}

    ones = int(np.count_nonzero(bits))
    zeros = n - ones
    p0 = zeros / n
    p1 = ones / n

    prev = bits[:-1]
    nxt = bits[1:]
    c00 = int(np.count_nonzero((prev == 0) & (nxt == 0)))
    c01 = int(np.count_nonzero((prev == 0) & (nxt == 1)))
    c10 = int(np.count_nonzero((prev == 1) & (nxt == 0)))
    c11 = int(np.count_nonzero((prev == 1) & (nxt == 1)))

    t0 = c00 + c01
    t1 = c10 + c11
    # Unseen state -> fall back to a uniform transition (conservative).
    p00 = c00 / t0 if t0 > 0 else 0.5
    p01 = c01 / t0 if t0 > 0 else 0.5
    p10 = c10 / t1 if t1 > 0 else 0.5
    p11 = c11 / t1 if t1 > 0 else 0.5

    # Viterbi recursion: m{s} = max probability of a path ending in state s.
    m0, m1 = p0, p1
    for _ in range(seq_len - 1):
        nm0 = max(m0 * p00, m1 * p10)
        nm1 = max(m0 * p01, m1 * p11)
        m0, m1 = nm0, nm1
    p_max = max(m0, m1)

    if p_max <= 0:
        h_inf = 1.0
    else:
        h_inf = min(-math.log2(p_max) / seq_len, 1.0)

    return {
        "h_inf": float(h_inf),
        "n": n,
        "p0": float(p0),
        "p1": float(p1),
        "p00": float(p00),
        "p01": float(p01),
        "p10": float(p10),
        "p11": float(p11),
        "p_max_seq": float(p_max),
        "seq_len": seq_len,
    }


def estimate_min_entropy(bits: np.ndarray) -> dict:
    """Run MCV + Markov and report H_inf = min as the conservative
    per-bit min-entropy lower bound (NIST 'minimum across estimators').
    """
    mcv = mcv_min_entropy(bits)
    markov = markov_min_entropy(bits)
    h_inf_min = min(mcv["h_inf"], markov["h_inf"])
    return {
        "n": int(bits.size),
        "h_inf_mcv": mcv["h_inf"],
        "h_inf_markov": markov["h_inf"],
        "h_inf_min": float(h_inf_min),
        "mcv": mcv,
        "markov": markov,
    }


def ikm_bytes_for_security(
    h_inf_per_bit: float, target_security_bits: int = 256
) -> int:
    """Smallest IKM length in bytes whose total min-entropy reaches
    ``target_security_bits``, given per-bit min-entropy ``h_inf_per_bit``.

    HKDF-Extract produces a key indistinguishable from uniform at
    security level equal to the IKM min-entropy; this is the IKM length
    a deployment must read so a 256-bit-strength PRK is achievable.
    """
    if h_inf_per_bit <= 0:
        return 0
    bits_needed = target_security_bits / h_inf_per_bit
    return math.ceil(bits_needed / 8)
