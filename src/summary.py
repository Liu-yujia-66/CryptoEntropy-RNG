from __future__ import annotations

"""
Shared summary helpers across Experiments 2/3/4.

Naming convention: experiment-specific functions are prefixed
`build_exp{N}_*` / `format_exp{N}_*`; generic helpers (e.g.
`period_label_from_months`) carry no prefix.

Functions:
- `build_exp2_combined_row`: assemble the per-(asset, ell, offset) summary row
  consumed by `summarize_bits_full`. Used by both transaction-time and
  1s-bar runners; varies only in `timestamp_unit` and `analysis_scope`.
- `period_label_from_months`: format a list of "YYYY-MM" strings as a
  compact window label ("2025.03", "2025.01-03", "2025"). Distinct from
  `utils.period_dir_name`, which returns directory-style names like
  "1month-2025.01" for filesystem paths.
- `format_exp2_selection_table`: render the cross-period selected-ell table
  (Window x Asset) used in `selected_ell_by_window.txt`.
"""

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.stats import summarize_bits_full
from src.utils import ASSET_ORDER


DISPLAY_NAMES: dict[str, str] = {
    "BNBUSDT": "BNB",
    "BTCUSDT": "BTC",
    "DOGEUSDT": "DOGE",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
}


def build_exp2_combined_row(
    *,
    asset: str,
    agg_level: int,
    offset: int,
    combined_bits: np.ndarray,
    combined_duration_seconds: float,
    source_files: Iterable[Path],
    timestamp_unit: str,
    analysis_scope: str,
) -> dict[str, object]:
    """Build one Exp 2 summary row for an offset's concatenated bitstream."""
    bits_per_second = (
        float(combined_bits.size / combined_duration_seconds)
        if combined_duration_seconds > 0
        else float("nan")
    )
    metadata: dict[str, object] = {
        "asset": asset,
        "date": "combined",
        "source_file": ",".join(str(p) for p in source_files),
        "timestamp_unit": timestamp_unit,
        "start_time": "",
        "end_time": "",
        "duration_seconds": combined_duration_seconds,
        "preview_duplicate_timestamps": float("nan"),
        "agg_level": agg_level,
        "offset": offset,
        "input_rows": float("nan"),
        "sampled_rows": float("nan"),
        "retained_rows": int(combined_bits.size),
        "zero_delta_count": float("nan"),
        "zero_delta_ratio": float("nan"),
        "duplicate_timestamp_count": float("nan"),
        "analysis_scope": analysis_scope,
        "bits_per_second": bits_per_second,
    }
    row = summarize_bits_full(bits=combined_bits, metadata=metadata)
    row["bits_per_second"] = bits_per_second
    return row


def period_label_from_months(months: list[str]) -> str:
    """Format a month list as a window label.

    Distinct from `utils.period_dir_name`, which returns directory-style
    "1month-YYYY.MM" strings used for filesystem paths.

    - 1 month  -> "YYYY.MM"
    - 12 months in same year -> "YYYY"
    - otherwise -> "YYYY.MM-MM" (single year) or first/last spanning label
    """
    parsed = sorted((int(m[:4]), int(m[5:])) for m in months)
    first_year, first_month = parsed[0]
    last_year, last_month = parsed[-1]
    if len(parsed) == 12 and first_year == last_year:
        return f"{first_year}"
    if len(parsed) == 1:
        return f"{first_year}.{first_month:02d}"
    return f"{first_year}.{first_month:02d}-{last_month:02d}"


def format_exp2_selection_table(
    period_selected_frames: list[tuple[list[str], pd.DataFrame]],
    intro_lines: list[str],
    display_names: dict[str, str] | None = None,
) -> str:
    """Render the Exp 2 Window x Asset selected-ell table.

    `intro_lines` is everything that appears above the table (title +
    parameter block); each entry is one line, no trailing newline.
    """
    if not period_selected_frames:
        return ""

    names = display_names or DISPLAY_NAMES
    header_assets = [asset for asset in ASSET_ORDER if asset in names]
    rows: list[tuple[str, list[str]]] = []

    for months, selected_df in period_selected_frames:
        period_label = period_label_from_months(months)
        selected_map = selected_df.set_index("asset")["selected_agg_level"].to_dict()
        values: list[str] = []
        for asset in header_assets:
            value = selected_map.get(asset)
            values.append("-" if pd.isna(value) else str(int(value)))
        rows.append((period_label, values))

    window_width = max(len("Window"), max(len(label) for label, _ in rows))
    asset_widths: list[int] = []
    for i, asset in enumerate(header_assets):
        width = max(len(names[asset]), max(len(values[i]) for _, values in rows))
        asset_widths.append(width)

    column_widths = [window_width, *asset_widths]
    header = " | ".join(
        [f"{'Window':<{window_width}}"]
        + [
            f"{names[asset]:<{asset_widths[i]}}"
            for i, asset in enumerate(header_assets)
        ]
    )
    separator = "-+-".join("-" * width for width in column_widths)
    body = [
        " | ".join(
            [f"{label:<{window_width}}"]
            + [f"{values[i]:<{asset_widths[i]}}" for i in range(len(header_assets))]
        )
        for label, values in rows
    ]

    return "\n".join([*intro_lines, "", header, separator, *body, ""])
