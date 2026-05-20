"""
Experiment 4 calibration helpers.

Implements the aggregation + gate stack for the XOR-fused stream:

  xor_aggregate_offset(fused_bits, ell, offset)
      For one starting offset, group consecutive ell fused bits into
      windows and XOR them: output[i] = XOR_{j=0..ell-1} fused[o + i*ell + j].
      This is the piling-up aggregation operator: marginal bias
      shrinks exponentially in ell (Bernoulli(p) ⇒ output bias
      0.5 − 0.5*(1−2p)^ell), and within-offset positions sample
      disjoint windows so the output inherits no spurious
      alternation. Replaces the v3.2 §2.3 literal text
      ("Exp 2 §4.3 1sbar framework"): on a binary input that
      framework's sub-sample → diff → drop-zero → sign produces a
      perfectly alternating stream because two consecutive non-zero
      transitions of a binary chain must differ in direction.
      XOR-aggregation is what the plan's piling-up argument
      (v3.2 §2.1) actually requires.

  evaluate_offset_bits(bits)
      Run the +Runs gate sub-tests (D adaptive-k, Monobit, Runs) on
      one offset's aggregated output. Returns the three p-values plus
      the bit count.

  evaluate_fused_at_ell(fused_bits, ell, ...)
      XOR-aggregate every offset 0..ell-1, run evaluate_offset_bits
      on each, apply the +Runs all-offset gate (>=80% of valid
      offsets pass D + Monobit + Runs at alpha=0.01). Returns the
      per-offset rows and the cell-level pass/fail.

  select_ell_star_from_grid(fused_bits, ell_grid, ...)
      Sweep ell from smallest to largest, return the smallest ell
      that passes the gate. Stops early on first hit. None if no ell
      passes.

  select_witness_offset(fused_bits, ell, ...)
      For a given (fused stream, ell), pick the offset with the
      largest combined p-value (geometric mean of D + Monobit + Runs).

  p80(values, ...)
      Calibration aggregation: 80th-percentile across calibration
      months, with explicit handling of None entries (months where
      the gate did not select any ell).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import math
import numpy as np

from src.stats import (
    _adaptive_k,
    entropy_predictability_test,
    monobit_test,
    runs_test,
)


# ---------------------------------------------------------------------------
# Per-offset evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OffsetEval:
    """Three +Runs-gate p-values + bit count for one offset bitstream."""

    offset: int
    bit_count: int
    d_pvalue: float
    monobit_pvalue: float
    runs_pvalue: float


def evaluate_offset_bits(offset: int, bits: np.ndarray) -> OffsetEval:
    """Run D (adaptive k) + Monobit + Runs on one offset bitstream."""
    n = int(bits.size)
    if n < 2:
        return OffsetEval(
            offset=offset,
            bit_count=n,
            d_pvalue=float("nan"),
            monobit_pvalue=float("nan"),
            runs_pvalue=float("nan"),
        )
    k = _adaptive_k(n)
    history_length = max(1, k - 1)
    _, _, d_p = entropy_predictability_test(bits, history_length=history_length)
    _, monobit_p = monobit_test(bits)
    _, runs_p = runs_test(bits)
    return OffsetEval(
        offset=offset,
        bit_count=n,
        d_pvalue=float(d_p),
        monobit_pvalue=float(monobit_p),
        runs_pvalue=float(runs_p),
    )


# ---------------------------------------------------------------------------
# Per-(fused, ell) gate evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EllEvaluation:
    """All-offset gate result for one (fused stream, ell) pair."""

    ell: int
    n_offsets_total: int
    n_offsets_valid: int
    valid_offset_ratio: float
    d_pass_rate: float
    monobit_pass_rate: float
    runs_pass_rate: float
    passes_gate: bool
    per_offset: tuple[OffsetEval, ...] = field(default_factory=tuple)


def xor_aggregate_offset(
    fused_bits: np.ndarray, ell: int, offset: int
) -> np.ndarray:
    """XOR-aggregate the fused stream at one starting offset.

    output[i] = XOR_{j=0..ell-1} fused[offset + i*ell + j].

    Equivalent to grouping the fused stream into non-overlapping
    ell-bit windows starting at ``offset`` and XOR-reducing each
    window. Vectorised via reshape.
    """
    if ell < 1:
        raise ValueError(f"ell must be >= 1, got {ell}")
    if offset < 0 or offset >= ell:
        raise ValueError(f"offset must satisfy 0 <= offset < ell, got {offset}")
    if fused_bits.dtype != np.uint8:
        fused_bits = fused_bits.astype(np.uint8)
    n = fused_bits.size
    if n <= offset:
        return np.array([], dtype=np.uint8)
    n_out = (n - offset) // ell
    if n_out == 0:
        return np.array([], dtype=np.uint8)
    window = fused_bits[offset : offset + n_out * ell].reshape(n_out, ell)
    return np.bitwise_xor.reduce(window, axis=1).astype(np.uint8)


def evaluate_fused_at_ell(
    fused_bits: np.ndarray,
    ell: int,
    alpha: float = 0.01,
    pass_rate_threshold: float = 0.80,
    valid_offset_ratio_threshold: float = 0.80,
    min_bit_count: int = 2000,
    keep_per_offset: bool = False,
) -> EllEvaluation:
    """All-offset +Runs gate at one aggregation level.

    XOR-aggregates every starting offset 0..ell-1 (see
    ``xor_aggregate_offset``), runs D + Monobit + Runs on each
    offset's output, then checks the all-offset gate.

    keep_per_offset=False (default) drops the per-offset detail to
    save memory during a long ell-sweep; the sweep can re-evaluate
    the selected ell with keep_per_offset=True if it needs the
    per-offset detail (e.g. for witness offset selection).
    """
    n_offsets_total = ell

    evals: list[OffsetEval] = [
        evaluate_offset_bits(offset, xor_aggregate_offset(fused_bits, ell, offset))
        for offset in range(ell)
    ]
    valid = [ev for ev in evals if ev.bit_count >= min_bit_count]
    n_valid = len(valid)
    valid_ratio = n_valid / n_offsets_total if n_offsets_total > 0 else 0.0

    if n_valid == 0:
        d_rate = monobit_rate = runs_rate = 0.0
    else:
        d_rate = float(
            sum(
                1
                for ev in valid
                if not math.isnan(ev.d_pvalue) and ev.d_pvalue >= alpha
            )
            / n_valid
        )
        monobit_rate = float(
            sum(
                1
                for ev in valid
                if not math.isnan(ev.monobit_pvalue) and ev.monobit_pvalue >= alpha
            )
            / n_valid
        )
        runs_rate = float(
            sum(
                1
                for ev in valid
                if not math.isnan(ev.runs_pvalue) and ev.runs_pvalue >= alpha
            )
            / n_valid
        )

    passes = bool(
        valid_ratio >= valid_offset_ratio_threshold
        and d_rate >= pass_rate_threshold
        and monobit_rate >= pass_rate_threshold
        and runs_rate >= pass_rate_threshold
    )
    return EllEvaluation(
        ell=ell,
        n_offsets_total=n_offsets_total,
        n_offsets_valid=n_valid,
        valid_offset_ratio=valid_ratio,
        d_pass_rate=d_rate,
        monobit_pass_rate=monobit_rate,
        runs_pass_rate=runs_rate,
        passes_gate=passes,
        per_offset=tuple(evals) if keep_per_offset else (),
    )


# ---------------------------------------------------------------------------
# Sweep + selection
# ---------------------------------------------------------------------------


def select_ell_star_from_grid(
    fused_bits: np.ndarray,
    ell_grid: Sequence[int],
    alpha: float = 0.01,
    pass_rate_threshold: float = 0.80,
    valid_offset_ratio_threshold: float = 0.80,
    min_bit_count: int = 2000,
    on_progress=None,
) -> tuple[int | None, list[EllEvaluation]]:
    """Sweep ell from smallest to largest; return the first ell that passes.

    Returns (ell_star, history). history is the list of EllEvaluations for
    all ell values that were actually tested (sweep stops at first pass,
    or runs to the end if no ell passes).

    Optional on_progress(ell_evaluation) callback is called after each
    ell is evaluated; used by the runner to print progress.
    """
    history: list[EllEvaluation] = []
    for ell in ell_grid:
        ev = evaluate_fused_at_ell(
            fused_bits=fused_bits,
            ell=ell,
            alpha=alpha,
            pass_rate_threshold=pass_rate_threshold,
            valid_offset_ratio_threshold=valid_offset_ratio_threshold,
            min_bit_count=min_bit_count,
            keep_per_offset=False,
        )
        history.append(ev)
        if on_progress is not None:
            on_progress(ev)
        if ev.passes_gate:
            return ell, history
    return None, history


# ---------------------------------------------------------------------------
# Witness offset selection
# ---------------------------------------------------------------------------


def select_witness_offset(
    fused_bits: np.ndarray,
    ell: int,
    alpha: float = 0.01,
    valid_offset_ratio_threshold: float = 0.80,
    min_bit_count: int = 2000,
) -> tuple[int, OffsetEval]:
    """Pick the offset at given ell with the largest combined p-value.

    Combined score = geometric mean of (D, Monobit, Runs) p-values,
    equivalently mean of log(p) on the valid offset population. Picks
    the offset maximising this score. Restricts to offsets with
    bit_count >= min_bit_count.

    Returns (witness_offset, OffsetEval for that offset).
    """
    ev = evaluate_fused_at_ell(
        fused_bits=fused_bits,
        ell=ell,
        alpha=alpha,
        pass_rate_threshold=0.0,  # not used here, but kept for API symmetry
        valid_offset_ratio_threshold=valid_offset_ratio_threshold,
        min_bit_count=min_bit_count,
        keep_per_offset=True,
    )
    valid = [
        oe
        for oe in ev.per_offset
        if oe.bit_count >= min_bit_count
        and not math.isnan(oe.d_pvalue)
        and not math.isnan(oe.monobit_pvalue)
        and not math.isnan(oe.runs_pvalue)
    ]
    if not valid:
        raise ValueError(
            f"no valid offsets at ell={ell} (n_total={len(ev.per_offset)}, "
            f"min_bit_count={min_bit_count})"
        )

    def _combined_log_score(oe: OffsetEval) -> float:
        # Use log to dodge underflow; larger mean log = larger geo-mean p.
        # Treat sub-floor p as the floor to avoid -inf.
        floor = 1e-300
        return float(
            np.mean(
                [
                    math.log(max(oe.d_pvalue, floor)),
                    math.log(max(oe.monobit_pvalue, floor)),
                    math.log(max(oe.runs_pvalue, floor)),
                ]
            )
        )

    best = max(valid, key=_combined_log_score)
    return best.offset, best


# ---------------------------------------------------------------------------
# Cross-month aggregation
# ---------------------------------------------------------------------------


def p80(values: Sequence[int | None]) -> int | None:
    """80th percentile of integer ells, ignoring None entries.

    Plan v3.2 §2.2 uses P80 (rather than median or max) because the
    sample is small (9 calibration months) and the goal is "majority
    coverage without being dragged by outliers". Returns None when
    every entry is None.
    """
    clean = [int(v) for v in values if v is not None]
    if not clean:
        return None
    arr = np.asarray(clean, dtype=np.float64)
    return int(round(float(np.quantile(arr, 0.80, method="higher"))))
