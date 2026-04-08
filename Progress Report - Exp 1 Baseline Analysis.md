# Progress Report: Experiment 1 Baseline Analysis

**Date:** April 8, 2026  
**Project:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation  
**Status:** Experiment 1 Baseline Completed

## 1. Objective

The objective of Experiment 1 was to establish a statistical baseline for raw high-frequency cryptocurrency tick data (`BTCUSDT` and `ETHUSDT`) and determine whether the corresponding sign-encoded direction sequences could be used directly as candidate random sources.

## 2. Methodology

**Data Source**  
Binance aggTrades (tick-level transaction data) covering 5 consecutive trading days for `BTCUSDT` and `ETHUSDT`.  
The current Experiment 1 baseline is therefore based on daily archived data.

**Pre-processing**  
Zero-price-change events were removed so that only non-zero price movements were retained.

**Encoding**  
Binary sign encoding was applied to consecutive price changes:  
`Delta P > 0 -> 1`, `Delta P < 0 -> 0`.

**Statistical Evaluation**  
The resulting bit sequences were evaluated using Shannon entropy, monobit statistics, runs statistics, lag-1 autocorrelation, and graphical diagnostics including price evolution, bitstream preview, and autocorrelation structure.

## 3. Key Findings

Based on the attached file `summary_exp1_baseline_k1_full.csv`, the following conclusions were obtained.

**High Marginal Entropy but Strong Dependence**  
For both BTC and ETH, Shannon entropy is generally very close to 1, and the proportion of ones remains close to 0.5. However, this apparent balance does not imply true randomness. In particular, high marginal entropy does not imply high conditional unpredictability: the sequences remain strongly predictable given recent history, which means that the effective randomness is much lower than the Shannon entropy alone would suggest.

**Strong Serial Dependence**  
The bitstream autocorrelation analysis shows strong positive lag-1 dependence, reaching approximately 0.75 for BTC and 0.82 for ETH on some days. This indicates substantial short-range persistence and violates the independence assumption required for direct randomness extraction.

**Runs-Based Evidence of Non-Random Structure**  
The runs test produces highly significant deviations from the behavior expected under an independent random sequence. This confirms that the raw sign-encoded sequences contain strong local structure.

**Long Deterministic Segments**  
Very long runs were observed in the baseline sequences, with the longest runs reaching well above hundreds of consecutive bits and, in some cases, exceeding 2000 bits. Such segments are incompatible with direct cryptographic use because they substantially reduce effective unpredictability and would make directly generated keys or passwords structurally weak.

**Raw Encoded Bit Generation Rate**  
Using the current baseline encoding, the effective directional bit generation rate is on the order of approximately 8–10 bits per second on active trading days, although this rate varies across assets and dates. This should be interpreted as an unfiltered, non-whitened bit generation rate rather than a true independent entropy rate, since the generated bits still exhibit strong dependence.

## 4. Conclusion

Experiment 1 shows that sign-encoded direction sequences derived from raw high-frequency cryptocurrency tick data are not suitable as direct random sources. Although their marginal entropy is high, they exhibit strong serial dependence and pronounced run structure. This provides a clear justification for Experiment 2, where temporal aggregation will be used to investigate whether increasing the aggregation level can suppress these dependencies and produce more randomness-like sequences.

For Experiment 2, the analysis will move from daily files to monthly archived data in order to support larger aggregation levels and more stable sequence-length comparisons. This is especially important for maintaining sufficient sequence length at larger `k` values and for preserving statistical significance in later randomness evaluation.

## 5. Attachments

- `scripts/exp1_baseline.py`  
  Baseline pipeline for loading tick data, encoding price-direction sequences, and computing summary statistics.

- `summary_exp1_baseline_k1_full.csv`  
  Full baseline statistics for `BTCUSDT` and `ETHUSDT` across 5 days.

- Plot outputs  
  Representative plots showing price evolution, price-delta distribution, bitstream preview, autocorrelation structure, and run-length behavior.
