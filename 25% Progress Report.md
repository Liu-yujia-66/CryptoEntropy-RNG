# 25% Progress Report

**Thesis Title:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**Student:** Yujia Liu (yujia.liu.9362@student.uu.se)
**Supervisor:** Andrey Shternshis (andrey.shternshis@it.uu.se)
**Subject Reviewer:** Parosh Abdulla (Parosh.Abdulla@it.uu.se)
**Department:** Information Technology, Uppsala University
**Report Date:** 2026-05-15
**Milestone:** 25% (Background, Methods, and Experiment 1 — Baseline)

---

## 1. Overview

This report covers the first quarter of the thesis work. The goal at this stage is to (i) set up the theoretical and methodological foundation, (ii) build the data pipeline over Binance spot-market `aggTrades` archives, and (iii) finish Experiment 1, which gives a quantitative baseline showing that raw high-frequency cryptocurrency tick sequences cannot be used directly as a random source. The result of Experiment 1 is what motivates the time-aggregation analysis (Experiment 2) that follows.

Three research questions have been written down:

- **RQ1.** How can we design an aggregation algorithm that extracts statistically independent random sequences from cryptocurrency price data?
- **RQ2.** To what extent can these sequences pass standard randomness tests?
- **RQ3.** Can this data-driven randomness be effectively applied to secure password generation?

This report mainly deals with the **negative side of RQ1**: whether the unaggregated baseline already passes standard randomness tests. The other research questions are addressed in later work.

## 2. Background and Methodology Foundation

**Positioning.** Random number generators are usually built in one of two ways. The first is a deterministic pseudo-random generator (PRNG) that needs a high-entropy seed. The second is a true random number generator (TRNG), for example on-chip electronic noise (Mathew et al., 2012) or a quantum source (Herrero-Collantes & Garcia-Escartin, 2017). A third research direction tries to extract randomness from publicly available high-entropy data. This thesis sits in the third group and focuses on cryptocurrency price streams, building on earlier work on financial randomness beacons (Clark & Hengartner, 2010; Chiba & Ichikawa, 2024; Landis & Bonneau, 2025).

**Methodological core.** The methodology is based on two recent papers:

1. **Entropy-based predictability test *D*** (Shternshis & Marmi, 2025), an independence test that uses the Kullback–Leibler divergence on length-*k* symbol blocks. Under H₀ = i.i.d., it asymptotically follows a χ² distribution. We use it as the main statistic, at both an adaptive *k* = ⌊0.5 log₂ *n*⌋ and a fixed *k* = 2 (the second one is used to check first-order pair dependence).
2. **All-offset construction** (Onofri et al., 2025): for each aggregation level ℓ, we build ℓ parallel bit streams from the ℓ different starting offsets, run the test battery on each one, and accept ℓ if a pass-rate criterion is met.

A few extra tests from NIST SP800-22 (Monobit, Runs, Approximate Entropy with *m* = 5) and two structural diagnostics (lag-1 autocorrelation ρ₁, longest 0/1 run length L_max) are added to cross-check the main statistic. All tests use α = 0.01.

**Data pipeline.** We download Binance public `aggTrades` monthly archives for five high-liquidity USDT spot pairs — BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, DOGEUSDT — chosen so that they cover a range of trades-per-second levels (the median raw trades/s goes from 12.6 to 50.8). The analysis window is 15 months (January 2025 to March 2026), so we end up with 5 × 15 = 75 (asset, month) cells, with monthly bit stream lengths between 10⁶ and 4 × 10⁷.

## 3. Experiment 1 — Baseline

### 3.1 Setup

Experiment 1 is the simplest case of the encoding pipeline, with ℓ = 1 and offset = 0: each `aggTrades` record becomes one bit through the sign of its price change, and zero-difference ticks are dropped. There is no aggregation and no post-processing. For every (asset, month) cell we compute: bit length *n*, bits/s, p(1), Shannon bias |H − 1|, Monobit *p*, Runs *p*, lag-1 autocorrelation ρ₁, longest run L_max, Approximate Entropy, and *D* at adaptive *k* and at fixed *k* = 2.

### 3.2 Two scope changes relative to the Initial Plan

The Initial Plan asked for two assets (BTC, ETH) with Shannon entropy and basic NIST tests. After supervisor review, two changes were made:

1. **Two assets → five assets.** Cross-asset patterns (for example, the relationship between trades/s and residual structure) are only visible when more assets are included; it also lets Experiment 1 and Experiment 2 share the same (asset, month) cell.
2. **Shannon entropy → full conditional predictability battery + structural extensions.** Because a high marginal entropy does not mean the sequence is unpredictable, the diagnostic battery was extended to include *D*, ApEn, ρ₁, and L_max. The Shannon bias is kept as a summary number only and is not used as an acceptance criterion.

### 3.3 Per-asset summary (across 15 monthly cells; α = 0.01)

| Asset | bps median | 1 − H max | ρ₁ median | Monobit rejects | Runs rejects | ApEn rejects | *D* (adaptive) rejects | *D* (*k* = 2) rejects | L_max max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC  | 10.68 | 1.94 × 10⁻³ | +0.636 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 12 039 |
| ETH  |  9.56 | 7.93 × 10⁻³ | +0.745 | 13/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15 899 |
| BNB  |  2.49 | 9.98 × 10⁻⁵ | +0.366 | 13/15 | 15/15 | 15/15 | 15/15 | 15/15 |  2 069 |
| DOGE |  2.02 | 1.35 × 10⁻⁵ | +0.477 |  8/15 | 15/15 | 15/15 | 15/15 | 15/15 |  5 071 |
| SOL  |  1.74 | 2.35 × 10⁻⁶ | +0.095 |  4/15 | 15/15 | 15/15 | 15/15 | 15/15 |    792 |

### 3.4 Key findings

1. **Conditional predictability and Runs reject on all 75 cells.** *D* (adaptive), *D* (*k* = 2), ApEn, and Runs all reject at α = 0.01 across every cell, and 73 of 75 Runs *p*-values underflow to 0. Even SOL, where p(1) is close to 0.5 and Monobit only rejects in 4 out of 15 months, is still rejected by all four conditional tests in every month. This is the clearest evidence that raw tick sequences are not random.
2. **Monobit on its own misses structure.** Fourteen cells are not rejected by Monobit (SOL 11, DOGE 7, BNB 2, ETH 2, BTC 0), and they are mostly on the lower-activity assets, where p(1) is close to 0.5 and the marginal test does not have enough power. A marginal frequency test on its own is not enough.
3. **Lag-1 autocorrelation is positive on every asset, and roughly grows with activity.** The per-asset medians are +0.745 (ETH), +0.636 (BTC), +0.477 (DOGE), +0.366 (BNB), +0.095 (SOL). This is consistent with persistent same-side order flow and trade-sign long memory (Lillo & Farmer, 2004), and not with the bid-ask-bounce reversal reported by Shternshis & Marmi (2025) on SNAP/F/CCL at the tick scale.
4. **The longest runs are 2–3 orders of magnitude above the i.i.d. baseline.** The maximum L_max values across the 15 months are 12 039 (BTC), 15 899 (ETH), 5 071 (DOGE), 2 069 (BNB), and 792 (SOL). For these stream lengths, the i.i.d. expectation E[L_max] ≈ log₂ *n* is about 20–25. Any password or seed sampled inside such a run would just be a string of constant bits.
5. **The baseline bit production stays below 16 bps.** Per-asset medians go from 1.74 (SOL) to 10.68 (BTC) bits/s. The ranking does not exactly follow raw trades/s because the per-asset zero-delta ratio varies (SOL is about 0.59, while BNB is about 0.43). This is the ceiling for any throughput estimate that uses aggregation later on.

### 3.5 Conclusion of Experiment 1

Experiment 1 gives a **quantitative negative result**: raw tick sign sequences are not acceptable as a random source. Runs and the conditional predictability battery reject on all 75 cells, and the longest-run statistics show structural failure modes that are directly relevant to cryptographic use. This result gives three design points for Experiment 2:

(i) **Aggregation is required.** No acceptance rule on raw tick streams can be non-empty.

(ii) **First-order residual structure as a comparison target.** The lag-1 autocorrelation is positive on every asset; this becomes the target when Experiment 2 compares two aggregation axes.

(iii) **Throughput ceiling.** The 1–16 bps baseline is the ceiling for any throughput estimate based on aggregation later in the thesis.

## 4. Current Status

| Item | Status |
|---|---|
| Background and literature review (Ch 1 + Ch 2) | Drafted |
| Methods (Ch 3 - encoding, all-offset construction, test battery, acceptance gates) | Drafted |
| Data pipeline over Binance monthly `aggTrades` archives | Done (5 assets × 15 months) |
| Experiment 1 - runner, diagnostics, summary tables, distribution plots | Done |
| Thesis §4.2 - Experiment 1 write-up | Drafted |

## 5. Next Steps

The next phase is **Experiment 2** (time aggregation, the positive side of RQ1 and RQ2). The aggregation analysis will use the all-offset construction of Onofri et al. (2025), with *D* (adaptive *k*) and Monobit as the main acceptance criteria, sweeping the aggregation level ℓ for each asset over the same 5 × 15 cell grid. The first stage will give a rough order of magnitude for the smallest acceptable ℓ in transaction time, before we look at refinements to the acceptance rule and alternative aggregation axes.
