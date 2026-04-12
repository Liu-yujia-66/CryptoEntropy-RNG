from __future__ import annotations

"""
Shared data loading utilities for Binance aggTrades CSV files.

Provides column definitions, timestamp detection, data loading, and
prepared month data structures used across all experiments.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))

import numpy as np
import pandas as pd


AGGTRADE_COLUMNS = [
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "is_buyer_maker",
    "is_best_match",
]

TimeUnit = Literal["ms", "us"]


@dataclass(frozen=True)
class FileAnalysisContext:
    source_file: str
    month_label: str
    timestamp_unit: TimeUnit
    start_time_iso: str
    end_time_iso: str
    duration_seconds: float
    preview_duplicate_timestamps: int


@dataclass(frozen=True)
class PreparedMonthData:
    context: FileAnalysisContext
    aggregate_trade_id: np.ndarray
    timestamp: np.ndarray
    price: np.ndarray


def detect_time_unit(series: pd.Series) -> TimeUnit:
    """Detect whether timestamps are in milliseconds or microseconds."""
    if series.empty:
        raise ValueError("Cannot detect timestamp unit from an empty series")

    non_null = series.dropna()
    if non_null.empty:
        raise ValueError("Cannot detect timestamp unit from an all-null series")

    digit_widths = non_null.astype("int64").astype(str).str.len()
    min_digits = int(digit_widths.min())
    max_digits = int(digit_widths.max())
    if min_digits != max_digits:
        raise ValueError(
            f"Inconsistent timestamp widths detected: min={min_digits}, max={max_digits}"
        )

    if max_digits >= 16:
        return "us"
    if max_digits >= 13:
        return "ms"
    raise ValueError(f"Unsupported timestamp width: {max_digits} digits")


def convert_timestamps(timestamp_series: pd.Series, time_unit: TimeUnit) -> pd.Series:
    """Convert integer timestamps to UTC-aware datetime Series."""
    timestamp_array = timestamp_series.to_numpy(dtype="int64")
    converted = pd.to_datetime(timestamp_array, unit=time_unit, utc=True)
    return pd.Series(converted, index=timestamp_series.index)


def load_aggtrades(path: Path, max_rows: int | None) -> pd.DataFrame:
    """Load a Binance aggTrades CSV file and cast columns to correct types."""
    df = pd.read_csv(path, names=AGGTRADE_COLUMNS, nrows=max_rows)
    if df.empty:
        raise ValueError(f"No rows found in input file: {path}")
    df["price"] = pd.to_numeric(df["price"], errors="raise")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="raise")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="raise").astype("int64")
    df["aggregate_trade_id"] = pd.to_numeric(
        df["aggregate_trade_id"], errors="raise"
    ).astype("int64")
    return df


def filter_month_files(files: list[Path], months: list[str] | None) -> list[Path]:
    """Filter a list of CSV paths to only those matching the given YYYY-MM months."""
    if not months:
        return files
    month_suffixes = tuple(f"{month}.csv" for month in months)
    return [path for path in files if path.name.endswith(month_suffixes)]


def prepare_month_data(path: Path, max_rows: int | None) -> PreparedMonthData:
    """Load and pre-process a single month file into numpy arrays ready for analysis."""
    raw_df = load_aggtrades(path, max_rows=max_rows)
    ordered = raw_df.sort_values("aggregate_trade_id").reset_index(drop=True)
    time_unit = detect_time_unit(ordered["timestamp"])
    event_time = convert_timestamps(ordered["timestamp"], time_unit)
    preview_duplicate_timestamps = int(ordered["timestamp"].head(5).duplicated().sum())
    start_time = event_time.iloc[0]
    end_time = event_time.iloc[-1]
    month_label = "-".join(path.stem.split("-")[-3:])

    context = FileAnalysisContext(
        source_file=str(path),
        month_label=month_label,
        timestamp_unit=time_unit,
        start_time_iso=start_time.isoformat(),
        end_time_iso=end_time.isoformat(),
        duration_seconds=float((end_time - start_time).total_seconds()),
        preview_duplicate_timestamps=preview_duplicate_timestamps,
    )
    return PreparedMonthData(
        context=context,
        aggregate_trade_id=ordered["aggregate_trade_id"].to_numpy(dtype=np.int64),
        timestamp=ordered["timestamp"].to_numpy(dtype=np.int64),
        price=ordered["price"].to_numpy(dtype=np.float64),
    )
