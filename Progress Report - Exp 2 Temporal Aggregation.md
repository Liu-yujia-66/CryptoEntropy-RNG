# Progress Report: Experiment 2 Temporal Aggregation

**Date:** April 10, 2026  
**Project:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation  
**Status:** Experiment 2 Single-Offset Analysis Completed

## 1. Objective

Experiment 2 investigates whether transaction-time temporal aggregation improves the randomness properties of sign-encoded cryptocurrency price sequences. Following the strong serial dependence observed in Experiment 1, the goal is to determine whether increasing the aggregation level `k` suppresses local dependence, reduces deterministic run structure, and yields bitstreams that are closer to passing standard randomness sanity checks.

At the current stage, Experiment 2 has been completed in a **single-offset transaction-time sampling setting**. This provides a first empirical map of how randomness indicators evolve with `k` across assets. A later extension will replicate the methodology of the reference preprint more fully by evaluating **all offsets** for each aggregation level.

## 2. Data and Scope

The current Experiment 2 run uses monthly Binance `aggTrades` data for:

- `BTCUSDT`
- `ETHUSDT`
- `BNBUSDT`
- `SOLUSDT`
- `DOGEUSDT`

The analyzed months are:

- `2026-01`
- `2026-02`
- `2026-03`

The aggregation levels currently evaluated on the full monthly data are:

- `k = 50, 100, 200, 500, 1000, 2000, 3000, 5000, 7000, 10000`

For each asset-month pair, the current pipeline samples one price every `k` trades in transaction time, computes consecutive sampled price changes, removes zero changes, and encodes direction as:

- `Delta P > 0 -> 1`
- `Delta P < 0 -> 0`

The resulting bitstreams are evaluated using:

- Shannon entropy
- proportion of ones `p(1)`
- lag-1 autocorrelation
- monobit test
- runs test
- longest runs
- bit generation rate

## 3. Current Methodological Position

This current report summarizes the completed **single-offset** version of Experiment 2. In practical terms, for each `k`, the present implementation uses one sampling path of the form:

`0, k, 2k, 3k, ...`

This is sufficient to identify the broad dependence-reduction pattern, but it is not yet the full all-offset construction used in the preprint *Emergence of Randomness in Temporally Aggregated Financial Tick Sequences*. Therefore, the present results should be interpreted as:

- a completed exploratory analysis of aggregation effects across assets, and
- a basis for selecting candidate `k` ranges before the final all-offset robustness step.

## 4. Key Findings from the Completed Run

### 4.1 Aggregation clearly improves randomness indicators

Across all five assets, increasing `k` substantially reduces short-range dependence. The clearest signal is the drop in lag-1 autocorrelation.

Using the full monthly data, the average lag-1 autocorrelation across the three analyzed months is approximately:

- `BTC`: `0.426` at `k=50`, `0.147` at `k=200`, `0.065` at `k=500`, `0.036` at `k=1000`
- `ETH`: `0.273` at `k=50`, `0.069` at `k=200`, `0.028` at `k=500`, `0.021` at `k=1000`
- `BNB`: `0.147` at `k=50`, `0.026` at `k=200`, `0.010` at `k=500`, `0.010` at `k=1000`
- `SOL`: `0.042` at `k=50`, `0.016` at `k=200`, `0.005` at `k=500`, `0.001` at `k=1000`
- `DOGE`: `0.029` at `k=50`, `0.015` at `k=200`, `0.005` at `k=500`, about `-0.013` at `k=1000`

This confirms the main qualitative hypothesis of Experiment 2: temporal aggregation in transaction time weakens the strong local dependence seen at low aggregation levels.

### 4.2 The transition is real, but not universal

The results do **not** support the existence of one clean global critical point that works equally well for all assets.

Instead, the transition is asset-dependent:

- `BTC` and `ETH` remain the hardest assets to whiten and require larger `k` values before the dependence measures become small.
- `BNB`, `SOL`, and `DOGE` become much closer to randomness-like behavior at lower `k`.

This is the most important practical conclusion of the current run. A universal `k` would be inefficient because it would force easier assets to sacrifice too much bit rate.

### 4.3 `k = 200` is a meaningful transition region

The current data suggest that `k = 200` is the first aggregation level where the full asset set begins to move out of the strongly dependent regime.

At `k = 200`:

- `BTC` still shows clear residual dependence with average lag-1 autocorrelation around `0.147`
- `ETH` improves substantially to about `0.069`
- `BNB`, `SOL`, and `DOGE` are already much closer to weak-dependence territory, with average lag-1 autocorrelation between roughly `0.015` and `0.026`

This makes `k = 200` a natural lower-bound candidate region, but not yet a safe common choice if one wants conservative randomness quality across all assets.

### 4.4 `k = 500` is a strong practical compromise

The current results indicate that `k = 500` is a strong practical compromise across assets.

At `k = 500`:

- `BTC` average lag-1 autocorrelation is reduced to about `0.065`
- `ETH` falls to about `0.028`
- `BNB`, `SOL`, and `DOGE` are all close to `0.01` or lower

At the same time, the bit generation rate remains materially higher than at `k = 1000` or above. This makes `k = 500` a plausible default candidate when balancing randomness quality against entropy throughput.

### 4.5 `k = 1000` is a more conservative choice

At `k = 1000`, the dependence indicators become smaller still:

- `BTC` average lag-1 autocorrelation falls to about `0.036`
- `ETH` to about `0.021`
- `BNB`, `SOL`, and `DOGE` remain in a weak-dependence regime

However, this comes with a clear entropy-cost tradeoff. Average bit counts and bits-per-second are approximately halved relative to `k = 500`. For example:

- `BTC` average bit count decreases from about `80,827` at `k = 500` to `40,474` at `k = 1000`
- `ETH` decreases from about `71,902` to `35,996`
- `BNB` decreases from about `20,496` to `10,264`

Therefore, `k = 1000` is better interpreted as a conservative asset-agnostic choice rather than an efficiency-optimal one.

### 4.6 Passing simple sanity checks remains asset-dependent

The monobit and runs results show that dependence does not disappear uniformly across assets.

- For `BTC`, runs-based deviations remain strong even when the lag-1 autocorrelation has already decreased substantially.
- `ETH` improves more slowly than `BNB`, `SOL`, and `DOGE`.
- `BNB`, `SOL`, and `DOGE` become compatible with simple sanity checks at lower aggregation levels.

This supports the conclusion that no single scalar indicator is sufficient for selecting `k`. A multi-test criterion will be needed in the next stage.

## 5. Interpretation

The current completed run supports three claims.

First, transaction-time aggregation does improve randomness-related properties of sign-encoded tick sequences.

Second, the improvement is gradual rather than abrupt. It is more accurate to speak about a transition region than a universal critical point.

Third, the transition is clearly asset-dependent. This means that an adaptive aggregation rule is more defensible than choosing one global `k` for every asset.

These findings are also consistent with the logic of Experiment 3, since the choice of `k` directly affects the tradeoff between statistical quality and entropy production rate.

## 6. Current Limitation

The main limitation of the current Experiment 2 report is methodological rather than computational.

The present implementation evaluates only one offset for each `k`. In the reference preprint, each aggregation level is represented by all possible offsets, producing a distribution of randomness outcomes for that scale. The current single-offset results already reveal the broad whitening pattern, but the final formal version of Experiment 2 should extend the analysis to:

- all offsets for each `k`
- an explicit pass-rate or acceptance-rate across offsets
- an automatic per-asset selection of the smallest acceptable `k`

## 7. Next Step

The next step is to convert the current exploratory findings into a formal asset-specific selection framework.

The planned procedure is:

1. For each asset and aggregation level `k`, generate all offset-based sequences.
2. Apply a multi-test randomness sanity check based on entropy/predictability and basic bit-level tests.
3. Select the smallest `k` that passes the acceptance criterion for that asset.
4. Report the corresponding bit generation rate as the practical entropy-efficiency outcome.

### 7.1 Planned Testing Hierarchy

The formal next-stage version of Experiment 2 will organize the evaluation procedure in two layers, following the logic of the two reference papers.

**Main criterion**

- entropy-based predictability test
- independence test based on empirical frequencies, Shannon entropy, and Kullback-Leibler divergence

**Auxiliary sanity checks**

- monobit test
- runs test
- approximate entropy or serial test
- if feasible, a small NIST subset

The intention is not to treat all tests as equal screening rules. Instead:

- the predictability test will serve as the main acceptance criterion
- the bit-level tests will serve as supporting sanity checks

### 7.2 Planned Automatic Selection Rule for `k`

For each asset `a` and each candidate aggregation level `k`, the planned formal procedure is:

1. Generate all `k` offset sequences.
2. Keep only sequences with sufficient length, for example `bit_count >= 10,000`.
3. For each valid offset sequence, compute:
   - entropy-based predictability: `p_ent`
   - monobit: `p_freq`
   - runs: `p_runs`
   - optional approximate entropy: `p_ae`
4. Define a given `k` as acceptable if:
   - at least `80%` of valid offsets satisfy `p_ent >= 0.01`
   - at least `80%` satisfy `p_freq >= 0.01`
   - at least `80%` satisfy `p_runs >= 0.01`
5. For each asset, choose the smallest acceptable `k`.
6. If two neighboring `k` values both pass, choose the one with higher `bits_per_second`, which in practice will usually be the smaller `k`.

At the current stage, these sequence-length and pass-rate thresholds should be interpreted as provisional operational choices for the final Experiment 2 design. The significance level `0.01` is consistent with standard randomness-testing practice and with the reference preprint.

## 8. Summary

Experiment 2 is now complete in its first substantive form and already provides a clear empirical result:

- temporal aggregation improves randomness indicators,
- the amount of required aggregation differs substantially across assets,
- `k = 200` is an important transition region,
- `k = 500` is a strong practical compromise,
- `k = 1000` is a more conservative global choice,
- and the final thesis conclusion should favor **asset-dependent aggregation levels** rather than a universal threshold.
