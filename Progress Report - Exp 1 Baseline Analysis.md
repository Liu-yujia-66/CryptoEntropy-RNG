# Progress Report: Experiment 1 Baseline Analysis

**Date:** 2026-05-07
**Project:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**Status:** Experiment 1 Baseline Completed(5 资产 × 5 天 = 25 个诊断单元)

## 1. Objective

Experiment 1 的目标是为 raw high-frequency 加密货币 tick 数据建立统计 baseline,判定其符号编码序列是否能直接作为随机源使用。本轮 baseline 覆盖 Binance 现货市场流动性最高的 5 个 USDT 现货对——`BTCUSDT`、`ETHUSDT`、`BNBUSDT`、`SOLUSDT`、`DOGEUSDT`,跨度覆盖 trades/s ~13 到 ~51 的活跃度区间(per-asset median raw trades/s,详见 thesis Table 4.1)。

## 2. Methodology

**Data source.** Binance `aggTrades`,5 资产 × 5 个连续交易日(2026-01-01 至 2026-01-05),共 25 个 (asset, day) 单元。窗口选在 Exp 2 样本期(2025-01 至 2026-03)最末季度 2026 Q1 的首周,作为 contemporaneous 切片。

**Pre-processing.** 按 trade 时间排序,丢弃 Δp = 0 的 tick(drop-zero)。

**Encoding.** 对剩余非零价格变化取符号:Δp > 0 → 1,Δp < 0 → 0。无聚合,无后处理(对应 thesis 算法 1 在 ℓ = 1, o = 0 的特例)。

**Diagnostics.** 每个 (asset, day) 单元计算 8 项指标——其中 Shannon 熵、Monobit、Runs 来自 NIST STS;p(1)、Shannon-bias |H − 1| 是衍生量;bit 长度 *n* 与 bits/s 是描述性元数据;**lag-1 自相关与最长 0-run / 1-run 长度 L_max** 不属于 NIST STS,作为 baseline 扩展引入,前者刻画短程依赖、后者给长结构的密码学语义直觉。

## 3. Key Findings

总结成五条(R1–R5,与 thesis §4.2 Results 同步):

**(R1) 边际熵看似几乎完美,但越接近完美,盲区越深。** 全部 25 个单元 1 − H ≤ 8.5 × 10⁻⁴,p(1) ∈ [0.500, 0.517];低活跃资产(SOL / DOGE)在某些 cell 上 1 − H 低至 ~10⁻⁸ 量级。仅看 Shannon-bias 会得出"序列接近完美随机"的错误结论——但下面 R2、R3 揭示的失效正是发生在这些 1 − H 最小的 cell 上。

**(R2) Monobit 在低活跃资产上完全失效,而 Runs 一个不漏。** 25 个单元中 11 个 Monobit 在 α = 0.01 下不拒绝(BNB 3 天、DOGE 3 天、SOL 全部 5 天均不拒绝);DOGE 01-03 给出 p = 0.949。但 Runs 在这 25 个 cell 上一律以 p ≪ 10⁻⁴⁴ 拒绝。

这一观察直接证明任何单一检验都有结构性盲区——当低活跃日 + 弱方向性使 p(1) 紧贴 0.5 时,Monobit 这种边际频率检验对它们没有信号。**这是 Exp 2 接受规则把 *D*(条件分布)+ Monobit(边际分布)并联的实证依据。**

**(R3) lag-1 自相关的符号因资产的活跃度区间而翻转——bid-ask bounce 与 order-flow 持续性是两种不同的机制。** SOL 五天一致为负(ρ₁ ∈ [−0.45, −0.09],median −0.22),复现 Shternshis & Marmi (2025) 在 SNAP / F / CCL 上报告的 bid-ask bounce stylized fact——成交价反复在 buy / ask 间跳动使相邻非零符号倾向反转。BTC 与 ETH 呈相反模式,具有强正 ρ₁(BTC median 0.40,ETH median 0.70),只能由持续同向 order-flow 解释——大 taker 单 walk-the-book 时连续多档同向成交,液态资产中 trade-sign 自身的 long-memory(Lillo & Farmer, 2004)进一步累积出正自相关。BNB 与 DOGE 介于两种 regime 之间,ρ₁ 量级较小。

**transaction-time 上的 1 阶残留因此由两种各自不同的微观结构机制在不同活跃度区间驱动,而非单一机制**;这一区分会进入 Exp 2 的 transaction-time 与 1-second bar 对照分析,需要在不同活跃度资产上分开评估。

**(R4) 最长 run 在密码学语义上结构性失败,且量级与 trades/s 同向缩放。** L_max 跨 25 cell 范围 18 至 795。各资产最大 L_max:**BTC 795**(01-01,1-run)、ETH 315、BNB 226、DOGE 53、SOL 28。前三者在密码学语义上是直接灾难——任何 N-bit 密码 / seed 的产出窗口若落在这种 run 内,输出就是一段全 0 或全 1。后两者(DOGE / SOL)更接近 i.i.d. 随机期望 E[L_max] ≈ log₂ n ≈ 16-18,但仍偏高,且伴随 Runs 强烈拒绝。L_max 与 Exp 2 selected ℓ\* 是同一现象的两面:trades/s 越高,需要更深的聚合才能打散同向 run。

**(R5) 比特产出速率 0.5–10 bps 是 baseline 的吞吐上界。** 各 cell bits/s 落在 0.49 (SOL 01-01) 至 9.69 (BTC 01-05) 区间;按 per-asset median 排序为 BTC ≈ 4.4 > ETH ≈ 3.6 > BNB ≈ 1.6 > DOGE ≈ 1.4 > SOL ≈ 0.8 bps。**前两位与 Table 4.1 的 raw trades/s 顺序一致,但下三者反转**——这是因为 SOL 的 zero-delta ratio 最高(median ≈ 0.64),drop-zero 后实际产 bit 的事件比 BNB(zero-delta ratio ≈ 0.44)少,使 SOL 在 bps 排序中位列最末。Baseline 吞吐量因此不仅取决于 trades/s,还取决于 per-asset 的 zero-delta ratio 这一资产个性化的微观结构属性。

用 Table 4.1 的 15 月 aggTrades/s p95 与 5 天窗口的 per-asset zero-delta ratio 做 cross-check,推算出的 15 月 bps 区间与 5 天数据数量级一致,最高极值(BTC / ETH 最活跃月)约 13 bps。Exp 2 通过聚合"漂白"会以这部分吞吐为代价,典型尺度降到约 10⁻² bps。

## 4. Conclusion

Experiment 1 给出一个**负向但定量**的结论:直接把 raw tick 的符号序列当 RNG,在 25/25 (asset, day) cell 上一致地、在 Runs 与 lag-1 自相关上结构性失败;Monobit 单独使用甚至会在低活跃资产上漏检(11/25 cell 不拒绝),只有 Runs 在 baseline 上达到通用的拒绝覆盖。这一结论为 Experiment 2 提供三个直接锚点:

(i) **聚合的必要性**——R3 / R4 给出"必须聚合"的实证理由。

(ii) **两种各自不同的 1 阶残留机制作为诊断目标**——SOL 上的 bid-ask bounce + BTC / ETH 上的持续 order-flow 同向相关,需要在 transaction-time 与 1-second bar 两条聚合轴之间做对照,1-second bar 是否带来增益取决于聚合能否各自吸收这两种残留机制,且两种机制需要在不同活跃度资产上分开评估。

(iii) **吞吐量上界**——R5 的 0.5–10 bps 是任何聚合后白化策略的天花板。

## 5. Attachments

- `scripts/exp1_baseline.py` —— Baseline pipeline:加载 tick 数据、符号编码、统计诊断
- `data/processed/experiment1/summary_exp1_baseline_k1_full.csv` —— 25 行(5 资产 × 5 天)的完整诊断指标
- `data/processed/experiment1/bitstreams/` —— 每个 (asset, day) 单元的 per-day bitstream CSV
- `data/processed/experiment1/plots/` —— 每个单元 5 panel 诊断图(price evolution / Δp 分布 / bitstream preview / ACF / run-length)
