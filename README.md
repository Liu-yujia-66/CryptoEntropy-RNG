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

This repository currently uses a minimal, script-first layout that works well in VS Code:

```text
.
├── data/      # downloaded data and generated outputs
├── scripts/   # runnable scripts, such as data collection or experiments
└── src/       # reusable Python code shared by scripts
```

Recommended workflow:

- put one-off or entry-point programs in `scripts/`
- move reusable logic into `src/`
- keep datasets and exported results in `data/`
