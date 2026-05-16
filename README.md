# CryptoEntropy-RNG
A high-fidelity Random Number Generator (RNG) leveraging temporal aggregation and multi-asset fusion of cryptocurrency market dynamics. This project implements an entropy extraction pipeline validated by NIST SP800-22 and TestU01 suites, featuring a secure password generation prototype.

## Environment Setup

Create and activate a local virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Install the base dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Project Structure

```text
.
├── data/
│   ├── raw/             # original downloaded aggTrades CSV files
│   ├── interim/         # intermediate files (e.g. matplotlib config cache)
│   └── processed/       # experiment outputs (not tracked by git)
├── scripts/             # experiment runners, plot scripts, ℓ* selectors
├── src/                 # shared library modules
│   ├── data_io.py       # data loading, timestamp detection, PreparedMonthData
│   ├── bars.py          # 1-second bar pipeline (UTC bucketing + forward-fill)
│   ├── bitstream.py     # offset-based bitstream construction
│   ├── stats.py         # randomness tests (Monobit, Runs, ApEn m=5, Shannon bias, Predictability D adaptive-k + k=2)
│   ├── exp2_summary.py  # shared summary helpers used by Experiment 2 runners
│   └── utils.py         # small utilities
└── thesis/              # LaTeX thesis source
    ├── main.tex         # primary thesis manuscript
    ├── references.bib   # bibliography
    └── figures/         # figures included in the manuscript
```

## Running Experiments

### Data Overview (thesis Table 4.1)

Compute the per-asset trades/s summary across the full 15-month sample
(2025-01 to 2026-03). Reads the same monthly `aggTrades` archives as
Experiment 2 and recovers the raw `trades` count from each row's
`last_trade_id - first_trade_id + 1` interval, so a separate `trades`
endpoint download is not needed.

```bash
python scripts/data_overview.py
```

Outputs (under `data/processed/data_overview/`):

- `by_asset_month.csv` — 75 rows = 5 assets × 15 months. Columns include
  `agg_trades_count`, `raw_trades_count`, `duration_seconds`,
  `agg_trades_per_second`, `raw_trades_per_second`, `raw_to_agg_ratio`.
- `by_asset_summary.csv` — 5 rows = per-asset median and [p5, p95] across
  the 15 months for both raw and aggTrades rates. **Data source for
  thesis Table 4.1** (`tab:trades-per-second`).

### Experiment 1 — Baseline Randomness (thesis Table 4.2)

Daily-window baseline diagnostics on raw tick data; defaults to the five
assets (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `DOGEUSDT`) over
2026-01-01 to 2026-01-05 with `--aggregation-k 1`.

```bash
python scripts/exp1_baseline.py
```

Outputs (under `data/processed/experiment1/`):

- `summary_exp1_baseline_k1_full.csv` — 25 rows = 5 assets × 5 days; full
  set of diagnostics (Shannon entropy, Monobit, Runs, lag-1
  autocorrelation, longest run, etc.). **Data source for thesis Table
  4.2 (per-asset summary).**
- `bitstreams/<ASSET>/<ASSET>_<date>_bitstream.csv` — per-day bitstream
  with original timestamps.
- `plots/<ASSET>/<ASSET>_<date>_plots.png` — five-panel diagnostic plots
  (price, Δp distribution, bitstream preview, ACF, run-length).

### Experiment 2 — Temporal Aggregation

Experiment 2 has four runner variants that share the same pipeline shape
(raw aggTrades → per-asset summary CSV → plots). They differ in the aggregation
axis (transaction-time vs 1-second bars) and in the acceptance gate.

**Single-offset analysis** (offset=0, generates -log(p-value) vs ℓ curves; diagnostic):

```bash
python scripts/runner_exp2_single_offset.py
python scripts/plot_exp2_single_offset.py --summary-dir <path>
```

**All-offset, strict gate** (≥80% of offsets must pass predictability + monobit):

```bash
python scripts/runner_exp2_all_offset.py
python scripts/plot_exp2_all_offset_optimized.py --summary-dir <path>
```

**All-offset, relaxed gate** (Plan A heuristic: ≥max(3, ⌈0.03·N⌉) offsets pass, α=0.01 per offset):

```bash
python scripts/runner_exp2_all_offset_relaxed.py
```

**Time-based (1-second bars)**:

```bash
python scripts/runner_exp2_all_offset_1sbars.py
python scripts/plot_exp2_all_offset_1sbars.py --summary-dir <path>
```

After the 1sbars runner produces per-month k_acceptance CSVs, pick the
smallest acceptable ℓ under three gates (base, +runs, +runs+apen):

```bash
python scripts/select_ell_exp2_1sbars.py --summary-dir <root>
```

Edit the configuration block at the top of each runner to set assets,
periods, and ℓ ranges. Design notes:

- `Exp2 Limitations.md` — gate taxonomy and known limitations
- `Exp2 Plan A - Relaxed Gate.md` — relaxed-gate heuristic
- `Exp2 Plan B - Time-Based Aggregation.md` — 1-second bar physical-time axis

#### Appendix table ↔ data file mapping

The thesis appendix (Tables A.1 – A.6) prints only the per-(asset, month)
`selected ℓ*` values. The raw CSVs sit under
`data/processed/experiment2/` and map to the appendix tables as follows:

| Thesis appendix       | Runner                                  | CSV file                                                                                                              |
| --------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Table A.1 (single offset)            | `runner_exp2_single_offset.py`         | `single-offset-per-month(50,2000,25)/selected_ell_by_window.txt`                                                       |
| Table A.2 (strict gate, D + Monobit) | `runner_exp2_all_offset.py`            | `all-offset-per-month(50,2000,25)/selected_ell_by_window.txt` (+ per-month `all_assets_summary_exp2_selected_k.csv`)   |
| Table A.3 (strict + Runs)            | `runner_exp2_all_offset.py`            | per-month `all_assets_summary_exp2_k_acceptance.csv` in the same directory as Table A.2                                |
| Table A.4 (relaxed gate)             | `runner_exp2_all_offset_relaxed.py`    | `relaxed-all-offset-per-month(3,0.03)-(10,2000,2)/selected_ell_by_window.txt`                                          |
| Table A.5 (Bonferroni 3-month)       | `runner_exp2_all_offset_relaxed.py`    | `relaxed-all-offset-per-month-bonferroni-(10,2000,2)/selected_ell_by_window.txt`                                       |
| Table A.6 (1-second bar, three gates: base / +Runs / +Runs+ApEn) | `runner_exp2_all_offset_1sbars.py` + `select_ell_exp2_1sbars.py` | `all-offset-per-month-1sbars(10,600,1)/selected_ell_by_window.txt` |

All paths are relative to `data/processed/experiment2/`.

## Data

Raw data is not included in this repository. Download aggTrades data from [https://data.binance.vision](https://data.binance.vision) and place it under:

```text
data/raw/binance/spot/aggTrades/<ASSET>/
```

Two granularities are used:

- **Experiment 1** — daily files (e.g. `BTCUSDT-aggTrades-2026-01-01.csv`); the baseline window is 2026-01-01 to 2026-01-05 across all five assets, sitting in the first week of the last quarter (2026 Q1) of the Experiment 2 sample period. Processed outputs live under `data/processed/experiment1/`.
- **Data overview** — reads the same monthly archives as Experiment 2; processed outputs live under `data/processed/data_overview/`.
- **Experiment 2** — monthly files (e.g. `BTCUSDT-aggTrades-2025-01.csv`); processed outputs live under `data/processed/experiment2/`.

Assets used: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `DOGEUSDT`

## Thesis

The accompanying thesis manuscript lives under `thesis/` and is built from
`thesis/main.tex` against `thesis/references.bib`. The manuscript's
Methods chapter (Ch.~3) maps onto source files as follows: `src/stats.py`
provides the test battery, `src/bars.py` provides the 1-second bar pipeline,
and the runners under `scripts/` drive the all-offset acceptance loop on
both the transaction-time and physical-time axes.
