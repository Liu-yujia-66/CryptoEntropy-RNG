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
│   ├── raw/                  # original downloaded aggTrades CSV files
│   ├── interim/              # intermediate files (e.g. matplotlib config cache)
│   └── processed/            # experiment outputs (not tracked by git)
├── scripts/                  # experiment runners, plot scripts, ℓ* selectors,
│                             #   aggregators
├── src/                      # shared library modules
│   ├── data_io.py            # data loading, timestamp detection, PreparedMonthData
│   ├── bars.py               # 1-second bar pipeline (UTC bucketing + forward-fill)
│   ├── bitstream.py          # offset-based bitstream construction
│   ├── stats.py              # in-house tests (Monobit, Runs, ApEn m=5, Shannon
│   │                         #   bias, Predictability D adaptive-k + k=2)
│   ├── nist_extended.py      # nistrng wrapper (SP800-22 R1A: BlockFrequency,
│   │                         #   CumSum F/B, LongestRun, DFT, Serial m/m-1)
│   ├── testu01_alphabit.py   # Python wrapper for the TestU01 Alphabit driver
│   ├── battery.py            # 3-battery orchestrator (stats + nistrng + Alphabit)
│   │                         #   + sanity-bracket schema for Exp 3 / Exp 4
│   ├── summary.py            # shared summary helpers (used by Exp 2 runners)
│   └── utils.py              # small utilities
├── tools/                    # TestU01 C build artefacts (binaries git-ignored)
│   ├── build_testu01.sh      # builds vendored TestU01 1.2.3 into a no-space
│   │                         #   path under ~/.cache/cryptoentropy-rng/testu01/
│   ├── Makefile              # links the two C binaries against that install
│   ├── alphabit_probe.c      # Phase 0 single-stream probe (debug)
│   └── alphabit_driver.c     # batch driver used by the Exp 3 / Exp 4 pipeline
├── vendor/                   # TestU01 1.2.3 source tree (git-ignored,
│                             #   fetched per Experiment 3 prerequisites)
└── thesis/                   # LaTeX thesis source
    ├── main.tex              # primary thesis manuscript
    ├── references.bib        # bibliography
    └── figures/              # figures included in the manuscript
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

### Experiment 3 — Extended Battery (NIST + TestU01 Alphabit)

Exp 3 takes the (asset, month, ℓ\*) cells selected by Exp 2's 1-second-bar
gates and runs an extended 29-sub-test battery on each cell's all-offset
streams:

- **5 from `src/stats.py`** (re-used from Exp 1/2 — D adaptive-k, D k=2,
  Monobit, Runs, ApEn m=5)
- **7 from nistrng SP800-22 R1A** — BlockFrequency, CumSum forward + backward,
  LongestRun, DFT, Serial m + m-1
- **17 from TestU01 Alphabit** — 4 MultinomialBitsOver, 2 HammingIndep, 1
  HammingCorr, plus RandomWalk1 H/M/J/R/C at L=64 and L=320. TestU01 itself
  skips its longer-block sub-tests on short streams (11 / 16 / 17 results at
  ≤5K / 10K–50K / ≥100K bits respectively), so per-offset output is 23–29
  rows depending on bit count.

#### Prerequisite: build TestU01

The Alphabit sub-tests run via a small C driver linked against the official
TestU01 1.2.3 library. Fetch the source into `vendor/TestU01-1.2.3/`
(download from <http://simul.iro.umontreal.ca/testu01/tu01.html>), then:

```bash
bash tools/build_testu01.sh    # configures + builds + installs to
                               #   ~/.cache/cryptoentropy-rng/testu01/
                               #   (a no-space path; TestU01 libtool can't
                               #    cope with the space in "Master Thesis")
make -C tools                  # compiles alphabit_probe + alphabit_driver
```

macOS arm64 (Apple clang) is the supported platform. Both compiled binaries
are git-ignored — rebuild whenever `tools/*.c` or the TestU01 install change.

#### Sanity check (one-off, before the main runner)

Calibrates each sub-test's type-I rate on `/dev/urandom` across six length
brackets (5K / 10K / 25K / 50K / 100K / 200K). One subprocess per bracket
runs in fresh-Python isolation (works around a cumulative-state SIGKILL on
the 100K bracket); resume-friendly via per-bracket partial CSVs.

```bash
python scripts/runner_exp3_sanity_check.py             # all 6 brackets, K=1000
python scripts/runner_exp3_sanity_check.py --bracket 100K   # one bracket
SANITY_K=10 python scripts/runner_exp3_sanity_check.py      # quick smoke (~1 min)
```

Output: `data/processed/experiment3/sanity_check/sanity_validity_matrix-k1000.csv`
(174 rows = 29 sub-tests × 6 brackets, three-state status:
`passed` / `failed` / `not_run`). The main runner reads this file once.

#### Main battery (chained: battery → aggregate → plot)

`runner_exp3_battery.py` runs one self-contained pipeline per gate listed
in `GATES`. Edit the constant at the top of the runner to add/remove gates;
the default is `["base", "runs"]` and runs both back-to-back (~70–100 min
total at MAX_WORKERS=5).

```bash
python scripts/runner_exp3_battery.py
```

For each gate the runner:

1. Re-reads Exp 2's per-month `is_acceptable*` CSV column to pick that gate's
   (asset, month, ℓ\*) cells (with a cross-check against
   `selected_ell_by_window.txt`),
2. Runs the 29-sub-test battery on all-offset streams (one
   `alphabit_driver` subprocess per cell, batched over all qualifying offsets),
3. Auto-chains `aggregate_exp3_battery.py --gate <gate>` →
   `plot_exp3.py --gate <gate>`.

The two downstream scripts also work standalone (`--gate base|runs|apen`).
Per-gate failures are isolated: a cell-level exception in one gate skips
that gate's aggregate/plot but does not abort subsequent gates.

#### Output layout (per gate)

```text
data/processed/experiment3/
├── sanity_check/                            # gate-independent
│   └── sanity_validity_matrix-k1000.csv
└── {gate}-gate/                             # one such tree per entry in GATES
    ├── per_cell_pvalues.csv                 # runner output: long-format,
    │                                        #   sorted by (asset, month,
    │                                        #   offset, sub_test)
    ├── per_cell_verdict.csv                 # aggregate output: N cells ×
    │                                        #   29 sub-tests, three-state
    │                                        #   verdict PASS/FAIL/INVALID/NOT_RUN
    ├── per_asset_summary.csv                # aggregate output: 5 assets ×
    │                                        #   29 sub-tests, the main result
    │                                        #   (plan §1.6 schema)
    └── figures/
        ├── pass_rate_per_asset.png          # plot output
        └── length_vs_pvalue.png             # plot output
```

`INVALID` (sub-test ran but every offset landed in a sanity-failed bracket)
and `NOT_RUN` (TestU01 length-skipped the sub-test) are reported separately
so the cell verdict preserves the Phase 5 three-state record; both stay out
of the admissible denominator.

## Data

Raw data is not included in this repository. Download aggTrades data from [https://data.binance.vision](https://data.binance.vision) and place it under:

```text
data/raw/binance/spot/aggTrades/<ASSET>/
```

Two granularities are used:

- **Experiment 1** — daily files (e.g. `BTCUSDT-aggTrades-2026-01-01.csv`); the baseline window is 2026-01-01 to 2026-01-05 across all five assets, sitting in the first week of the last quarter (2026 Q1) of the Experiment 2 sample period. Processed outputs live under `data/processed/experiment1/`.
- **Data overview** — reads the same monthly archives as Experiment 2; processed outputs live under `data/processed/data_overview/`.
- **Experiment 2** — monthly files (e.g. `BTCUSDT-aggTrades-2025-01.csv`); processed outputs live under `data/processed/experiment2/`.
- **Experiment 3** — re-uses the same monthly archives as Experiment 2 (driven by Exp 2's selected ℓ\* per (asset, month)); processed outputs live under `data/processed/experiment3/`.

Assets used: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `DOGEUSDT`

## Thesis

The accompanying thesis manuscript lives under `thesis/` and is built from
`thesis/main.tex` against `thesis/references.bib`. Source-file mapping by
chapter:

- **Ch.~3 (Methods).** `src/bars.py` is the 1-second-bar pipeline,
  `src/bitstream.py` is the all-offset encoding, `src/stats.py` /
  `src/nist_extended.py` / `src/testu01_alphabit.py` are the three
  independent batteries, and `src/battery.py` is the battery-neutral
  orchestrator that backs `full_battery()`.
- **Ch.~4 (Experiments).** The runners under `scripts/` drive each
  experiment's acceptance loop on both the transaction-time and
  physical-time axes (Exp 1 / Exp 2), then the 29-sub-test extended
  battery on Exp 2's selected ℓ\* (Exp 3, see above).
