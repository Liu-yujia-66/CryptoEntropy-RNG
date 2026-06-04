from __future__ import annotations

"""
Multi-asset XOR fusion at the 1-second sign-bit level (Experiment 4).

Pipeline:
  1. Per asset, build a per-second close-price series (forward-filled empty
     seconds) using src.bars.prepare_month_bars.
  2. Per asset, compute the sign of consecutive deltas; preserve zero
     deltas so they can be dropped jointly at the alignment step.
  3. UTC-second align all assets in the subset by intersecting their
     covered second ranges.
  4. Drop-any-zero: keep only seconds where every asset has Δp ≠ 0.
  5. fused_bits[t] = XOR over a ∈ subset of (sign_a[t] > 0).

Why a separate sign function instead of reusing
src.bitstream.build_offset_bitstream_from_arrays: the existing function
drops zero deltas per-asset, producing variable-length output that cannot
be aligned across assets. Fusion needs per-asset signs at the full
UTC-second grain with zeros preserved, dropped only at the multi-asset
join.

Forward-fill convention follows src.bars (empty seconds inherit the
previous close, producing a zero delta that drop-any-zero removes).
Baseline survival is reported two ways: a naive 0.85^n heuristic and an
empirical-independent baseline computed from per-asset zero-delta rates,
which is more accurate but loses the fixed reference point.
"""

from dataclasses import dataclass, field
from functools import reduce
from itertools import combinations
from pathlib import Path

import numpy as np

from src.bars import BarsCoverage, prepare_month_bars
from src.mutual_info import mi_1bit, pearson_phi_1bit


@dataclass(frozen=True)
class PerAssetSigns:
    """Per-second sign array for one (asset, month), zero deltas preserved.

    Length of ``signs`` equals ``epoch_s.size`` equals the number of
    UTC seconds in the asset's covered range
    [first_trade_second, last_trade_second]. The first element of
    ``signs`` is 0 by convention (no prior second to diff against).
    """

    asset: str
    epoch_s: np.ndarray  # int64, monotonically increasing seconds
    signs: np.ndarray    # int8 ∈ {-1, 0, +1}
    coverage: BarsCoverage


@dataclass(frozen=True)
class FusedStream:
    """Output of build_fused_stream.

    ``fused_bits`` is the dense 1-D bit array after drop-any-zero, ready
    to feed the Exp 2 1-sec-bar all-offset framework as if it were a
    single-asset stream. Note that downstream "time" semantics are token
    indices on this stream, not UTC seconds.
    """

    subset: tuple[str, ...]
    month_label: str
    fused_bits: np.ndarray         # uint8 ∈ {0, 1}, length == kept_seconds
    aligned_epoch_s: np.ndarray    # int64, length == raw_seconds
    keep_mask: np.ndarray          # bool, length == raw_seconds
    raw_seconds: int               # intersection length across the subset
    kept_seconds: int              # == fused_bits.size
    survival_rate: float           # kept_seconds / raw_seconds
    naive_baseline: float                  # 0.85 ** n reference
    empirical_independent_baseline: float  # ∏ (1 - per_asset_zero_delta_rate)
    survival_vs_naive_ratio: float
    survival_vs_empirical_ratio: float
    per_asset_coverage: dict[str, float] = field(default_factory=dict)
    # ↑ seconds_with_trades / seconds_total reported by src.bars on the
    #   asset's *full* covered range. Useful as a coarse outage diagnostic;
    #   it is NOT the coverage restricted to the intersection.
    per_asset_zero_delta_rate: dict[str, float] = field(default_factory=dict)
    # ↑ count(signs == 0) / raw_seconds, measured AFTER slicing to the
    #   intersection. This is the operationally relevant rate for the
    #   drop-any-zero step.
    per_asset_p1: dict[str, float] = field(default_factory=dict)
    # ↑ P(sign = +1 | kept) per asset, computed on the kept_mask positions.
    #   These are the marginal bias of each XOR input; together with
    #   pairwise_correlation they explain XOR-output bias when fused_bits
    #   p(1) drifts from 0.5.
    pairwise_correlation: dict[tuple[str, str], float] = field(default_factory=dict)
    # ↑ Pearson correlation between (sign_a > 0) and (sign_b > 0) on
    #   kept positions, for every unordered pair (a, b) in subset
    #   (canonical order: a < b lexicographically).
    pairwise_mi_1bit: dict[tuple[str, str], float] = field(default_factory=dict)
    # ↑ Mutual information in bits on the same pair-of-binary streams.
    #   Acceptance heuristic: I < 1e-3 bits/symbol means "near-independent"
    #   inputs; the smoke-time per-(month, subset) value here previews what
    #   the calibration-pool 5x5 matrix will look like.


def _file_path_for(asset: str, month_label: str, input_root: Path) -> Path:
    return input_root / asset / f"{asset}-aggTrades-{month_label}.csv"


def build_per_asset_signs(
    asset: str,
    month_label: str,
    input_root: Path,
    max_rows: int | None = None,
) -> PerAssetSigns:
    """Load one (asset, month) and return per-second sign array.

    Zero deltas are kept as 0; the first second is 0 by convention. The
    return is a dense array indexed by UTC second over the asset's
    covered range.
    """
    path = _file_path_for(asset, month_label, input_root)
    prepared, coverage = prepare_month_bars(path, max_rows=max_rows)

    # src.bars writes timestamp as second_epoch * 1000, so floor-divide
    # recovers the integer epoch second for each row.
    epoch_s = (prepared.timestamp // 1000).astype(np.int64)
    close = prepared.price

    n = close.size
    delta = np.empty(n, dtype=np.float64)
    delta[0] = 0.0
    delta[1:] = np.diff(close)
    signs = np.sign(delta).astype(np.int8)

    return PerAssetSigns(
        asset=asset,
        epoch_s=epoch_s,
        signs=signs,
        coverage=coverage,
    )


def build_fused_stream(
    subset: list[str],
    month_label: str,
    input_root: Path,
    max_rows: int | None = None,
) -> FusedStream:
    """Build an XOR-fused 1-second bit stream for a subset of assets.

    Order in ``subset`` does not affect ``fused_bits`` (XOR is commutative).
    The order is preserved in the returned dataclass solely for traceability.

    Raises ValueError if the intersection of per-asset covered ranges is
    empty or if fewer than two assets are passed.
    """
    if len(subset) < 2:
        raise ValueError(
            f"fusion requires at least two assets; got subset={subset!r}"
        )

    per_asset = [
        build_per_asset_signs(asset, month_label, input_root, max_rows=max_rows)
        for asset in subset
    ]
    return build_fused_stream_from_signs(subset, month_label, per_asset)


def build_fused_stream_from_signs(
    subset: list[str],
    month_label: str,
    per_asset: list[PerAssetSigns],
) -> FusedStream:
    """Build a FusedStream from pre-loaded per-asset sign arrays.

    Lets the caller share a per-(asset, month) cache across multiple
    subsets in the same month (the calibration runner reuses this to
    avoid reloading each asset four times when sweeping n=2..5).
    """
    if len(subset) < 2:
        raise ValueError(
            f"fusion requires at least two assets; got subset={subset!r}"
        )
    if len(per_asset) != len(subset) or [p.asset for p in per_asset] != list(subset):
        raise ValueError(
            f"per_asset order/contents must match subset; "
            f"subset={subset!r}, per_asset assets={[p.asset for p in per_asset]!r}"
        )

    start_s = max(int(p.epoch_s[0]) for p in per_asset)
    end_s = min(int(p.epoch_s[-1]) for p in per_asset)
    if end_s < start_s:
        raise ValueError(
            f"empty intersection for subset={subset!r} in month={month_label!r}: "
            f"max start_s={start_s} > min end_s={end_s}"
        )

    raw_seconds = end_s - start_s + 1
    aligned_epoch_s = np.arange(start_s, end_s + 1, dtype=np.int64)

    sliced_signs: list[np.ndarray] = []
    per_asset_zero_delta_rate: dict[str, float] = {}
    per_asset_coverage: dict[str, float] = {}
    for p in per_asset:
        asset_start = int(p.epoch_s[0])
        slice_start = start_s - asset_start
        sliced = p.signs[slice_start : slice_start + raw_seconds]
        if sliced.size != raw_seconds:
            raise RuntimeError(
                f"slice length mismatch for {p.asset}: "
                f"expected {raw_seconds}, got {sliced.size}"
            )
        sliced_signs.append(sliced)
        zero_count = int(np.count_nonzero(sliced == 0))
        per_asset_zero_delta_rate[p.asset] = zero_count / raw_seconds
        per_asset_coverage[p.asset] = p.coverage.coverage

    # Drop-any-zero mask: True iff every asset has Δp ≠ 0 at that second.
    keep_mask = np.ones(raw_seconds, dtype=bool)
    for sliced in sliced_signs:
        keep_mask &= sliced != 0
    kept_seconds = int(keep_mask.sum())

    per_asset_p1: dict[str, float] = {}
    pairwise_correlation: dict[tuple[str, str], float] = {}
    pairwise_mi_1bit: dict[tuple[str, str], float] = {}

    if kept_seconds == 0:
        fused_bits = np.array([], dtype=np.uint8)
        bit_arrays: list[np.ndarray] = [
            np.array([], dtype=np.uint8) for _ in subset
        ]
    else:
        bit_arrays = [
            (sliced[keep_mask] > 0).astype(np.uint8) for sliced in sliced_signs
        ]
        fused_bits = reduce(np.bitwise_xor, bit_arrays)

    for asset, bits in zip(subset, bit_arrays):
        per_asset_p1[asset] = float(bits.mean()) if bits.size > 0 else 0.0

    # Pairwise correlation / MI on kept positions only — these characterise
    # the inputs that XOR sees, not the raw per-second signs (which include
    # zero deltas that get dropped before fusion).
    for a, b in combinations(subset, 2):
        key = tuple(sorted([a, b]))
        bits_a = bit_arrays[subset.index(a)]
        bits_b = bit_arrays[subset.index(b)]
        pairwise_correlation[key] = pearson_phi_1bit(bits_a, bits_b)
        pairwise_mi_1bit[key] = mi_1bit(bits_a, bits_b)

    n_assets = len(subset)
    survival_rate = kept_seconds / raw_seconds if raw_seconds > 0 else 0.0
    naive_baseline = 0.85**n_assets
    empirical_independent_baseline = 1.0
    for asset in subset:
        empirical_independent_baseline *= 1.0 - per_asset_zero_delta_rate[asset]

    survival_vs_naive_ratio = (
        survival_rate / naive_baseline if naive_baseline > 0 else float("inf")
    )
    survival_vs_empirical_ratio = (
        survival_rate / empirical_independent_baseline
        if empirical_independent_baseline > 0
        else float("inf")
    )

    return FusedStream(
        subset=tuple(subset),
        month_label=month_label,
        fused_bits=fused_bits,
        aligned_epoch_s=aligned_epoch_s,
        keep_mask=keep_mask,
        raw_seconds=raw_seconds,
        kept_seconds=kept_seconds,
        survival_rate=survival_rate,
        naive_baseline=naive_baseline,
        empirical_independent_baseline=empirical_independent_baseline,
        survival_vs_naive_ratio=survival_vs_naive_ratio,
        survival_vs_empirical_ratio=survival_vs_empirical_ratio,
        per_asset_coverage=per_asset_coverage,
        per_asset_zero_delta_rate=per_asset_zero_delta_rate,
        per_asset_p1=per_asset_p1,
        pairwise_correlation=pairwise_correlation,
        pairwise_mi_1bit=pairwise_mi_1bit,
    )
