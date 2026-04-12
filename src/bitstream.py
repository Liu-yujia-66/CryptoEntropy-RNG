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
    stats: dict[str, float]


def build_offset_bitstream_from_arrays(
    aggregate_trade_id: np.ndarray,
    timestamp: np.ndarray,
    price: np.ndarray,
    sampling_k: int,
    offset: int,
) -> OffsetBitstream:
    """
    Build a single-offset bitstream by sampling every k-th trade starting at `offset`.

    Price deltas of zero are discarded. Remaining sign changes become bits (up=1, down=0).
    """
    if sampling_k < 1:
        raise ValueError("sampling_k must be >= 1")
    if offset < 0 or offset >= sampling_k:
        raise ValueError("offset must satisfy 0 <= offset < sampling_k")

    sampled_timestamp = timestamp[offset::sampling_k]
    sampled_price = price[offset::sampling_k]
    sampled_rows = int(sampled_price.size)

    if sampled_rows == 0:
        stats: dict[str, float] = {
            "sampling_k": int(sampling_k),
            "offset": int(offset),
            "input_rows": int(price.size),
            "sampled_rows": 0,
            "retained_rows": 0,
            "zero_delta_count": 0,
            "zero_delta_ratio": float("nan"),
            "duplicate_timestamp_count": 0,
        }
        return OffsetBitstream(offset=offset, bits=np.array([], dtype=np.uint8), stats=stats)

    price_delta = np.diff(sampled_price)
    zero_mask = price_delta == 0
    zero_delta_count = int(np.count_nonzero(zero_mask))
    nonzero_mask = ~zero_mask
    retained_rows = int(np.count_nonzero(nonzero_mask))
    bits = (price_delta[nonzero_mask] > 0).astype(np.uint8)

    stats = {
        "sampling_k": int(sampling_k),
        "offset": int(offset),
        "input_rows": int(price.size),
        "sampled_rows": sampled_rows,
        "retained_rows": retained_rows,
        "zero_delta_count": zero_delta_count,
        "zero_delta_ratio": (
            zero_delta_count / sampled_rows if sampled_rows else float("nan")
        ),
        "duplicate_timestamp_count": int(
            sampled_timestamp.size - np.unique(sampled_timestamp).size
        ),
    }
    return OffsetBitstream(offset=offset, bits=bits, stats=stats)


def build_all_offset_bitstreams(
    prepared: PreparedMonthData, sampling_k: int
) -> list[OffsetBitstream]:
    """Build bitstreams for all k offsets from a prepared month dataset."""
    return [
        build_offset_bitstream_from_arrays(
            aggregate_trade_id=prepared.aggregate_trade_id,
            timestamp=prepared.timestamp,
            price=prepared.price,
            sampling_k=sampling_k,
            offset=offset,
        )
        for offset in range(sampling_k)
    ]


def save_bitstream(bits: np.ndarray, output_path: Path) -> None:
    """Save a bitstream array to a single-column CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"bit": bits.astype(int)}).to_csv(output_path, index=False)
