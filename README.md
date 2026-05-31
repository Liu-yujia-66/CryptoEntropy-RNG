# CryptoEntropy-RNG

A high-fidelity Random Number Generator (RNG) leveraging temporal
aggregation and multi-asset XOR combination of cryptocurrency market
dynamics. The pipeline runs Experiments 1–4 (raw baseline → temporal
aggregation → extended NIST + TestU01 Alphabit battery → multi-asset
XOR combination) and feeds the resulting fused streams through an
HKDF-SHA256 prototype that generates 16-character strong passwords.

Status (2026-05): all four experiments and the prototype are
complete. Pipeline outputs land under `data/processed/{data_overview,
experiment{1..4}, prototype}/`. The thesis manuscript draft lives at
[`thesis/main.tex`](thesis/main.tex).

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
│   ├── fusion.py             # Exp 4: per-asset sign streams + drop-any-zero XOR
│   │                         #   combination at the 1-second tick
│   ├── calibration.py        # Exp 4: XOR ℓ-aggregation + +Runs gate +
│   │                         #   select_ell_star_from_grid + select_witness_offset + p80
│   ├── mutual_info.py        # Exp 4: pairwise 1-bit MI / Pearson ρ utilities
│   ├── min_entropy.py        # Exp 4: NIST SP 800-90B MCV + Markov estimators
│   ├── prototype.py          # Prototype: HKDF-SHA256 (RFC 5869) + charset
│   │                         #   rejection sampling + B1/B2 baselines (salt-seeded)
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

### Experiment 4 — Multi-Asset XOR Combination

Exp 4 combines the per-asset 1-second sign bits across `n ∈ {2, 3, 4, 5}`
assets via XOR, then runs the same 29-sub-test battery as Exp 3 on the
combined stream's ℓ-XOR-aggregated outputs. A 9/6 calibration/validation
split fixes the asset subset, the aggregation level ℓ\*\_n, and the
witness offset on the first 9 months (2025-01..2025-09) and holds out
the next 6 (2025-10..2026-03) for unconditional evaluation.

```bash
# Step 1 — MI matrix on the calibration window (subset-selection diagnostic)
python scripts/runner_exp4_mi_matrix.py
python scripts/plot_exp4_mi_matrix.py

# Step 2 — exhaust all C(5,n) subsets (26 total) over the 9 calibration months
#   ~13 min on M-series; first-hit ℓ scan with +Runs gate, P80 across months
python scripts/runner_exp4_calibration_all_subsets.py

# Step 3 — validation on the held-out 6 months using the calibration picks
#   ~10 min; runs the 29-sub-test battery on each (n, month) cell and
#   auto-emits validation_summary.txt at the end
python scripts/runner_exp4_validation.py
python scripts/plot_exp4_validation.py

# Step 4 — NIST SP 800-90B min-entropy estimation on the validation streams
python scripts/runner_exp4_min_entropy.py
```

Output layout:

```text
data/processed/experiment4/
├── mi/                            # Step 1 — pairwise MI matrix
│   ├── mi_pool_matrix.csv
│   ├── mi_pool_summary.json       # subset_recommendations_by_max_pairwise_mi
│   └── figures/exp4_mi_matrix.png
├── calibration_all_subsets/       # Step 2 — 26 subsets x 9 months
│   ├── all_subsets_summary.csv    # one row per (n, subset) — throughput
│   │                              #   estimate, ℓ\*_n, witness, p(combined=1)
│   ├── all_subsets_summary.json
│   └── n{N}_<sorted-assets>/      # per-subset detail (ell_n_choice.json,
│                                  #   witness_offset.json, etc.)
├── validation/                    # Step 3 — 4 n x 6 months
│   ├── validation_summary.json    # ell\*_n / witness / output_bits / per-
│   │                              #   sub-test pass counts per n
│   ├── validation_summary.txt     # human-readable summary (auto-regenerated
│   │                              #   by summarize_exp4_validation.py)
│   ├── n{N}/per_month_verdict_matrix.csv
│   ├── n{N}/per_month_throughput.csv
│   ├── n{N}/{YYYY-MM}/fused_stream.bin       # combined stream (one bit per
│   │                                         #   byte; consumed by the
│   │                                         #   prototype as IKM)
│   ├── n{N}/{YYYY-MM}/per_offset_pvalues.csv
│   └── figures/exp4_validation_{verdict,tradeoff}.png
└── min_entropy/                   # Step 4 — SP 800-90B MCV + Markov
    ├── min_entropy_per_cell.csv
    └── min_entropy_summary.json   # per-n median + worst-month H∞ + IKM bytes
```

The calibration scan uses the ℓ grid `[1, 400]` with step 1. In the
production run, ℓ=1 is rejected by Monobit on every calibration cell, so
including it does not change the selected subsets or the reported ℓ\*_n
values; it only makes the scan grid match the thesis description exactly.

### Prototype — Password Generation

The prototype reads Exp 4's `fused_stream.bin` files, which store one
combined bit per byte. It first packs these 0/1 bytes with `np.packbits`,
then consumes disjoint 33-byte IKM blocks through HKDF-Extract →
HKDF-Expand → charset rejection sampling, and emits 16-character strong
passwords. Two salt-seeded baselines (B1 = direct uniform sampling, B2 =
salt-seeded ideal random IKM through the same HKDF pipeline) are generated
alongside for indistinguishability comparison.

```bash
# Step 1 — generate 3,000 passwords (market n in {2,3,5} + B1 + B2)
#   30 cells x 100 = 3,000 passwords; a few seconds; reads Exp 4
#   validation/n{2,3,5}/{month}/fused_stream.bin
python scripts/runner_prototype.py

# Step 2 — evaluation: pooled chi-square uniformity + Shannon entropy +
#   selected-cell position-frequency heatmap + 5-group side-by-side figure
python scripts/eval_prototype.py
```

Output layout:

```text
data/processed/prototype/
├── salt.bin                            # 32-byte HKDF salt (persisted for
│                                       #   demo reproducibility; production
│                                       #   would rotate per deployment)
├── config.json                         # full HKDF / charset parameters
├── market/n{2,3,5}/{YYYY-MM}/
│   ├── passwords.txt                   # 100 passwords per cell
│   └── metadata.json
├── baseline_b1/{YYYY-MM}/...            # secrets-style direct sampling
├── baseline_b2/{YYYY-MM}/...            # salt-seeded ideal random IKM
│                                        #   through the same pipeline
└── evaluation/
    ├── prototype_summary.txt           # data summary (regenerated each run)
    ├── prototype_analysis.txt          # interpretation + security model
    │                                   #   (hand-maintained companion)
    ├── per_cell_eval.csv               # 30 rows = 5 groups x 6 months
    ├── summary.json
    └── figures/
        ├── position_heatmap_n3_2026-03.png
        └── sidebyside_chi2_entropy.png
```

The two text files are intentionally split: `prototype_summary.txt`
holds **numbers only** and is regenerated by `eval_prototype.py` on
every run; `prototype_analysis.txt` holds the **interpretation and
security model** (target tier, Miller-Madow caveat, public-source vs
secret-salt framing, out-of-scope extensions for key generation and
public beacons) and is hand-maintained.

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
- **Experiment 4** — re-uses the same monthly archives; combines per-asset
  1-second sign bits across `n ∈ {2,3,4,5}` assets via XOR with a 9/6
  calibration/validation split (2025-01..2025-09 / 2025-10..2026-03);
  processed outputs live under `data/processed/experiment4/`.
- **Prototype** — reads Exp 4's validation `fused_stream.bin` files,
  packs their 0/1 byte-per-bit streams into IKM bytes, and emits
  16-character strong passwords plus matched B1/B2 baselines; processed
  outputs live under `data/processed/prototype/`.

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
  physical-time axes (§4.2 Exp 1 / §4.3 Exp 2), then the 29-sub-test
  extended battery on Exp 2's selected ℓ\* (§4.4 Exp 3, see above), then
  the multi-asset XOR combination with the 9/6 split (§4.5 Exp 4), and
  finally the HKDF-SHA256 password generator (Ch.~5 Prototype). Data
  source for each thesis figure / table is mapped in the per-experiment
  sections above; raw output trees sit under
  `data/processed/experiment{1..4}/` and `data/processed/prototype/`.
