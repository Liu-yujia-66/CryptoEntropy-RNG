# CryptoEntropy-RNG

CryptoEntropy-RNG is the codebase for a master's thesis on whether public
cryptocurrency market data can be turned into statistically usable entropy
input for password generation.

The project studies a four-stage experimental chain:

1. raw tick-sign baseline;
2. temporal aggregation on transaction-time and 1-second physical-time axes;
3. extended randomness auditing with NIST SP800-22 and TestU01 Alphabit;
4. multi-asset XOR combination with a calibration/validation split.

The selected streams are then passed through an HKDF-SHA256 password prototype.
The thesis manuscript is in [`thesis/main.tex`](thesis/main.tex).

## Status

The four experiments and the prototype are complete. Main outputs are written to:

```text
data/processed/
├── data_overview/
├── experiment1/
├── experiment2/
├── experiment3/
├── experiment4/
└── prototype/
```

Raw market data and most processed outputs are not tracked by git. Thesis
figures copied into `thesis/figures/` are tracked.

## Environment

Create a virtual environment and install the Python dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The extended battery also needs TestU01 for the Alphabit tests. See
[TestU01](#testu01-prerequisite).

## Data

Download Binance spot `aggTrades` data from
[data.binance.vision](https://data.binance.vision) and place it under:

```text
data/raw/binance/spot/aggTrades/<ASSET>/
```

The project uses five USDT spot pairs:

```text
BTCUSDT  ETHUSDT  BNBUSDT  SOLUSDT  DOGEUSDT
```

The thesis sample period is 2025-01 to 2026-03. The code expects monthly files
such as:

```text
data/raw/binance/spot/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-01.csv
```

## Repository Layout

```text
.
├── data/
│   ├── raw/                  # downloaded Binance aggTrades files
│   ├── interim/              # temporary caches
│   └── processed/            # generated experiment outputs
├── scripts/                  # runners, aggregators, and plotting scripts
├── src/                      # shared pipeline and test-battery code
├── tools/                    # TestU01 build wrapper and C drivers
├── thesis/                   # LaTeX thesis source and figures
└── README.md
```

Key source modules:

| Module | Role |
|---|---|
| `src/data_io.py` | Binance CSV loading and monthly data preparation |
| `src/bars.py` | 1-second bar construction and forward-fill pipeline |
| `src/bitstream.py` | all-offset bitstream construction |
| `src/stats.py` | in-house tests: Monobit, Runs, ApEn, Shannon bias, predictability `D` |
| `src/nist_extended.py` | NIST SP800-22 wrapper through `nistrng` |
| `src/testu01_alphabit.py` | Python wrapper for the TestU01 Alphabit driver |
| `src/battery.py` | shared 29-sub-test battery orchestration |
| `src/fusion.py` | multi-asset 1-second sign-bit XOR combination |
| `src/calibration.py` | Exp 4 subset search, `ell*` selection, selected output offset selection |
| `src/min_entropy.py` | MCV and Markov min-entropy estimators |
| `src/prototype.py` | HKDF-SHA256 password prototype and baselines |

## Terminology Note

The thesis prose uses the final terminology agreed for the manuscript:

| Thesis term | Older code/output term | Meaning |
|---|---|---|
| `criterion` | `gate` | A pass/fail selection rule, such as the strict, relaxed, base, or +Runs criterion. |
| `selected output offset` | `witness offset` | The fixed offset chosen during calibration to define the output stream used for throughput and prototype input. |
| `combined stream` | `fused_stream.bin`, `fused_p1`, `fusion_n` | The multi-asset XOR output stream. |

Some code, command-line options, JSON/CSV columns, and historical paths still use
the older names (`gate`, `witness`, `fused`). They are kept for compatibility with
existing processed outputs. In the thesis text and figures, these correspond to
`criterion`, `selected output offset`, and `combined stream`.

## Reproducing the Pipeline

The runners are configured through constants near the top of each script. The
default settings match the thesis runs unless noted.

### 0. Data Overview

Produces the trades/s summary used by thesis Table 4.1.

```bash
python scripts/data_overview.py
```

Main outputs:

```text
data/processed/data_overview/by_asset_month.csv
data/processed/data_overview/by_asset_summary.csv
```

### 1. Experiment 1: Raw Baseline

Runs the raw tick-sign baseline at `(asset, month)` granularity for all five
assets and all 15 months. This is the source for thesis Table 4.2 and Figure
4.1.

```bash
python scripts/runner_exp1_baseline.py
```

Main outputs:

```text
data/processed/experiment1/
├── all_assets_summary_exp1_baseline.csv
├── per_asset_summary.csv
├── per_asset_summary.md
├── per_asset_distributions.png
└── by_asset/<ASSET>/<ASSET>_summary_exp1_baseline.csv
```

### 2. Experiment 2: Temporal Aggregation

Experiment 2 compares transaction-time aggregation and 1-second-bar
physical-time aggregation. It also compares single-offset, strict all-offset,
relaxed all-offset, and 1-second-bar criteria.

```bash
# Single-offset diagnostic
python scripts/runner_exp2_single_offset.py
python scripts/plot_exp2_single_offset.py --summary-dir <summary-dir>

# Strict all-offset criterion
python scripts/runner_exp2_all_offset.py
python scripts/plot_exp2_all_offset_optimized.py --summary-dir <summary-dir>

# Relaxed all-offset criterion
python scripts/runner_exp2_all_offset_relaxed.py

# 1-second-bar all-offset criterion
python scripts/runner_exp2_all_offset_1sbars.py
python scripts/plot_exp2_all_offset_1sbars.py --summary-dir <summary-dir>

# Select ell* under base / +Runs / +Runs+ApEn criteria
python scripts/select_ell_exp2_1sbars.py --summary-dir <summary-dir>
```

The appendix tables in the thesis are generated from the selected-`ell*`
outputs under `data/processed/experiment2/`.

### TestU01 Prerequisite

Experiments 3 and 4 use TestU01 Alphabit through a C driver. Fetch TestU01
1.2.3 into `vendor/TestU01-1.2.3/`, then build the local drivers:

```bash
bash tools/build_testu01.sh
make -C tools
```

The build script installs TestU01 under `~/.cache/cryptoentropy-rng/testu01/`.
This avoids path issues caused by spaces in local directory names.

### 3. Experiment 3: Extended Battery

Experiment 3 audits the Exp 2 selected 1-second-bar streams with a 29-sub-test
universe:

- 5 in-house core tests from `src/stats.py`;
- 7 NIST SP800-22 tests through `nistrng`;
- 17 TestU01 Alphabit statistics.

First run the sanity check:

```bash
python scripts/runner_exp3_sanity_check.py
```

For a quick smoke test:

```bash
SANITY_K=10 python scripts/runner_exp3_sanity_check.py
```

Then run the main battery:

```bash
python scripts/runner_exp3_battery.py
```

Main outputs:

```text
data/processed/experiment3/
├── sanity_check/sanity_validity_matrix-k1000.csv
└── {base-gate,runs-gate}/
    ├── per_cell_pvalues.csv
    ├── per_cell_verdict.csv
    ├── per_asset_summary.csv
    └── figures/
        ├── pass_rate_per_asset.png
        └── length_vs_pvalue.png
```

The default `GATES` setting in `runner_exp3_battery.py` is `["base", "runs"]`;
in thesis terminology these are the base and +Runs criteria. The
`{base-gate,runs-gate}` directory names are historical output paths.

### 4. Experiment 4: Multi-Asset XOR Combination

Experiment 4 combines 1-second sign-bit streams across asset subsets of size
`n ∈ {2,3,4,5}`. Calibration uses 2025-01 to 2025-09; validation uses
2025-10 to 2026-03.

```bash
# Pairwise dependence diagnostic on the calibration window
python scripts/runner_exp4_mi_matrix.py
python scripts/plot_exp4_mi_matrix.py

# Exhaustive calibration over C(5,2)+C(5,3)+C(5,4)+C(5,5)=26 subsets
python scripts/runner_exp4_calibration_all_subsets.py

# Held-out validation with fixed calibration picks
python scripts/runner_exp4_validation.py
python scripts/plot_exp4_validation.py

# Min-entropy estimate on validation streams
python scripts/runner_exp4_min_entropy.py
```

The calibration scan uses the `ell = 1,...,400` grid with step 1.

Main outputs:

```text
data/processed/experiment4/
├── mi/
│   ├── mi_pool_matrix.csv
│   ├── rho_pool_matrix.csv
│   └── figures/exp4_mi_matrix.png
├── calibration_all_subsets/
│   ├── all_subsets_summary.csv
│   └── all_subsets_summary.json
├── validation/
│   ├── validation_summary.json
│   ├── validation_summary.txt
│   ├── n{N}/per_month_verdict_matrix.csv
│   ├── n{N}/per_month_throughput.csv
│   ├── n{N}/{YYYY-MM}/fused_stream.bin
│   └── figures/exp4_validation_{verdict,tradeoff}.png
└── min_entropy/
    ├── min_entropy_per_cell.csv
    └── min_entropy_summary.json
```

`fused_stream.bin` stores one combined bit per byte. The filename is historical;
the thesis calls these outputs combined streams.

### 5. Password Prototype

The prototype consumes the deployable Exp 4 validation streams for
`n ∈ {2,3,5}`. It packs the byte-per-bit streams into IKM bytes, uses
HKDF-SHA256, and maps output bytes into 16-character passwords over a
70-character alphabet.

```bash
python scripts/runner_prototype.py
python scripts/eval_prototype.py
```

Main outputs:

```text
data/processed/prototype/
├── salt.bin
├── config.json
├── market/n{2,3,5}/{YYYY-MM}/
│   ├── passwords.txt
│   └── metadata.json
├── baseline_b1/{YYYY-MM}/
├── baseline_b2/{YYYY-MM}/
└── evaluation/
    ├── prototype_summary.txt
    ├── prototype_analysis.txt
    ├── per_cell_eval.csv
    ├── summary.json
    └── figures/
        ├── position_heatmap_n3_2026-03.png
        └── sidebyside_chi2_entropy.png
```

`prototype_summary.txt` is regenerated by `eval_prototype.py`.
`prototype_analysis.txt` is hand-maintained and contains the interpretation and
security-scope notes.

## Thesis Figures

The manuscript uses copied figure files under `thesis/figures/`. Regenerate
the upstream plots first, then copy the relevant PNGs into that directory if a
figure changes.

Common figure sources:

| Thesis figure | Source script | Figure file |
|---|---|---|
| Figure 4.1 | `scripts/plot_exp1_baseline.py` | `exp1_per_asset_distributions.png` |
| Figure 4.10 | `scripts/plot_exp4_mi_matrix.py` | `exp4_mi_matrix.png` |
| Figure 4.11 | `scripts/plot_exp4_validation.py` | `exp4_validation_tradeoff.png` |
| Figure 4.12 | `scripts/plot_exp4_validation.py` | `exp4_validation_verdict.png` |
| Figure 5.1 | `scripts/plot_prototype_pipeline.py` | `prototype_pipeline.png` |
| Figure 5.2 | `scripts/eval_prototype.py` | `prototype_eval_chi2_entropy.png` |

## Thesis Build

The thesis source is:

```text
thesis/main.tex
thesis/references.bib
```

The current workflow builds the PDF in Overleaf. The repository also keeps the
Chinese working draft in `thesis-draft-chinese.md`; the submitted manuscript is
the English LaTeX version.

## Notes

- Randomness batteries are descriptive statistical audits, not a proof of
  cryptographic security.
- The password prototype is evaluated in a passive statistical setting. A real
  secret-producing deployment still needs non-public deployment-secret material.
- The repository-persisted prototype salt is for reproducibility, not production
  secrecy.
