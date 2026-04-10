from __future__ import annotations

"""
Experiment 2 all-offset transaction-time aggregation analysis.

Example:
    python scripts/exp2_all_offsets.py
"""

import argparse
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

os.environ.setdefault("MPLCONFIGDIR", str(Path("data/interim/.mplconfig").resolve()))

import numpy as np
import pandas as pd
from scipy.special import gammaincc
from scipy.stats import chi2


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

DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]
DEFAULT_MONTHS = ["2026-01", "2026-02", "2026-03"]
DEFAULT_SAMPLING_K_VALUES = [1000]
DEFAULT_MAX_ROWS = None
# DEFAULT_MAX_ROWS = 100_000
MIN_BIT_COUNT = 10000


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
class OffsetBitstream:
    offset: int
    bits: np.ndarray
    stats: dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 2 all-offset transaction-time aggregation analysis."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/raw/binance/spot/aggTrades"),
        help="Root directory containing asset subdirectories with aggTrades CSV files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/processed/experiment2/all-offset"),
        help="Root directory for all-offset Experiment 2 outputs.",
    )
    parser.add_argument(
        "--assets",
        nargs="*",
        default=DEFAULT_ASSETS,
        help="Asset directories to process.",
    )
    parser.add_argument(
        "--months",
        nargs="*",
        default=DEFAULT_MONTHS,
        help="Optional month filters such as 2026-01 2026-02 2026-03.",
    )
    parser.add_argument(
        "--sampling-k-values",
        nargs="+",
        type=int,
        default=DEFAULT_SAMPLING_K_VALUES,
        help="Candidate transaction-time aggregation levels.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help="Optional row cap per file for debugging.",
    )
    parser.add_argument(
        "--min-bit-count",
        type=int,
        default=MIN_BIT_COUNT,
        help="Minimum bit count required for an offset sequence to be considered valid.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.01,
        help="Significance level used in acceptance checks.",
    )
    parser.add_argument(
        "--pass-rate-threshold",
        type=float,
        default=0.80,
        help="Minimum fraction of valid offsets that must pass each test.",
    )
    parser.add_argument(
        "--history-length",
        type=int,
        default=1,
        help="History length used in the entropy-based predictability test.",
    )
    parser.add_argument(
        "--save-bitstreams",
        action="store_true",
        help="Save concatenated per-offset bitstreams to disk.",
    )
    return parser.parse_args()


def detect_time_unit(series: pd.Series) -> TimeUnit:
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
            "Inconsistent timestamp widths detected: "
            f"min={min_digits}, max={max_digits}"
        )

    if max_digits >= 16:
        return "us"
    if max_digits >= 13:
        return "ms"
    raise ValueError(f"Unsupported timestamp width: {max_digits} digits")


def load_aggtrades(path: Path, max_rows: int | None) -> pd.DataFrame:
    df = pd.read_csv(path, names=AGGTRADE_COLUMNS, nrows=max_rows)
    if df.empty:
        raise ValueError(f"No rows found in input file: {path}")
    df["price"] = pd.to_numeric(df["price"], errors="raise")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="raise").astype("int64")
    df["aggregate_trade_id"] = pd.to_numeric(
        df["aggregate_trade_id"], errors="raise"
    ).astype("int64")
    return df


def prepare_aggtrades(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values("aggregate_trade_id").reset_index(drop=True).copy()
    time_unit = detect_time_unit(ordered["timestamp"])
    ordered["event_time"] = convert_timestamps(ordered["timestamp"], time_unit)
    ordered.attrs["timestamp_unit"] = time_unit
    return ordered


def build_file_context(path: Path, df: pd.DataFrame) -> FileAnalysisContext:
    preview_duplicate_timestamps = int(df["timestamp"].head(5).duplicated().sum())
    start_time = df["event_time"].iloc[0]
    end_time = df["event_time"].iloc[-1]
    month_label = "-".join(path.stem.split("-")[-3:])
    return FileAnalysisContext(
        source_file=str(path),
        month_label=month_label,
        timestamp_unit=cast(TimeUnit, df.attrs["timestamp_unit"]),
        start_time_iso=start_time.isoformat(),
        end_time_iso=end_time.isoformat(),
        duration_seconds=float((end_time - start_time).total_seconds()),
        preview_duplicate_timestamps=preview_duplicate_timestamps,
    )


def convert_timestamps(timestamp_series: pd.Series, time_unit: TimeUnit) -> pd.Series:
    timestamp_array = timestamp_series.to_numpy(dtype="int64")
    converted = pd.to_datetime(timestamp_array, unit=time_unit, utc=True)
    return pd.Series(converted, index=timestamp_series.index)


def shannon_entropy_from_bits(bits: np.ndarray) -> float:
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
    if bits.size == 0:
        return 0
    return 1 + int(np.sum(bits[1:] != bits[:-1]))


def longest_run(bits: np.ndarray, value: int) -> int:
    max_run = 0
    current = 0
    for bit in bits:
        if bit == value:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def monobit_test(bits: np.ndarray) -> tuple[float, float]:
    n = bits.size
    if n == 0:
        return float("nan"), float("nan")
    s = int(2 * bits.sum() - n)
    z_score = float(abs(s) / math.sqrt(n))
    p_value = float(math.erfc(z_score / math.sqrt(2)))
    return float(z_score), float(p_value)


def runs_test(bits: np.ndarray) -> tuple[float, float]:
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


def lag_autocorrelation(bits: np.ndarray, lag: int) -> float:
    if lag <= 0 or lag >= bits.size:
        return float("nan")
    x = bits[:-lag].astype(float)
    y = bits[lag:].astype(float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def approximate_entropy_test(
    bits: np.ndarray, block_size: int = 2
) -> tuple[float, float]:
    n = bits.size
    if n < max(16, block_size + 2):
        return float("nan"), float("nan")

    bits_ext = np.concatenate([bits, bits[: block_size + 1]])

    def phi(m: int) -> float:
        counts = np.zeros(2**m, dtype=float)
        for i in range(n):
            pattern = 0
            for j in range(m):
                pattern = (pattern << 1) | int(bits_ext[i + j])
            counts[pattern] += 1.0
        probs = counts / n
        valid = probs > 0
        return float(np.sum(probs[valid] * np.log(probs[valid])))

    phi_m = phi(block_size)
    phi_m1 = phi(block_size + 1)
    ap_en = float(phi_m - phi_m1)
    chi_sq = float(2.0 * n * (math.log(2) - ap_en))
    p_value = float(gammaincc(2 ** (block_size - 1), chi_sq / 2.0))
    return ap_en, p_value


def entropy_predictability_test(
    bits: np.ndarray, history_length: int = 1
) -> tuple[float, float, float]:
    n = bits.size
    m = history_length
    if m < 1:
        raise ValueError("history_length must be >= 1")
    if n <= m + 1:
        return float("nan"), float("nan"), float("nan")

    total = n - m
    num_contexts = 2**m
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
    unconditional_entropy = 0.0
    for p in p_next:
        if p > 0:
            unconditional_entropy -= p * math.log2(p)

    conditional_entropy = 0.0
    for context in range(num_contexts):
        if context_counts[context] == 0:
            continue
        probs = joint_counts[context] / context_counts[context]
        h_context = 0.0
        for p in probs:
            if p > 0:
                h_context -= p * math.log2(p)
        conditional_entropy += (context_counts[context] / total) * h_context

    mutual_information_bits = float(unconditional_entropy - conditional_entropy)

    g_stat = 0.0
    for context in range(num_contexts):
        if context_counts[context] == 0:
            continue
        for bit in range(2):
            observed = joint_counts[context, bit]
            if observed == 0:
                continue
            expected = context_counts[context] * p_next[bit]
            if expected > 0:
                g_stat += 2.0 * observed * math.log(observed / expected)

    observed_context_count = int(np.sum(context_counts > 0))
    degrees_of_freedom = (observed_context_count - 1) * (2 - 1)
    if degrees_of_freedom <= 0:
        return mutual_information_bits, float("nan"), float("nan")

    p_value = float(1.0 - chi2.cdf(g_stat, degrees_of_freedom))
    return mutual_information_bits, float(g_stat), p_value


def build_offset_bitstream(
    df: pd.DataFrame, sampling_k: int, offset: int
) -> OffsetBitstream:
    if sampling_k < 1:
        raise ValueError("sampling_k must be >= 1")
    if offset < 0 or offset >= sampling_k:
        raise ValueError("offset must satisfy 0 <= offset < sampling_k")

    sampled = df.iloc[offset::sampling_k].copy()
    sampled["price_delta"] = sampled["price"].diff()
    zero_delta_count = int((sampled["price_delta"] == 0).sum())

    bit_df = sampled.loc[
        sampled["price_delta"] != 0,
        ["aggregate_trade_id", "timestamp", "price", "price_delta"],
    ].copy()
    bit_df = bit_df.dropna(subset=["price_delta"])
    bit_df["bit"] = (bit_df["price_delta"] > 0).astype(int)

    stats = {
        "sampling_k": int(sampling_k),
        "offset": int(offset),
        "input_rows": int(len(df)),
        "sampled_rows": int(len(sampled)),
        "retained_rows": int(len(bit_df)),
        "zero_delta_count": zero_delta_count,
        "zero_delta_ratio": (
            zero_delta_count / len(sampled) if len(sampled) else float("nan")
        ),
        "duplicate_timestamp_count": int(sampled["timestamp"].duplicated().sum()),
    }
    return OffsetBitstream(
        offset=offset,
        bits=bit_df["bit"].to_numpy(dtype=int),
        stats=stats,
    )


def build_all_offset_bitstreams(
    df: pd.DataFrame, sampling_k: int
) -> list[OffsetBitstream]:
    if sampling_k < 1:
        raise ValueError("sampling_k must be >= 1")
    return [
        build_offset_bitstream(df=df, sampling_k=sampling_k, offset=offset)
        for offset in range(sampling_k)
    ]


def summarize_bits(
    bits: np.ndarray,
    history_length: int,
    metadata: dict[str, object],
) -> dict[str, object]:
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


def save_bitstream(bits: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"bit": bits.astype(int)}).to_csv(output_path, index=False)


def filter_month_files(files: list[Path], months: list[str] | None) -> list[Path]:
    if not months:
        return files
    month_suffixes = tuple(f"{month}.csv" for month in months)
    return [path for path in files if path.name.endswith(month_suffixes)]


def build_monthly_row(
    asset: str,
    history_length: int,
    file_context: FileAnalysisContext,
    bitstream: OffsetBitstream,
) -> dict[str, object]:
    bits_per_second = (
        float(bitstream.bits.size / file_context.duration_seconds)
        if file_context.duration_seconds > 0
        else float("nan")
    )
    return summarize_bits(
        bits=bitstream.bits,
        history_length=history_length,
        metadata={
            "asset": asset,
            "date": file_context.month_label,
            "source_file": file_context.source_file,
            "timestamp_unit": file_context.timestamp_unit,
            "start_time": file_context.start_time_iso,
            "end_time": file_context.end_time_iso,
            "duration_seconds": file_context.duration_seconds,
            "preview_duplicate_timestamps": file_context.preview_duplicate_timestamps,
            **bitstream.stats,
            "analysis_scope": "monthly_offset",
            "bits_per_second": bits_per_second,
        },
    )


def build_combined_row(
    asset: str,
    sampling_k: int,
    offset: int,
    combined_bits: np.ndarray,
    combined_duration_seconds: float,
    source_files: list[Path],
    history_length: int,
) -> dict[str, object]:
    bits_per_second = (
        float(combined_bits.size / combined_duration_seconds)
        if combined_duration_seconds > 0
        else float("nan")
    )
    combined_summary = summarize_bits(
        bits=combined_bits,
        history_length=history_length,
        metadata={
            "asset": asset,
            "date": "combined",
            "source_file": ",".join(str(path) for path in source_files),
            "timestamp_unit": "mixed",
            "start_time": "",
            "end_time": "",
            "duration_seconds": combined_duration_seconds,
            "preview_duplicate_timestamps": float("nan"),
            "sampling_k": sampling_k,
            "offset": offset,
            "input_rows": float("nan"),
            "sampled_rows": float("nan"),
            "retained_rows": int(combined_bits.size),
            "zero_delta_count": float("nan"),
            "zero_delta_ratio": float("nan"),
            "duplicate_timestamp_count": float("nan"),
            "analysis_scope": "combined_offset",
            "bits_per_second": bits_per_second,
        },
    )
    combined_summary["bits_per_second"] = bits_per_second
    return combined_summary


def summarize_acceptance(
    combined_df: pd.DataFrame,
    min_bit_count: int,
    alpha: float,
    pass_rate_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []

    grouped = combined_df.groupby(["asset", "sampling_k"], sort=True)
    for key, group in grouped:
        asset, sampling_k = cast(tuple[str, int], key)
        valid = group[group["bit_count"] >= min_bit_count].copy()
        valid_offset_count = int(len(valid))
        total_offset_count = int(len(group))

        if valid.empty:
            selection_rows.append(
                {
                    "asset": asset,
                    "sampling_k": sampling_k,
                    "total_offset_count": total_offset_count,
                    "valid_offset_count": 0,
                    "valid_offset_ratio": 0.0,
                    "predictability_pass_rate": float("nan"),
                    "monobit_pass_rate": float("nan"),
                    "runs_pass_rate": float("nan"),
                    "approximate_entropy_pass_rate": float("nan"),
                    "avg_bits_per_second": float("nan"),
                    "min_bit_count_required": min_bit_count,
                    "alpha": alpha,
                    "pass_rate_threshold": pass_rate_threshold,
                    "is_acceptable": False,
                }
            )
            continue

        predictability_pass_rate = float(
            (valid["predictability_pvalue"] >= alpha).mean()
        )
        monobit_pass_rate = float((valid["monobit_pvalue"] >= alpha).mean())
        runs_pass_rate = float((valid["runs_pvalue"] >= alpha).mean())
        approximate_entropy_pass_rate = float(
            (valid["approximate_entropy_pvalue"] >= alpha).mean()
        )
        avg_bits_per_second = float(valid["bits_per_second"].mean())
        is_acceptable = bool(
            predictability_pass_rate >= pass_rate_threshold
            and monobit_pass_rate >= pass_rate_threshold
            and runs_pass_rate >= pass_rate_threshold
        )

        selection_rows.append(
            {
                "asset": asset,
                "sampling_k": sampling_k,
                "total_offset_count": total_offset_count,
                "valid_offset_count": valid_offset_count,
                "valid_offset_ratio": valid_offset_count / total_offset_count,
                "predictability_pass_rate": predictability_pass_rate,
                "monobit_pass_rate": monobit_pass_rate,
                "runs_pass_rate": runs_pass_rate,
                "approximate_entropy_pass_rate": approximate_entropy_pass_rate,
                "avg_bits_per_second": avg_bits_per_second,
                "min_bit_count_required": min_bit_count,
                "alpha": alpha,
                "pass_rate_threshold": pass_rate_threshold,
                "is_acceptable": is_acceptable,
            }
        )

    selection_df = pd.DataFrame(selection_rows).sort_values(["asset", "sampling_k"])

    for asset, group in selection_df.groupby("asset", sort=True):
        acceptable = group[group["is_acceptable"]].sort_values("sampling_k")
        if acceptable.empty:
            selected_rows.append(
                {
                    "asset": asset,
                    "selected_k": float("nan"),
                    "selection_status": "no_acceptable_k",
                }
            )
            continue

        chosen = acceptable.iloc[0]
        selected_rows.append(
            {
                "asset": asset,
                "selected_k": int(chosen["sampling_k"]),
                "selection_status": "selected_smallest_acceptable_k",
                "predictability_pass_rate": chosen["predictability_pass_rate"],
                "monobit_pass_rate": chosen["monobit_pass_rate"],
                "runs_pass_rate": chosen["runs_pass_rate"],
                "avg_bits_per_second": chosen["avg_bits_per_second"],
            }
        )

    selected_df = pd.DataFrame(selected_rows).sort_values("asset")
    return selection_df, selected_df


def save_asset_outputs(
    output_dir: Path,
    monthly_df: pd.DataFrame,
    combined_df: pd.DataFrame,
    selection_df: pd.DataFrame,
    selected_df: pd.DataFrame,
) -> None:
    for asset in sorted(monthly_df["asset"].unique()):
        asset_output_dir = output_dir / "by_asset" / asset
        asset_output_dir.mkdir(parents=True, exist_ok=True)

        asset_monthly_df = monthly_df[monthly_df["asset"] == asset].copy()
        asset_combined_df = combined_df[combined_df["asset"] == asset].copy()
        asset_selection_df = selection_df[selection_df["asset"] == asset].copy()
        asset_selected_df = selected_df[selected_df["asset"] == asset].copy()

        monthly_path = (
            asset_output_dir / f"{asset}_summary_exp2_all_offsets_monthly.csv"
        )
        combined_path = (
            asset_output_dir / f"{asset}_summary_exp2_all_offsets_combined.csv"
        )
        selection_path = (
            asset_output_dir / f"{asset}_summary_exp2_all_offsets_k_acceptance.csv"
        )
        selected_path = (
            asset_output_dir / f"{asset}_summary_exp2_all_offsets_selected_k.csv"
        )

        asset_monthly_df.to_csv(monthly_path, index=False)
        asset_combined_df.to_csv(combined_path, index=False)
        asset_selection_df.to_csv(selection_path, index=False)
        asset_selected_df.to_csv(selected_path, index=False)

        print(f"[done] saved {asset} monthly offset summary to {monthly_path}")
        print(f"[done] saved {asset} combined offset summary to {combined_path}")
        print(f"[done] saved {asset} k acceptance summary to {selection_path}")
        print(f"[done] saved {asset} selected-k summary to {selected_path}")

    all_monthly_path = output_dir / "all_assets_summary_exp2_all_offsets_monthly.csv"
    all_combined_path = output_dir / "all_assets_summary_exp2_all_offsets_combined.csv"
    all_selection_path = (
        output_dir / "all_assets_summary_exp2_all_offsets_k_acceptance.csv"
    )
    all_selected_path = (
        output_dir / "all_assets_summary_exp2_all_offsets_selected_k.csv"
    )

    monthly_df.to_csv(all_monthly_path, index=False)
    combined_df.to_csv(all_combined_path, index=False)
    selection_df.to_csv(all_selection_path, index=False)
    selected_df.to_csv(all_selected_path, index=False)

    print(f"[done] saved all-asset monthly summary to {all_monthly_path}")
    print(f"[done] saved all-asset combined summary to {all_combined_path}")
    print(f"[done] saved all-asset k acceptance summary to {all_selection_path}")
    print(f"[done] saved all-asset selected-k summary to {all_selected_path}")


def main() -> None:
    args = parse_args()

    summary_dir_name = f"rows{args.max_rows}" if args.max_rows is not None else "full"
    output_dir = args.output_root / summary_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly_rows: list[dict[str, object]] = []
    combined_rows: list[dict[str, object]] = []

    for asset in args.assets:
        asset_dir = args.input_root / asset
        if not asset_dir.exists():
            print(f"[skip] asset directory not found: {asset_dir}")
            continue

        files = filter_month_files(sorted(asset_dir.glob("*.csv")), args.months)
        if not files:
            print(f"[skip] no csv files found under: {asset_dir}")
            continue

        for sampling_k in sorted(set(args.sampling_k_values)):
            print(f"[processing] asset={asset} k={sampling_k}")
            combined_bits_by_offset: dict[int, list[np.ndarray]] = {
                offset: [] for offset in range(sampling_k)
            }
            combined_duration_seconds = 0.0

            for path in files:
                raw_df = load_aggtrades(path, max_rows=args.max_rows)
                prepared_df = prepare_aggtrades(raw_df)
                file_context = build_file_context(path, prepared_df)
                combined_duration_seconds += file_context.duration_seconds

                for bitstream in build_all_offset_bitstreams(prepared_df, sampling_k):
                    combined_bits_by_offset[bitstream.offset].append(bitstream.bits)
                    monthly_rows.append(
                        build_monthly_row(
                            asset=asset,
                            history_length=args.history_length,
                            file_context=file_context,
                            bitstream=bitstream,
                        )
                    )

            for offset in range(sampling_k):
                offset_chunks = combined_bits_by_offset[offset]
                if not offset_chunks:
                    continue
                combined_bits = (
                    np.concatenate(offset_chunks)
                    if offset_chunks
                    else np.array([], dtype=int)
                )
                combined_rows.append(
                    build_combined_row(
                        asset=asset,
                        sampling_k=sampling_k,
                        offset=offset,
                        combined_bits=combined_bits,
                        combined_duration_seconds=combined_duration_seconds,
                        source_files=files,
                        history_length=args.history_length,
                    )
                )

                if args.save_bitstreams:
                    bitstream_path = (
                        output_dir
                        / "bitstreams"
                        / f"k_{sampling_k}"
                        / asset
                        / f"{asset}_combined_offset{offset}_k{sampling_k}.csv"
                    )
                    save_bitstream(combined_bits, bitstream_path)

    if not monthly_rows:
        print("No files processed.")
        return

    monthly_df = pd.DataFrame(monthly_rows).sort_values(
        ["asset", "sampling_k", "date", "offset"]
    )
    combined_df = pd.DataFrame(combined_rows).sort_values(
        ["asset", "sampling_k", "offset"]
    )
    selection_df, selected_df = summarize_acceptance(
        combined_df=combined_df,
        min_bit_count=args.min_bit_count,
        alpha=args.alpha,
        pass_rate_threshold=args.pass_rate_threshold,
    )

    save_asset_outputs(
        output_dir=output_dir,
        monthly_df=monthly_df,
        combined_df=combined_df,
        selection_df=selection_df,
        selected_df=selected_df,
    )


if __name__ == "__main__":
    main()
