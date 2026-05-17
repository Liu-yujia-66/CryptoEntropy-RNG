# 50% Progress Report

**Thesis Title:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**Student:** Yujia Liu (yujia.liu.9362@student.uu.se)
**Supervisor:** Andrey Shternshis (andrey.shternshis@it.uu.se)
**Subject Reviewer:** Parosh Abdulla (Parosh.Abdulla@it.uu.se)
**Department:** Information Technology, Uppsala University
**Report Date:** 2026-05-15
**Milestone:** 50% (Experiments 1 and 2 — Baseline and Temporal Aggregation)

---

## 1. Overview

This report covers the first half of the thesis work. During this phase the goal has been to answer Research Question 1 (RQ1) — how an aggregation algorithm can extract statistically independent random sequences from cryptocurrency price data — and Research Question 2 (RQ2) — to what extent these sequences can pass standard randomness tests. Two experiments have been finished end to end (data pipeline, runners, diagnostics, and write-up):

- **Experiment 1 - Baseline.** Shows quantitatively that raw tick sign sequences cannot be used directly as a random source, which is what motivates the use of time aggregation.
- **Experiment 2 - Temporal Aggregation.** For each (asset, month) cell, it finds the smallest aggregation level ℓ\* at which the bit stream passes the chosen test battery, compares two aggregation axes (transaction time and physical time), and refines the acceptance rule through three iterations.

The thesis chapters for this phase (Ch 1 Introduction, Ch 2 Background, Ch 3 Methods, Ch 4 §4.1 Overview, §4.2 Experiment 1, §4.3 Experiment 2 with Appendix Tables A.1–A.5) are drafted.

## 2. Methodological Foundation

All bit streams are produced through a common encoding pipeline. Given a tick price series {(t_i, p_i)} sorted by timestamp, an aggregation level ℓ and a starting offset o ∈ {0, …, ℓ − 1} define a sampled subsequence q_j = p_{o + jℓ}, and the bit b_j is the sign of the difference Δq_j. Zero differences are dropped, because mapping a zero to either 0 or 1 by any fixed rule would inject a clear bias.

The methodology combines two prior frameworks:

1. **Entropy-based predictability test *D*** (Shternshis & Marmi, 2025). A KL-divergence-based test on length-*k* symbol blocks; under H₀ = i.i.d., it asymptotically follows a χ² distribution. The test is run at both an adaptive *k* = ⌊0.5 log₂ *n*⌋ (the main statistic) and a fixed *k* = 2 (a first-order diagnostic).
2. **All-offset construction** (Onofri et al., 2025). For each ℓ, all ℓ parallel bit streams (one for each starting offset) are tested in parallel, and ℓ is accepted through a pass-rate criterion rather than by a single bit stream passing.

A few extra tests from NIST SP800-22 (Monobit, Runs, Approximate Entropy with *m* = 5) and two structural diagnostics (lag-1 autocorrelation ρ₁, longest 0/1 run L_max) cross-check the main statistic. All tests use α = 0.01. The minimum bit count for a valid offset is 2 000.

The data span is five high-liquidity USDT spot pairs (BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, DOGEUSDT) over the 15 months from January 2025 to March 2026, which gives 75 (asset, month) cells. The five assets cover a median raw trades/s range from 12.6 to 50.8.

## 3. Experiment 1 — Baseline (Recap)

Experiment 1 is the special case where ℓ = 1 and o = 0 (no aggregation). Across all 75 cells, the conditional predictability tests (*D* adaptive, *D* fixed *k* = 2, ApEn) and Runs reject at α = 0.01 in every cell, and 73 out of 75 Runs *p*-values underflow to 0. Monobit, by contrast, fails to reject in 14 cells (mostly on the lower-activity assets SOL and DOGE, where p(1) is close to 0.5), which confirms that a marginal frequency test on its own is not enough.

The per-asset lag-1 autocorrelation medians are +0.745 (ETH), +0.636 (BTC), +0.477 (DOGE), +0.366 (BNB), and +0.095 (SOL) - all positive. This is consistent with persistent same-side order flow and trade-sign long memory (Lillo & Farmer, 2004), and is the opposite of the bid-ask-bounce reversal reported by Shternshis & Marmi (2025) on SNAP/F/CCL at the tick scale. The maximum observed longest-run lengths (12 039 for BTC, 15 899 for ETH, down to 792 for SOL) are 2–3 orders of magnitude above the i.i.d. expectation log₂ *n* ≈ 20–25 for these stream lengths. The baseline bit-production rates fall between 1.74 and 10.68 bits/s per-asset median.

Experiment 1 gives a **quantitative negative result** that supports three design points for Experiment 2: aggregation is required; the first-order residual structure becomes a comparison target; and the 1–16 bps baseline is a ceiling for any throughput estimate later in the thesis.

## 4. Experiment 2 — Temporal Aggregation

Experiment 2 is the methodological core of this phase. It went through four stages in order, and each stage was driven by a specific problem in the previous one. The four-stage progression is summarised in the table below; the two main methodological decisions are discussed afterwards.

### 4.1 Four-stage iteration

| Stage | Aggregation axis | Acceptance rule | ℓ grid | Motivation |
|---|---|---|---|---|
| (1) Single offset | transaction-time (trade count) | fixed o = 0; *D* (adaptive) AND Monobit both *p* ≥ α | [50, 2000] step 25 | Experiment 1 motivates aggregation; first locate the order of magnitude of ℓ\*. |
| (2) All-offset **strict gate** | transaction-time | full all-offset construction; ≥ 80% of offsets must pass both *D* (adaptive) and Monobit | [50, 2000] step 25 | Single offset fails on two BTC months entirely; offset robustness needs to be measured, not assumed. |
| (3) All-offset **relaxed gate** | transaction-time | heuristic redundancy rule n_pass ≥ max(F, ⌈f · N_valid⌉) with (F, f) = (3, 0.03) | [10, 2000] step 2 | The strict gate fails on 12 cells (BTC 8 months, ETH 2, SOL 2); the coarse grid also limits the precision of ℓ\*. |
| (4) **1-second bars** | physical-time (UTC seconds) | full all-offset construction; ≥ 80% pass rate (*D* + Monobit) on per-second close-price series | [10, 600] step 1 | On the transaction-time axis, *D* (*k* = 2) and Runs are rejected on almost every witness stream; the throughput also moves with the intra-month trades/s, which makes a fixed SLA hard to write down. |

### 4.2 Two methodological decisions

**(i) The relaxed gate is a heuristic, not a formal multiple-testing correction.** The supervisor pointed out that, in the all-offset setting, only one bit stream is needed in the end. This suggested replacing the pass-rate rule with an existential ("at least one offset passes") rule. We considered Bonferroni and Šidák corrections in this direction, but they turned out to point the wrong way: they tighten α to control the family-wise probability of falsely *rejecting* H₀, while under an ∃-pass rule the concern is falsely *accepting* a non-random sequence - and tightening α makes each individual offset *easier* to pass, which raises rather than lowers the family-wise false-acceptance probability. We ran a directional check on the first quarter of 2025 (thesis Table A.4): the Bonferroni version gives systematically smaller selected ℓ\* than the heuristic, which confirms the direction. The relaxed gate therefore uses a redundancy criterion (at least F offsets pass in absolute terms, and at least a fraction f of the valid offsets), with (F, f) = (3, 0.03) chosen so that the floor sits comfortably above the α = 0.01 noise level. The rule is explicitly marked as a heuristic robustness check in the thesis.

**(ii) Physical-time aggregation is what improves independence.** Under the same +Runs comparison, the transaction-time strict gate coverage drops from 63/75 to 48/75 (a 24% within-axis loss), while the physical-time base gate coverage drops from 70/75 to 62/75 (an 11% loss). This asymmetry suggests that the first-order residual seen under transaction-time aggregation is more likely a property of the sampling axis than of the underlying tick data. The finding reframes the residual structure from "the gate has failed" to "this is the cost of the sampling-axis choice", and supports physical-time aggregation as the preferred deployment-side configuration.

### 4.3 Selected ℓ\* per-asset summary (across 15 monthly cells)

| Asset | Strict gate (trades) n_pass / median ℓ\* | Relaxed gate (trades) n_pass / median ℓ\* | 1-second bar base (seconds) n_pass / median ℓ\* |
|---|---:|---:|---:|
| BTC  |  7/15 / 1500 | 15/15 / 1150 | 15/15 / 62 |
| ETH  | 13/15 /  975 | 15/15 /  556 | 12/15 / 65 |
| BNB  | 15/15 /  350 | 15/15 /  212 | 14/15 / 84 |
| SOL  | 13/15 /  350 | 15/15 /  180 | 15/15 / 54 |
| DOGE | 15/15 /  375 | 15/15 /  156 | 14/15 / 33 |

The full per-(asset, month) tables, the +Runs and +Runs+ApEn comparisons, and the Bonferroni directional control are in thesis Appendix Tables A.1–A.5.

### 4.4 Key findings

1. **The cross-asset ranking is stable: BTC > ETH ≫ BNB / SOL / DOGE.** This coarse activity-based ordering holds across all three gates. BTC and ETH both need a deeper aggregation than the three less active assets, and there is a large gap between the two groups. Within the lower tier, BNB / SOL / DOGE are not strictly monotone. The direction agrees with Onofri et al. (2025) Case 2 on US equities ("higher trades/s ⇒ larger ℓ\*"), and is a cross-market replication on cryptocurrency spot data.
2. **The relaxed gate lifts coverage from 63/75 to 75/75.** Twelve cells failed under the strict gate (BTC in 8 months, ETH in 2, SOL in 2); the relaxed gate finds an acceptable ℓ\* ∈ [48, 1750] for every cell. The per-asset median ℓ\* falls by 23% (BTC) to 58% (DOGE), and the per-cell bit rate rises from about 0.012 bits/s under strict to about 0.021 bits/s under relaxed (roughly 1.8×).
3. **Physical-time aggregation absorbs the first-order residual in 62 of 75 cells.** Under transaction time, *D* (*k* = 2) and Runs are rejected on almost every witness stream chosen by the gate. On the 1-second bar axis, both tests reach a ≥ 0.80 pass rate in 62 of 75 cells. The five cells where the base gate itself fails are all in months where the seconds-with-trades coverage is below 0.75 (DOGE/ETH in 2025-12 and 2026-02 to 03; BNB in 2025-07), which points to a data-density condition rather than a gate-design problem.
4. **Throughput at selected ℓ\* sits in the 10⁻² bps range.** Transaction-time strict gives roughly 0.012 bits/s; relaxed gives about 0.021 bits/s; 1-second bar base falls between 0.01 and 0.03 bits/s. Selected ℓ\* on the physical-time axis maps directly to a per-bit wall-clock latency in the minute range, which is consistent with the latency upper bound of 600 s = 10 min set in the Methods chapter (§3.5).

### 4.5 Limitations recorded for the Discussion chapter

1. **The offset must be fixed methodologically.** Selected witness offsets are diagnostic only; they cannot be picked after the fact in a deployment setting.
2. **Transaction-time first-order residual.** *D* (*k* = 2) and Runs are rejected on the witness streams chosen on this axis. The 1-second bar axis absorbs this on 62 of 75 cells; if transaction-time aggregation is still used downstream, a debiasing step such as von Neumann is needed.
3. **No formal correction over the ℓ grid.** Multiple selection over the ℓ grid is not corrected by Bonferroni or FDR; this is a shared limitation of both the strict and the relaxed configurations.
4. **The relaxed gate (F, f) = (3, 0.03) is a design choice.** There is no formal multiple-testing correction for the ∃-pass direction (Section 4.2 above), and no sensitivity sweep over (F, f) has been done.
5. **Edge-of-range sample sizes.** The per-offset stream lengths *n* ∈ [2 × 10³, ~10⁴] sit at the lower edge of the Q–Q simulation range in Shternshis & Marmi (2025) Appendix A; the *p*-value precision is correspondingly weaker than at *n* ≥ 10⁴.

## 5. Current Status

| Chapter / Item | Status |
|---|---|
| Ch 1 — Introduction | Drafted (revisions from supervisor review partially addressed) |
| Ch 2 — Background | Drafted; literature coverage to be widened following supervisor feedback |
| Ch 3 — Methods | Drafted (six sections: Encoding, All-Offset, Test Battery, Acceptance Gates, 1-Second Pipeline, Throughput Metric) |
| Ch 4 §4.1 — Setup + Data | Drafted |
| Ch 4 §4.2 — Experiment 1 | Drafted |
| Ch 4 §4.3 — Experiment 2 | Drafted (four sub-stages); Appendix Tables A.1–A.5 included |
| References | Cross-checked against source PDFs and pruned |

## 6. Closing Remarks for This Phase

The two experiments finished in this phase make up the methodological backbone of the thesis. Experiment 1 gives the negative baseline that motivates aggregation; Experiment 2 produces the operating parameters (the selected ℓ\* per asset and per month, on two aggregation axes) that downstream work will use. The four-stage iteration in Experiment 2 also surfaces two cross-cutting observations - the cross-market replication of the activity-vs-ℓ relationship reported by Onofri et al. (2025), and the reframing of the first-order residual as a property of the transaction-time sampling axis rather than of the source data - which will feature in the Discussion chapter.

The rest of the thesis work will turn to the application side of RQ3, and to the implications of the results above for downstream construction. Those parts are outside the scope of this 50% milestone report.
