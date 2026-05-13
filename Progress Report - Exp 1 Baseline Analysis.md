# Progress Report: Experiment 1 Baseline Analysis

**Date:** 2026-05-09
**Project:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**Status:** Experiment 1 Baseline Completed(5 资产 × 15 个月 = 75 个 (asset, month) cell;诊断粒度月度)

## 1. Objective

Experiment 1 的目标是为 raw high-frequency 加密货币 tick 数据建立统计 baseline,判定其符号编码序列是否能直接作为随机源使用。本轮 baseline 覆盖 Binance 现货市场流动性最高的 5 个 USDT 现货对——`BTCUSDT`、`ETHUSDT`、`BNBUSDT`、`SOLUSDT`、`DOGEUSDT`,跨 raw trades/s ~13 到 ~51 的活跃度区间(per-asset median,thesis Table 4.1),时段与 Experiment 2 一致(2025-01 至 2026-03,共 15 个月)。

## 2. Methodology

**Data source.** Binance `aggTrades`,5 资产 × 15 个月度归档(2025-01 至 2026-03),共 75 个 (asset, month) 诊断单元。每个 cell 一条月度比特流,bit 长度 ~10⁶ 至 4×10⁷。

**Pre-processing.** 按 trade 时间排序,丢弃 Δp = 0 的 tick(drop-zero)。

**Encoding.** 对剩余非零价格变化取符号:Δp > 0 → 1,Δp < 0 → 0。无聚合,无后处理(对应 thesis 算法 1 在 ℓ = 1, o = 0 的特例)。

**Diagnostics.** 每个 (asset, month) 单元计算 8 项指标——其中 Shannon 熵、Monobit、Runs 来自 NIST STS;p(1)、Shannon-bias |H − 1| 是衍生量;bit 长度 *n* 与 bits/s 是描述性元数据;**lag-1 自相关 ρ₁ 与最长 0-run / 1-run 长度 L_max** 不属于 NIST STS,作为 baseline 扩展引入,前者刻画短程依赖、后者给长结构的密码学语义直觉。

**Pipeline.** `scripts/runner_exp1_baseline.py` 读取月度归档、产出每个 (asset, month) 一行 summary;子进程 `scripts/plot_exp1_baseline.py` 把 75 行汇总为 5 行 per-asset summary(thesis Table 4.2)+ 4 panel 分布图(thesis Figure 4.1)。

## 3. Key Findings

边际分布在 75 个 cell 上一致接近平衡(1 − H 全部 ≤ 7.93 × 10⁻³,低活跃资产可低至 ~10⁻⁵ 至 ~10⁻⁶ 量级)。但如 thesis §2.2 所警示,Shannon-bias 仅作汇总指标、不进入接受判据;以下四条来自条件分布与结构性诊断。

**Monobit 通过率随活跃度递减,Runs 在所有 cell 上一律拒绝。** 75 个 cell 中 14 个不拒绝 α = 0.01:SOL 11、DOGE 7、BNB 与 ETH 各 2、BTC 0。Runs 在全部 75 cell 一律以 p ≪ 10⁻³⁰⁰ 拒绝,序列显然非随机。Monobit 模式单调随活跃度递减:最活跃的 BTC 月月被拒,最不活跃的 SOL 约三分之二月份不拒——其 p(1) 紧贴 0.5,边际频率检验在这种条件下没有信号。这是"单一检验不充分"的具体例子。

**lag-1 自相关在每个资产上都为正,量级随活跃度递增。** Per-asset median 分别是 ETH +0.745、BTC +0.636、DOGE +0.477、BNB +0.366、SOL +0.095。在 per-month 层面,BTC / ETH / DOGE / BNB 的分布稳定在零线之上,SOL 紧贴零线、跨度小。这与持续同向 order-flow 一致:大 taker 单 walk-the-book 时连续多档同向成交,高流动性资产中 trade-sign 自身的 long-memory(Lillo & Farmer, 2004)进一步累积出正自相关。Shternshis & Marmi (2025) 在 SNAP / F / CCL 上报告的 bid-ask bounce stylized fact 作用在 tick scale,产生反向相关;在月度粒度下该效应不是本论文研究的五个加密货币对的主导特征,虽然 SOL per-month 检视显示个别月份 ρ₁ 短暂跌至零下。

**最长 run 是结构性密码学失败,量级随活跃度缩放。** 各资产 15 月观察到的最大 L_max:**BTC 12 039**、**ETH 15 899**、DOGE 5 071、BNB 2 069、SOL 792。i.i.d. 随机期望 E[L_max] ≈ log₂ n,本论文月度比特流 n ~ 10⁶ 至 4 × 10⁷,该期望约在 20 至 25 之间。每个观测到的 L_max 都比该 baseline 高 2–3 个数量级;排序大体随活跃度单调(BTC 与 ETH 因 ETH per-month ρ₁ 更强而有 swap)。任何 N-bit 密码 / seed 的产出窗口若落在 BTC / ETH 量级的 run 内,输出就是一段全 0 或全 1——直接的密码学失败,即便边际熵看似几近完美。

**比特产出速率不超过 16 bps。** Per-cell bits/s 区间从 0.87(SOL,2026-03)到 15.52(BTC,2026-02);按 per-asset median 排序为 BTC 10.68 > ETH 9.56 > BNB 2.49 > DOGE 2.02 > SOL 1.74 bps。前两位与 Table 4.1 raw trades/s 顺序一致(BTC > ETH),下三者反转:SOL 虽 raw trades/s 高于 BNB / DOGE,其 zero-delta ratio 是五者中最高(15 月 median 约 0.59),drop-zero 之后剩余 bit 事件比 BNB(zero-delta ratio ≈ 0.43)更少,使 SOL 在 bps 排序中位列最末。Baseline 吞吐量因此不仅取决于 trades/s,也取决于 per-asset 的 zero-delta ratio。

## 4. Conclusion

Experiment 1 给出一个**负向但定量**的结论:直接把 raw tick 的符号序列当 RNG,Runs 在 75/75 (asset, month) cell 上一致拒绝、每个资产 lag-1 自相关 median 为正、最长 run 比 i.i.d. baseline 高 2–3 个数量级。Monobit 单独使用甚至会在低活跃资产上漏检(14/75 cell 不拒绝),只有 Runs 在 baseline 上达到通用拒绝覆盖。这一结论为 Experiment 2 提供三个直接锚点:

(i) **聚合的必要性**——Runs 在全部 75 个 baseline cell 上一致拒绝、lag-1 在所有资产上偏离 0,任何针对 raw tick 流的接受规则都为空集。

(ii) **1 阶残留结构作为诊断目标**——每个资产上都为正、量级随活跃度缩放的 lag-1 自相关,是 Experiment 2 在 transaction-time 与 1-second bar 两条聚合轴之间做对照分析的 explicit target;1-second bar 是否带来增益,取决于聚合能否吸收这一短程依赖。

(iii) **吞吐量上界**——75 个月度 cell 的 baseline bits/s 量级(1 至 16 bps)是 §3.6 throughput metric 与 Exp 3 entropy-rate 讨论的天花板。

## 5. Attachments

- `scripts/runner_exp1_baseline.py` —— Baseline runner:per-(asset, month) ThreadPoolExecutor pipeline
- `scripts/plot_exp1_baseline.py` —— 子进程,把 75 行 summary 汇总为 5 行 per-asset table + 4 panel 分布图
- `data/processed/experiment1/all_assets_summary_exp1_baseline.csv` —— 75 行 per-(asset, month) 完整诊断指标
- `data/processed/experiment1/by_asset/<ASSET>/<ASSET>_summary_exp1_baseline.csv` —— 每个资产 15 行 per-month 诊断
- `data/processed/experiment1/per_asset_summary.csv` / `per_asset_summary.md` —— thesis Table 4.2 的 5 行 summary(CSV / markdown 双格式)
- `data/processed/experiment1/per_asset_distributions.png` —— thesis Figure 4.1 的 4 panel 分布图(bps box / ρ₁ box / Monobit −log₁₀(p) ECDF / L_max histogram)
