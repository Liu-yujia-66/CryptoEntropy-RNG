from __future__ import annotations

"""
Experiment 3 main runner: N cell × ℓ* offset × 12 sub-test battery.
Cell count N depends on the GATE constant (see GATE config; plan §1.1
main result uses "runs" → 62 cells).

Reads:
- Exp 2 1sbar gate output: `all_assets_summary_exp2_k_acceptance.csv` per
  month. Selects the smallest ℓ where the gate column (chosen by GATE) is
  True per (asset, month). With GATE="runs" this reproduces the 62-cell
  sample in plan §1.4.1 (BTC 15, ETH 8, BNB 14, SOL 12, DOGE 13 — 13 cells
  excluded since their +Runs gate did not pass).
- Sanity validity matrix produced by `scripts/runner_exp3_sanity_check.py`
  (path embeds K via `sanity_check_validity_matrix-k{K}.csv`).

Pre-flight checks (fail fast before the long run):
- The gate's CSV column (e.g. `is_acceptable_with_runs` for GATE="runs")
  exists in every per-month k_acceptance.
- All per-month k_acceptance CSVs actually exist (silent missing → all
  cells skipped is a real risk).
- The (asset, month) → ℓ* selection from the CSVs matches the corresponding
  gate section of `selected_ell_by_window.txt`. If they disagree, abort
  with the mismatches printed — protects against the .txt being from a
  different gate / older run than the CSVs.
- The sanity validity matrix covers every (sub_test, bracket) the runner
  will look up; missing entries warned about up-front (defaulting to False
  in `full_battery`).

Writes `data/processed/experiment3/per_cell_pvalues-{GATE}.csv`, long-format
per plan §1.6 schema (~55K–90K rows), sorted by (asset, month, offset,
sub_test) so diffs between runs are meaningful:

    asset, month, offset, per_offset_bits, sanity_bracket,
    sub_test, p_value, sanity_valid

The cell-level verdict aggregation (per_asset_summary.csv) is a separate
downstream step — this runner only produces the raw per-(cell, offset,
sub_test) p-value table. α=0.01 is applied during aggregation, not here.

Per-offset filter: offsets with bit_count < MIN_BIT_COUNT (= 2000, same
as Exp 2 framework) are skipped entirely; they do not appear in the CSV.

Parallel: ProcessPoolExecutor with MAX_WORKERS workers, one cell per task.
BLAS thread limits set to 1 so outer ProcessPool × inner BLAS does not
oversubscribe the CPU. Sanity-runner pattern. Expected ~10–15 min for the
default 62-cell (+runs) sample at MAX_WORKERS=5 (vs ~80 min single-thread).

Checkpoint: the output CSV is rewritten every CHECKPOINT_INTERVAL completed
cells, so a crash partway through doesn't lose finished cells.

Run from project root:
    python scripts/runner_exp3_battery.py
"""

# BLAS thread limits must be set BEFORE numpy is imported, otherwise the
# outer ProcessPool × inner BLAS threads oversubscribe the CPU and slow
# everything down. Workers inherit these env vars.
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")  # macOS Accelerate

import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bars import prepare_month_bars
from src.bitstream import build_all_offset_bitstreams
from src.data_io import filter_month_files
from src.battery import (
    ALL_SUB_TESTS,
    SANITY_BRACKETS,
    bracket_for_length,
    full_battery,
)

# Configuration

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT"]

MONTHS = [
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
]

MIN_BIT_COUNT = 2000  # per-offset floor, same as Exp 2 all-offset gate
MAX_WORKERS = 5
CHECKPOINT_INTERVAL = 5  # write CSV every N completed cells

# Exp 2 gate selecting the (asset, month, ℓ) sample to feed into Exp 3.
# - "base": predictability + monobit            (loosest, most cells)
# - "runs": predictability + monobit + runs     (plan §1.1 default, 62/75)
# - "apen": predictability + monobit + runs + apen  (strictest, fewest)
# The CSV column and the .txt section header are derived from this.
GATE = "base"

# Exp 2 CSV doesn't pre-compute an `is_acceptable_with_apen` column, so we
# derive it from `is_acceptable_with_runs` and the apen pass-rate column.
# `required_columns` is checked up-front; `make_mask(df)` returns a boolean
# Series the runner uses to pick acceptable rows.
def _mask_base(df: pd.DataFrame) -> "pd.Series":
    return df["is_acceptable"].astype(bool)


def _mask_runs(df: pd.DataFrame) -> "pd.Series":
    return df["is_acceptable_with_runs"].astype(bool)


def _mask_apen(df: pd.DataFrame) -> "pd.Series":
    return df["is_acceptable_with_runs"].astype(bool) & (
        df["approximate_entropy_pass_rate"] >= df["pass_rate_threshold"]
    )


_GATE_SPEC = {
    "base": {
        "required_columns": ["is_acceptable"],
        "make_mask": _mask_base,
        "txt_section_regex": r"Gate: predictability \+ monobit\s*\n",
    },
    "runs": {
        "required_columns": ["is_acceptable_with_runs"],
        "make_mask": _mask_runs,
        "txt_section_regex": r"Gate: predictability \+ monobit \+ runs\s*\n",
    },
    "apen": {
        "required_columns": [
            "is_acceptable_with_runs",
            "approximate_entropy_pass_rate",
            "pass_rate_threshold",
        ],
        "make_mask": _mask_apen,
        "txt_section_regex": r"Gate: predictability \+ monobit \+ runs \+ apen\s*\n",
    },
}
if GATE not in _GATE_SPEC:
    raise ValueError(f"GATE must be one of {list(_GATE_SPEC)}; got {GATE!r}")
GATE_REQUIRED_COLUMNS = _GATE_SPEC[GATE]["required_columns"]
GATE_MAKE_MASK = _GATE_SPEC[GATE]["make_mask"]
GATE_TXT_REGEX = _GATE_SPEC[GATE]["txt_section_regex"]

INPUT_ROOT = Path(
    os.getenv("CRYPTOENTROPY_INPUT_ROOT", "data/raw/binance/spot/aggTrades")
)
EXP2_K_ACCEPTANCE_ROOT = Path(
    "data/processed/experiment2/all-offset-per-month-1sbars(10,600,1)"
)
SELECTED_ELL_TXT = EXP2_K_ACCEPTANCE_ROOT / "selected_ell_by_window.txt"
SANITY_MATRIX_PATH = Path(
    "data/processed/experiment3/sanity_check_validity_matrix-k1000.csv"
)
# Gate-suffixed output keeps multiple runs side-by-side without overwriting.
OUTPUT_PATH = Path(f"data/processed/experiment3/per_cell_pvalues-{GATE}.csv")

# Short → full asset name (used when parsing the .txt header)
_ASSET_SHORT_TO_FULL = {
    "BNB": "BNBUSDT",
    "BTC": "BTCUSDT",
    "DOGE": "DOGEUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}


# Helpers


def _load_sanity_matrix(path: Path) -> dict[tuple[str, str], bool]:
    """Load sanity validity matrix CSV → dict[(sub_test, bracket), passed_sanity]."""
    df = pd.read_csv(path)
    return {
        (str(r.sub_test), str(r.bracket)): bool(r.passed_sanity)
        for r in df.itertuples(index=False)
    }


def _month_dir_name(month: str) -> str:
    """Convert 'YYYY-MM' to Exp 2 1sbar directory name '1month-YYYY.MM'."""
    return f"1month-{month.replace('-', '.')}"


def _select_ell_star_for_month(month_dir: Path) -> dict[str, int | None]:
    """For one validation month, return per-asset selected ℓ* using the
    gate selected by the module-level GATE (smallest ell where
    GATE_MAKE_MASK is True). Returns None for assets that did not pass
    that gate in this month.

    Raises if the k_acceptance CSV is missing — silent all-None would
    mask "Exp 2 didn't run this month" as "no asset passed", which is a
    different (and serious) problem.
    """
    csv_path = month_dir / "all_assets_summary_exp2_k_acceptance.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing k_acceptance CSV: {csv_path}. "
            f"Did Exp 2 1sbar runner produce output for this month?"
        )
    df = pd.read_csv(csv_path)
    missing = [c for c in GATE_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"Expected columns {missing} (GATE={GATE!r}) in {csv_path}; "
            f"got {list(df.columns)}"
        )
    df = df.assign(_gate_mask=GATE_MAKE_MASK(df))
    selected: dict[str, int | None] = {}
    for asset, group in df.groupby("asset"):
        acceptable = group[group["_gate_mask"]].sort_values("agg_level")
        selected[str(asset)] = (
            int(acceptable.iloc[0]["agg_level"]) if not acceptable.empty else None
        )
    return selected


def _parse_selected_ell_txt(path: Path) -> dict[tuple[str, str], int | None]:
    """Parse `selected_ell_by_window.txt`, return the gate section selected
    by the module-level GATE as a dict[(asset, month), ell or None].
    Asset names are normalised to the full-symbol form (BNBUSDT, BTCUSDT, ...).
    """
    text = path.read_text()
    # GATE_TXT_REGEX matches the section header; the lookahead stops at the
    # next "Gate:" line (or EOF), so longer-prefix sections don't bleed in.
    pattern = GATE_TXT_REGEX + r"(.*?)(?=\nGate:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not find gate section for GATE={GATE!r} in {path}")

    section = match.group(1)
    lines = [
        l.strip() for l in section.strip().split("\n") if l.strip() and "---" not in l
    ]
    if not lines:
        raise RuntimeError(f"Empty gate section for GATE={GATE!r} in {path}")

    header = [p.strip() for p in lines[0].split("|")]
    assets_in_order = [_ASSET_SHORT_TO_FULL[h] for h in header[1:]]

    result: dict[tuple[str, str], int | None] = {}
    for line in lines[1:]:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != len(header):
            continue
        month = parts[0].replace(".", "-")
        for asset, val in zip(assets_in_order, parts[1:]):
            result[(asset, month)] = None if val == "-" else int(val)
    return result


def _verify_selection_consistency(
    from_csv: dict[tuple[str, str], int | None],
    from_txt: dict[tuple[str, str], int | None],
) -> None:
    """Cross-check (asset, month) → ℓ* between the two sources. Raise on mismatch.

    Catches the case where the .txt file is from an older Exp 2 run or
    a different gate, which would otherwise cause Exp 3 to silently work
    on the wrong cells.
    """
    all_keys = set(from_csv.keys()) | set(from_txt.keys())
    mismatches = [
        (key, from_csv.get(key), from_txt.get(key))
        for key in sorted(all_keys)
        if from_csv.get(key) != from_txt.get(key)
    ]
    if mismatches:
        lines = [
            "Selection mismatch between k_acceptance.csv and "
            f"selected_ell_by_window.txt:"
        ]
        for (asset, month), csv_val, txt_val in mismatches:
            lines.append(f"  {asset:<8} {month}: csv={csv_val}, txt={txt_val}")
        raise RuntimeError("\n".join(lines))


def _process_cell(
    asset: str,
    month: str,
    ell_star: int,
    sanity_matrix: dict[tuple[str, str], bool],
) -> list[dict]:
    """One (asset, month) cell: load 1s bars, build all ℓ* offsets,
    run full_battery on each, return long-format rows. Picklable so it
    can run in a ProcessPool worker.

    Offsets with < MIN_BIT_COUNT bits are skipped (consistent with Exp 2
    all-offset gate's valid-offset filter).
    """
    asset_dir = INPUT_ROOT / asset
    if not asset_dir.exists():
        return []
    files = filter_month_files(sorted(asset_dir.glob("*.csv")), [month])
    if not files:
        return []
    if len(files) > 1:
        # Binance monthly aggTrades are normally one file per (asset, month).
        # Take the first and warn — multi-file months would need explicit
        # concat to stay consistent with the Exp 2 ℓ* selection.
        print(
            f"  [warn] {asset} {month}: {len(files)} files match, using "
            f"{files[0].name} (full list: {[f.name for f in files]})"
        )

    prepared, _coverage = prepare_month_bars(files[0], max_rows=None)
    rows: list[dict] = []
    for bitstream in build_all_offset_bitstreams(prepared, ell_star):
        bits = bitstream.bits
        if bits.size < MIN_BIT_COUNT:
            continue
        results = full_battery(bits, sanity_matrix)
        bracket = bracket_for_length(int(bits.size))
        for sub_test, (p, valid) in results.items():
            rows.append(
                {
                    "asset": asset,
                    "month": month,
                    "offset": int(bitstream.offset),
                    "per_offset_bits": int(bits.size),
                    "sanity_bracket": bracket,
                    "sub_test": sub_test,
                    "p_value": float(p),
                    "sanity_valid": bool(valid) if valid is not None else None,
                }
            )
    return rows


# Main


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    sanity_path = project_root / SANITY_MATRIX_PATH
    selected_ell_txt_path = project_root / SELECTED_ELL_TXT
    output_path = project_root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sanity_matrix = _load_sanity_matrix(sanity_path)
    # Validate sanity matrix covers every (sub_test, bracket) lookup we'll do.
    # full_battery defaults missing keys to False (conservative), but missing
    # entries usually mean the sanity runner used a different sub-test list
    # — better to surface it now.
    expected_keys = {
        (s, b) for s in ALL_SUB_TESTS for _, b in SANITY_BRACKETS
    }
    missing_sanity = expected_keys - set(sanity_matrix.keys())
    if missing_sanity:
        print(
            f"[warn] sanity matrix missing {len(missing_sanity)} (sub_test, bracket) "
            f"entries (full_battery will default these to sanity_valid=False): "
            f"{sorted(missing_sanity)[:5]}{'...' if len(missing_sanity) > 5 else ''}"
        )

    print(f"[config] GATE={GATE!r} (required columns {GATE_REQUIRED_COLUMNS})")
    print(f"[config] sanity matrix: {len(sanity_matrix)} entries from {sanity_path}")
    print(
        f"[config] MIN_BIT_COUNT={MIN_BIT_COUNT}, MAX_WORKERS={MAX_WORKERS}, "
        f"CHECKPOINT_INTERVAL={CHECKPOINT_INTERVAL}"
    )
    print(f"[config] sub-tests ({len(ALL_SUB_TESTS)}): {ALL_SUB_TESTS}")
    print(f"[config] α=0.01 is applied downstream (per_asset_summary), not here")
    print(f"[config] output: {output_path}")

    # Pre-flight: build selection from CSVs and verify against .txt
    print("\n[pre-flight] building selection from k_acceptance CSVs ...")
    selection_csv: dict[tuple[str, str], int | None] = {}
    for month in MONTHS:
        month_dir = project_root / EXP2_K_ACCEPTANCE_ROOT / _month_dir_name(month)
        ells = _select_ell_star_for_month(month_dir)
        for asset in ASSETS:
            selection_csv[(asset, month)] = ells.get(asset)

    print(f"[pre-flight] cross-checking against {selected_ell_txt_path} ...")
    selection_txt = _parse_selected_ell_txt(selected_ell_txt_path)
    _verify_selection_consistency(selection_csv, selection_txt)
    print(
        f"[pre-flight] OK — {len(selection_csv)} (asset, month) cells "
        f"consistent across CSV and .txt"
    )

    cells_to_process = [
        (asset, month, ell)
        for (asset, month), ell in sorted(selection_csv.items())
        if ell is not None
    ]
    skipped_cells = [k for k, v in selection_csv.items() if v is None]
    print(
        f"[pre-flight] {len(cells_to_process)} cells to process, "
        f"{len(skipped_cells)} excluded (no {GATE!r}-gate-passing ell)"
    )

    # Parallel execution + per-checkpoint save
    all_rows: list[dict] = []
    completed = 0
    failed: list[tuple[str, str, str]] = []
    total_start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_cell = {
            executor.submit(_process_cell, asset, month, ell, sanity_matrix): (
                asset,
                month,
                ell,
            )
            for asset, month, ell in cells_to_process
        }
        for future in as_completed(future_to_cell):
            asset, month, ell = future_to_cell[future]
            try:
                rows = future.result()
            except Exception as exc:
                failed.append((asset, month, str(exc)))
                print(f"  [error] {asset} {month}: {exc}")
                continue

            completed += 1
            all_rows.extend(rows)
            n_valid = len(rows) // len(ALL_SUB_TESTS) if rows else 0
            elapsed = time.perf_counter() - total_start
            rate = completed / elapsed if elapsed > 0 else 0.0
            eta_min = (
                (len(cells_to_process) - completed) / rate / 60 if rate > 0 else 0.0
            )

            print(
                f"  [done {completed:>2}/{len(cells_to_process)}] "
                f"{asset:<8} {month}  ℓ*={ell:>3}  "
                f"valid_offsets={n_valid:>3}  total={len(all_rows):>7,} rows  "
                f"(~{eta_min:.1f}min remaining)"
            )

            # Trigger off (completed + failed) so consecutive failures
            # don't indefinitely delay a checkpoint.
            if (completed + len(failed)) % CHECKPOINT_INTERVAL == 0:
                pd.DataFrame(all_rows).to_csv(output_path, index=False)
                print(
                    f"    [checkpoint] saved {len(all_rows):,} rows → {output_path.name}"
                )

    # Final save — sort by (asset, month, offset, sub_test) so the CSV row
    # order is deterministic across re-runs (as_completed yields tasks in
    # completion order, which varies). Sub-test order follows ALL_SUB_TESTS
    # via a categorical to preserve the battery's natural reading order
    # (D_adaptive first, Serial last) rather than alphabetical.
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["sub_test"] = pd.Categorical(df["sub_test"], categories=ALL_SUB_TESTS, ordered=True)
        df = df.sort_values(
            ["asset", "month", "offset", "sub_test"]
        ).reset_index(drop=True)
        df["sub_test"] = df["sub_test"].astype(str)  # write as plain str, not categorical
    df.to_csv(output_path, index=False)

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[saved] {output_path}: {len(df):,} rows")
    print(f"[time] total: {total_elapsed/60:.1f}min")
    print(
        f"[stats] {completed}/{len(cells_to_process)} cells processed, "
        f"{len(skipped_cells)} excluded, {len(failed)} failed"
    )
    if failed:
        print("[failures]")
        for asset, month, exc in failed:
            print(f"  {asset} {month}: {exc}")


if __name__ == "__main__":
    main()
