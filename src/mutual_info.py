from __future__ import annotations

"""
Pairwise 1-bit mutual information / Pearson correlation utilities for
Experiment 4.

Two layers:

  Array-based helpers
    pearson_phi_1bit(x, y), mi_1bit(x, y) — operate on aligned {0,1}
    arrays. Used by src.fusion for smoke-time diagnostics on a single
    (subset, month) cell.

  Count-based helpers + pool builder
    joint_counts_1bit, mi_from_counts, pearson_from_counts and
    pool_pair_across_months / compute_pairwise_mi_matrix — operate on
    the 2x2 joint contingency table and stream-accumulate it across
    many (asset, month) cells, building the 5x5 calibration-window pool
    matrix.

The count-based pool is mathematically equivalent to concatenating bit
streams and computing MI on the concatenation, but does the bookkeeping
in O(months) memory instead of O(months * cell_length).

drop-any-zero is applied PAIR-specifically here: for the pair (a, b)
we keep only seconds where both a and b have non-zero per-second
sign. This differs from the N-asset XOR fusion where the mask uses
every asset in the subset.
"""

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

# Note: src.fusion is imported lazily inside the pool builders to avoid a
# circular import (src.fusion imports the array-based helpers from here
# for its smoke-time diagnostics).


def pearson_phi_1bit(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation (phi coefficient) between two {0, 1} arrays.

    Returns 0.0 when either array has zero variance (constant), since
    correlation is undefined in that case.
    """
    if x.size == 0:
        return 0.0
    px = float(x.mean())
    py = float(y.mean())
    var_x = px * (1.0 - px)
    var_y = py * (1.0 - py)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    cov = float((x * y).mean()) - px * py
    return cov / float(np.sqrt(var_x * var_y))


def mi_1bit(x: np.ndarray, y: np.ndarray) -> float:
    """Mutual information in bits between two {0, 1} arrays.

    Plug-in estimator from the 2x2 joint frequency table; zero cells
    contribute zero (0 log 0 := 0 convention).
    """
    if x.size == 0:
        return 0.0
    n11 = int(np.count_nonzero((x == 1) & (y == 1)))
    n10 = int(np.count_nonzero((x == 1) & (y == 0)))
    n01 = int(np.count_nonzero((x == 0) & (y == 1)))
    n00 = int(x.size - n11 - n10 - n01)
    return mi_from_counts(n00, n01, n10, n11)


def joint_counts_1bit(x: np.ndarray, y: np.ndarray) -> tuple[int, int, int, int]:
    """Return the 2x2 joint contingency table as (n00, n01, n10, n11)."""
    if x.size == 0:
        return (0, 0, 0, 0)
    n11 = int(np.count_nonzero((x == 1) & (y == 1)))
    n10 = int(np.count_nonzero((x == 1) & (y == 0)))
    n01 = int(np.count_nonzero((x == 0) & (y == 1)))
    n00 = int(x.size - n11 - n10 - n01)
    return n00, n01, n10, n11


def mi_from_counts(n00: int, n01: int, n10: int, n11: int) -> float:
    """MI in bits from a 2x2 joint contingency table."""
    n = n00 + n01 + n10 + n11
    if n == 0:
        return 0.0
    p_x0 = (n00 + n01) / n
    p_x1 = (n10 + n11) / n
    p_y0 = (n00 + n10) / n
    p_y1 = (n01 + n11) / n
    mi = 0.0
    for count, p_marg in (
        (n00, p_x0 * p_y0),
        (n01, p_x0 * p_y1),
        (n10, p_x1 * p_y0),
        (n11, p_x1 * p_y1),
    ):
        if count == 0 or p_marg <= 0.0:
            continue
        p_joint = count / n
        mi += p_joint * np.log2(p_joint / p_marg)
    return float(mi)


def pearson_from_counts(n00: int, n01: int, n10: int, n11: int) -> float:
    """Pearson phi from a 2x2 joint contingency table."""
    n = n00 + n01 + n10 + n11
    if n == 0:
        return 0.0
    p_x1 = (n10 + n11) / n
    p_y1 = (n01 + n11) / n
    var_x = p_x1 * (1.0 - p_x1)
    var_y = p_y1 * (1.0 - p_y1)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    cov = (n11 / n) - p_x1 * p_y1
    return float(cov / np.sqrt(var_x * var_y))


@dataclass(frozen=True)
class PairMonthCell:
    asset_a: str
    asset_b: str
    month: str
    raw_intersection_seconds: int
    n_kept: int  # n00 + n01 + n10 + n11 on the kept (pair-drop-zero) positions
    n00: int
    n01: int
    n10: int
    n11: int
    mi_bits: float
    rho_pearson: float
    marginal_p1_a: float
    marginal_p1_b: float


@dataclass(frozen=True)
class PairPoolResult:
    asset_a: str
    asset_b: str
    months: tuple[str, ...]
    pool_n_kept: int
    pool_n00: int
    pool_n01: int
    pool_n10: int
    pool_n11: int
    pool_mi_bits: float
    pool_rho_pearson: float
    pool_marginal_p1_a: float
    pool_marginal_p1_b: float
    per_month: tuple[PairMonthCell, ...]


def _slice_to_intersection(
    epoch_s: np.ndarray,
    signs: np.ndarray,
    start_s: int,
    length: int,
) -> np.ndarray:
    asset_start = int(epoch_s[0])
    offset = start_s - asset_start
    sliced = signs[offset : offset + length]
    if sliced.size != length:
        raise RuntimeError(
            f"slice length mismatch: expected {length}, got {sliced.size}"
        )
    return sliced


def pool_pair_across_months(
    asset_a: str,
    asset_b: str,
    months: list[str],
    input_root: Path,
    max_rows: int | None = None,
    verbose: bool = False,
) -> PairPoolResult:
    """Compute pooled and per-month 1-bit MI / Pearson for one pair (a, b).

    Each month independently: load both per-asset signs, intersect their
    UTC second ranges, apply pair-specific drop-any-zero, accumulate the
    2x2 joint contingency table. The cross-month pool is the cell-wise
    sum of per-month tables.
    """
    from src.fusion import build_per_asset_signs  # lazy: see module-top note

    pool = [0, 0, 0, 0]  # n00, n01, n10, n11
    per_month: list[PairMonthCell] = []

    for month in months:
        sa = build_per_asset_signs(asset_a, month, input_root, max_rows=max_rows)
        sb = build_per_asset_signs(asset_b, month, input_root, max_rows=max_rows)

        start_s = max(int(sa.epoch_s[0]), int(sb.epoch_s[0]))
        end_s = min(int(sa.epoch_s[-1]), int(sb.epoch_s[-1]))
        if end_s < start_s:
            if verbose:
                print(
                    f"[mi] {asset_a}/{asset_b} {month}: empty intersection; "
                    "skipping month"
                )
            per_month.append(
                PairMonthCell(
                    asset_a=asset_a,
                    asset_b=asset_b,
                    month=month,
                    raw_intersection_seconds=0,
                    n_kept=0,
                    n00=0,
                    n01=0,
                    n10=0,
                    n11=0,
                    mi_bits=0.0,
                    rho_pearson=0.0,
                    marginal_p1_a=0.0,
                    marginal_p1_b=0.0,
                )
            )
            continue

        raw_seconds = end_s - start_s + 1
        sliced_a = _slice_to_intersection(sa.epoch_s, sa.signs, start_s, raw_seconds)
        sliced_b = _slice_to_intersection(sb.epoch_s, sb.signs, start_s, raw_seconds)
        keep_mask = (sliced_a != 0) & (sliced_b != 0)

        bits_a = (sliced_a[keep_mask] > 0).astype(np.uint8)
        bits_b = (sliced_b[keep_mask] > 0).astype(np.uint8)
        n00, n01, n10, n11 = joint_counts_1bit(bits_a, bits_b)

        cell = PairMonthCell(
            asset_a=asset_a,
            asset_b=asset_b,
            month=month,
            raw_intersection_seconds=raw_seconds,
            n_kept=n00 + n01 + n10 + n11,
            n00=n00,
            n01=n01,
            n10=n10,
            n11=n11,
            mi_bits=mi_from_counts(n00, n01, n10, n11),
            rho_pearson=pearson_from_counts(n00, n01, n10, n11),
            marginal_p1_a=(n10 + n11) / (n00 + n01 + n10 + n11)
            if (n00 + n01 + n10 + n11) > 0
            else 0.0,
            marginal_p1_b=(n01 + n11) / (n00 + n01 + n10 + n11)
            if (n00 + n01 + n10 + n11) > 0
            else 0.0,
        )
        per_month.append(cell)
        pool[0] += n00
        pool[1] += n01
        pool[2] += n10
        pool[3] += n11
        if verbose:
            print(
                f"[mi] {asset_a}/{asset_b} {month}: "
                f"n_kept={cell.n_kept:>10,}  MI={cell.mi_bits:.5f}  "
                f"rho={cell.rho_pearson:+.4f}"
            )

    pool_n00, pool_n01, pool_n10, pool_n11 = pool
    pool_n = pool_n00 + pool_n01 + pool_n10 + pool_n11
    return PairPoolResult(
        asset_a=asset_a,
        asset_b=asset_b,
        months=tuple(months),
        pool_n_kept=pool_n,
        pool_n00=pool_n00,
        pool_n01=pool_n01,
        pool_n10=pool_n10,
        pool_n11=pool_n11,
        pool_mi_bits=mi_from_counts(pool_n00, pool_n01, pool_n10, pool_n11),
        pool_rho_pearson=pearson_from_counts(
            pool_n00, pool_n01, pool_n10, pool_n11
        ),
        pool_marginal_p1_a=(pool_n10 + pool_n11) / pool_n if pool_n > 0 else 0.0,
        pool_marginal_p1_b=(pool_n01 + pool_n11) / pool_n if pool_n > 0 else 0.0,
        per_month=tuple(per_month),
    )


@dataclass(frozen=True)
class PairwiseMatrixResult:
    assets: tuple[str, ...]
    months: tuple[str, ...]
    mi_matrix: pd.DataFrame  # symmetric, NaN diagonal, bits
    rho_matrix: pd.DataFrame  # symmetric, NaN diagonal
    per_month_long: pd.DataFrame
    pool_summary_long: pd.DataFrame  # one row per pair (pool stats)


def compute_pairwise_mi_matrix(
    assets: list[str],
    months: list[str],
    input_root: Path,
    max_rows: int | None = None,
    verbose: bool = True,
) -> PairwiseMatrixResult:
    """Build the full pairwise 1-bit MI / Pearson pool matrix.

    Internally caches all per-asset signs for the current month while
    iterating pairs, then drops the cache before moving on, keeping
    memory at O(n_assets * cell_length) instead of O(n_pairs *
    cell_length).
    """
    from src.fusion import build_per_asset_signs  # lazy: see module-top note

    pairs = list(combinations(assets, 2))
    pool_counts: dict[tuple[str, str], list[int]] = {
        pair: [0, 0, 0, 0] for pair in pairs
    }
    per_month_rows: list[dict] = []

    for month in months:
        if verbose:
            print(f"\n[mi] === month {month} ===")
        cache: dict[str, "object"] = {}
        for asset in assets:
            cache[asset] = build_per_asset_signs(
                asset, month, input_root, max_rows=max_rows
            )

        for asset_a, asset_b in pairs:
            sa = cache[asset_a]
            sb = cache[asset_b]
            start_s = max(int(sa.epoch_s[0]), int(sb.epoch_s[0]))
            end_s = min(int(sa.epoch_s[-1]), int(sb.epoch_s[-1]))
            if end_s < start_s:
                if verbose:
                    print(
                        f"[mi] {asset_a}/{asset_b} {month}: empty intersection"
                    )
                per_month_rows.append(
                    dict(
                        asset_a=asset_a,
                        asset_b=asset_b,
                        month=month,
                        raw_intersection_seconds=0,
                        n_kept=0,
                        n00=0,
                        n01=0,
                        n10=0,
                        n11=0,
                        mi_bits=0.0,
                        rho_pearson=0.0,
                        marginal_p1_a=0.0,
                        marginal_p1_b=0.0,
                    )
                )
                continue
            raw_seconds = end_s - start_s + 1
            sliced_a = _slice_to_intersection(
                sa.epoch_s, sa.signs, start_s, raw_seconds
            )
            sliced_b = _slice_to_intersection(
                sb.epoch_s, sb.signs, start_s, raw_seconds
            )
            keep_mask = (sliced_a != 0) & (sliced_b != 0)
            bits_a = (sliced_a[keep_mask] > 0).astype(np.uint8)
            bits_b = (sliced_b[keep_mask] > 0).astype(np.uint8)
            n00, n01, n10, n11 = joint_counts_1bit(bits_a, bits_b)
            n_kept = n00 + n01 + n10 + n11
            mi = mi_from_counts(n00, n01, n10, n11)
            rho = pearson_from_counts(n00, n01, n10, n11)
            per_month_rows.append(
                dict(
                    asset_a=asset_a,
                    asset_b=asset_b,
                    month=month,
                    raw_intersection_seconds=raw_seconds,
                    n_kept=n_kept,
                    n00=n00,
                    n01=n01,
                    n10=n10,
                    n11=n11,
                    mi_bits=mi,
                    rho_pearson=rho,
                    marginal_p1_a=(n10 + n11) / n_kept if n_kept > 0 else 0.0,
                    marginal_p1_b=(n01 + n11) / n_kept if n_kept > 0 else 0.0,
                )
            )
            pool_counts[(asset_a, asset_b)][0] += n00
            pool_counts[(asset_a, asset_b)][1] += n01
            pool_counts[(asset_a, asset_b)][2] += n10
            pool_counts[(asset_a, asset_b)][3] += n11
            if verbose:
                print(
                    f"[mi] {asset_a}/{asset_b} {month}: "
                    f"n_kept={n_kept:>10,}  MI={mi:.5f}  rho={rho:+.4f}"
                )
        del cache

    mi_matrix = pd.DataFrame(np.nan, index=assets, columns=assets, dtype=float)
    rho_matrix = pd.DataFrame(np.nan, index=assets, columns=assets, dtype=float)
    pool_rows: list[dict] = []
    for (asset_a, asset_b), counts in pool_counts.items():
        n00, n01, n10, n11 = counts
        n_kept = n00 + n01 + n10 + n11
        mi = mi_from_counts(n00, n01, n10, n11)
        rho = pearson_from_counts(n00, n01, n10, n11)
        mi_matrix.loc[asset_a, asset_b] = mi
        mi_matrix.loc[asset_b, asset_a] = mi
        rho_matrix.loc[asset_a, asset_b] = rho
        rho_matrix.loc[asset_b, asset_a] = rho
        pool_rows.append(
            dict(
                asset_a=asset_a,
                asset_b=asset_b,
                n_months=len(months),
                pool_n_kept=n_kept,
                pool_n00=n00,
                pool_n01=n01,
                pool_n10=n10,
                pool_n11=n11,
                pool_mi_bits=mi,
                pool_rho_pearson=rho,
                pool_marginal_p1_a=(n10 + n11) / n_kept if n_kept > 0 else 0.0,
                pool_marginal_p1_b=(n01 + n11) / n_kept if n_kept > 0 else 0.0,
            )
        )

    return PairwiseMatrixResult(
        assets=tuple(assets),
        months=tuple(months),
        mi_matrix=mi_matrix,
        rho_matrix=rho_matrix,
        per_month_long=pd.DataFrame(per_month_rows),
        pool_summary_long=pd.DataFrame(pool_rows),
    )


def recommend_subsets_by_max_mi(
    mi_matrix: pd.DataFrame, n_values: list[int] = (2, 3, 4, 5)
) -> dict[int, dict]:
    """For each n, find the n-asset subset that minimises the max pairwise
    MI inside the subset. Ties broken by total pairwise MI."""
    assets = list(mi_matrix.index)
    out: dict[int, dict] = {}
    for n in n_values:
        if n > len(assets):
            continue
        best: tuple[float, float, tuple[str, ...]] | None = None
        for subset in combinations(assets, n):
            pair_mis = [
                mi_matrix.loc[a, b]
                for a, b in combinations(subset, 2)
            ]
            if not pair_mis:
                continue
            max_mi = float(max(pair_mis))
            sum_mi = float(sum(pair_mis))
            key = (max_mi, sum_mi)
            if best is None or key < best[:2]:
                best = (max_mi, sum_mi, tuple(subset))
        if best is not None:
            out[n] = {
                "subset": list(best[2]),
                "max_pairwise_mi_bits": best[0],
                "sum_pairwise_mi_bits": best[1],
            }
    return out


def recommend_subsets_by_sum_mi(
    mi_matrix: pd.DataFrame, n_values: list[int] = (2, 3, 4, 5)
) -> dict[int, dict]:
    """For each n, find the n-asset subset that minimises the total
    (sum) of pairwise MIs inside the subset."""
    assets = list(mi_matrix.index)
    out: dict[int, dict] = {}
    for n in n_values:
        if n > len(assets):
            continue
        best: tuple[float, float, tuple[str, ...]] | None = None
        for subset in combinations(assets, n):
            pair_mis = [
                mi_matrix.loc[a, b]
                for a, b in combinations(subset, 2)
            ]
            if not pair_mis:
                continue
            sum_mi = float(sum(pair_mis))
            max_mi = float(max(pair_mis))
            key = (sum_mi, max_mi)
            if best is None or key < best[:2]:
                best = (sum_mi, max_mi, tuple(subset))
        if best is not None:
            out[n] = {
                "subset": list(best[2]),
                "sum_pairwise_mi_bits": best[0],
                "max_pairwise_mi_bits": best[1],
            }
    return out
