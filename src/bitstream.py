from __future__ import annotations

"""
Shared bitstream construction utilities.

Provides offset-based bitstream building from pre-loaded numpy arrays,
used by Experiment 2 and future multi-offset or multi-asset experiments.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_io import PreparedMonthData


@dataclass(frozen=True)
class OffsetBitstream:
    offset: int
    bits: np.ndarray


def build_offset_bitstream_from_arrays(
    price: np.ndarray,
    agg_level: int,
    offset: int,
) -> OffsetBitstream:
    """
    Build a single-offset bitstream by sampling every ell-th trade starting at `offset`.

    agg_level (ℓ) is the aggregation level: one bit is produced per ell trades.
    Price deltas of zero are discarded. Remaining sign changes become bits (up=1, down=0).
    """
    if agg_level < 1:
        raise ValueError("agg_level must be >= 1")
    if offset < 0 or offset >= agg_level:
        raise ValueError("offset must satisfy 0 <= offset < agg_level")

    sampled_price = price[offset::agg_level]
    if sampled_price.size == 0:
        return OffsetBitstream(offset=offset, bits=np.array([], dtype=np.uint8))

    price_delta = np.diff(sampled_price)
    nonzero_mask = price_delta != 0
    bits = (price_delta[nonzero_mask] > 0).astype(np.uint8)
    return OffsetBitstream(offset=offset, bits=bits)


def build_all_offset_bitstreams(
    prepared: PreparedMonthData, agg_level: int
) -> list[OffsetBitstream]:
    """Build bitstreams for all ell offsets from a prepared month dataset."""
    return [
        build_offset_bitstream_from_arrays(
            price=prepared.price,
            agg_level=agg_level,
            offset=offset,
        )
        for offset in range(agg_level)
    ]


def save_bitstream(bits: np.ndarray, output_path: Path) -> None:
    """Save a bitstream array to a single-column CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"bit": bits.astype(int)}).to_csv(output_path, index=False)
