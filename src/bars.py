from __future__ import annotations

"""
Time-based aggregation: aggTrades -> 1-second close-price bars.

Returns a `PreparedMonthData` whose `price` field is the per-second close
price (last trade in each second). Empty seconds are forward-filled, which
yields zero price-deltas that the existing `build_offset_bitstream_from_arrays`
filter discards. This keeps the all-offset / gate / runner stack untouched:
the only change is the source of `prepared.price`.

Usage:
    from src.bars import prepare_month_bars
    prepared = prepare_month_bars(path, max_rows=None)
    # prepared.price is a 1-second close array; pass to existing
    # build_offset_bitstream_from_arrays / build_all_offset_bitstreams.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_io import (
    FileAnalysisContext,
    PreparedMonthData,
    detect_time_unit,
    load_aggtrades,
)


@dataclass(frozen=True)
class BarsCoverage:
    """Per-month diagnostic of how many calendar seconds saw a trade.

    Empty seconds are forward-filled with the previous close, producing zero
    deltas that the bitstream filter discards. This metric quantifies how
    much of the wall-clock time actually carried entropy.
    """

    month_label: str
    seconds_total: int
    seconds_with_trades: int

    @property
    def coverage(self) -> float:
        return self.seconds_with_trades / self.seconds_total


def prepare_month_bars(
    path: Path, max_rows: int | None
) -> tuple[PreparedMonthData, BarsCoverage]:
    """Load one aggTrades CSV and reduce to a 1-second close-price series.

    Empty seconds (no trade) are forward-filled with the previous close,
    producing zero deltas that the downstream bitstream builder filters out.
    `context.duration_seconds` is the number of seconds spanned (== price.size),
    so `bits / duration_seconds` gives a meaningful bits-per-wall-second rate
    capped at 1 bit/s.
    """
    raw_df = load_aggtrades(path, max_rows=max_rows)
    ordered = raw_df.sort_values("aggregate_trade_id").reset_index(drop=True)
    time_unit = detect_time_unit(ordered["timestamp"])

    divisor = 1000 if time_unit == "ms" else 1_000_000
    ts = ordered["timestamp"].to_numpy(dtype=np.int64)
    epoch_s = ts // divisor

    last_per_sec = (
        pd.DataFrame(
            {"epoch_s": epoch_s, "price": ordered["price"].to_numpy(dtype=np.float64)}
        )
        .groupby("epoch_s", sort=True)["price"]
        .last()
    )

    start_s = int(last_per_sec.index.min())
    end_s = int(last_per_sec.index.max())
    full_index = pd.RangeIndex(start_s, end_s + 1)
    bars = last_per_sec.reindex(full_index).ffill()

    second_epoch = bars.index.to_numpy(dtype=np.int64)
    close = bars.to_numpy(dtype=np.float64)

    n_seconds_total = int(close.size)
    n_seconds_with_trades = int(last_per_sec.size)

    start_dt = pd.Timestamp(start_s, unit="s", tz="UTC")
    end_dt = pd.Timestamp(end_s, unit="s", tz="UTC")
    month_label = "-".join(path.stem.split("-")[-3:])

    print(
        f"[bars] {path.name}  seconds_total={n_seconds_total:,}  "
        f"with_trades={n_seconds_with_trades:,}  "
        f"coverage={n_seconds_with_trades / n_seconds_total:.3f}"
    )

    context = FileAnalysisContext(
        source_file=str(path),
        month_label=month_label,
        timestamp_unit=time_unit,
        start_time_iso=start_dt.isoformat(),
        end_time_iso=end_dt.isoformat(),
        duration_seconds=float(n_seconds_total),
        preview_duplicate_timestamps=0,
    )
    prepared = PreparedMonthData(
        context=context,
        aggregate_trade_id=np.arange(n_seconds_total, dtype=np.int64),
        timestamp=second_epoch * 1000,
        price=close,
    )
    coverage = BarsCoverage(
        month_label=month_label,
        seconds_total=n_seconds_total,
        seconds_with_trades=n_seconds_with_trades,
    )
    return prepared, coverage
