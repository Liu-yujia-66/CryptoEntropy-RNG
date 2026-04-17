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
│   ├── raw/          # original downloaded aggTrades CSV files
│   ├── interim/      # intermediate files (e.g. matplotlib config cache)
│   └── processed/    # experiment outputs (not tracked by git)
├── scripts/          # experiment runners and plot scripts
└── src/              # shared library modules
    ├── data_io.py    # data loading, timestamp detection, PreparedMonthData
    ├── stats.py      # statistical tests (monobit, runs, approx entropy m=5, shannon bias, predictability adaptive-k + k=2)
    └── bitstream.py  # offset-based bitstream construction
```

## Running Experiments

### Experiment 1 — Baseline Randomness

```bash
python scripts/exp1_baseline.py
```

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
python scripts/plot_exp2_all_offsets_optimized.py --summary-dir <path>
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
periods, and ℓ ranges. See `Exp2 Limitations.md` for the gate taxonomy and
`Exp2 Plan A - Relaxed Gate.md` for the relaxed-gate design.

## Data

Raw data is not included in this repository. Download aggTrades data from [https://data.binance.vision](https://data.binance.vision) and place it under:

```text
data/raw/binance/spot/aggTrades/<ASSET>/
```

Two granularities are used:

- **Experiment 1** — daily files (e.g. `BTCUSDT-aggTrades-2026-04-01.csv`)
- **Experiment 2** — monthly files (e.g. `BTCUSDT-aggTrades-2025-01.csv`)

Assets used: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `DOGEUSDT`
