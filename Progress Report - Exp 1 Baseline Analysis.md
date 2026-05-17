# Progress Report — Experiment 1: Baseline Randomness of Raw High-Frequency Price Sequences

**论文题目:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**学生:** Yujia Liu (yujia.liu.9362@student.uu.se)
**导师:** Andrey Shternshis
**Subject Reviewer:** Parosh Abdulla
**报告日期:** 2026-05-16
**状态:** 实验、数据、写作均已完成,对应论文 Ch 4 §4.2。

---

## 1. 实验目标

回应研究问题 RQ1 的负向部分:不经任何聚合的原始 tick 符号序列,能否直接作为随机源使用?该结论(若为否)定量化"必须聚合"这一前提,并直接动机化 Experiment 2。

## 2. 方法论摘要

**数据.** Binance 公开 `aggTrades`,5 个 USDT 现货对(BTCUSDT、ETHUSDT、BNBUSDT、SOLUSDT、DOGEUSDT)× 15 个月度归档(2025-01 至 2026-03),共 75 个 (asset, month) cell;每条月度比特流长度 *n* ∈ [10⁶, 4 × 10⁷]。资产覆盖 raw trades/s 中位数 12.6–50.8 的活跃度区间(论文 Table 4.1)。

**编码.** 按时间排序 → 丢弃 Δp = 0 的 tick(drop-zero) → 符号编码 Δp > 0 ↦ 1, Δp < 0 ↦ 0。对应论文 Algorithm 1 在 ℓ = 1, o = 0 的退化形式。

**诊断电池.** 每个 cell 计算 8 项指标,显著性水平 α = 0.01:

- **NIST STS 子检验:** Monobit(边际频率)、Runs(游程数偏离 i.i.d. 期望)、Approximate Entropy(m = 5,复杂度差);
- **熵驱动可预测性检验:** Shternshis & Marmi (2025) 的 *D* 检验,在 adaptive *k* = ⌊0.5 log₂ *n*⌋ 与 fixed *k* = 2 两种参数下分别计算;
- **结构性诊断扩展(非 NIST):** lag-1 自相关 ρ₁(短程依赖)、最长 0/1 run 长度 L_max(长结构,密码学语义直觉);
- **描述性元数据:** bit 长度 *n*、bits/s、p(1)、Shannon-bias |H − 1|(仅作汇总指标,不进入接受判据)。

**实现.** `scripts/runner_exp1_baseline.py`(per-(asset, month) 并发 pipeline)→ 75 行 summary CSV;子进程 `plot_exp1_baseline.py` 汇总为 5 行 per-asset 表(论文 Table 4.2)+ 4 panel 分布图(论文 Figure 4.1)。

## 3. 设计决策与迭代

Exp 1 没有方法论迭代,但相对 Initial Plan 做了两处 scope 扩展,均在与导师 review 后确认:

1. **资产数 2 → 5.** Initial Plan 原定 BTC / ETH 双资产;扩展到 5 资产以便观察"活跃度 → 1 阶残差 / 最长 run / bps"的跨资产模式。该扩展也使 Exp 1 与 Exp 2 共享同一 (asset, month) cell 单元,跨实验对比更直接。
2. **指标 Shannon entropy + 基础 NIST → 完整条件可预测性 battery + 结构性扩展指标.** 导师在 review 中指出"高边际熵不蕴含不可预测";因此引入 *D* 检验、ApEn、ρ₁、L_max 共同诊断,Shannon-bias 降为汇总指标。

## 4. 关键结果

### Table — Per-asset summary (跨 15 月汇总,源自论文 Table 4.2)

| Asset | bps median | 1−H max | ρ₁ median | Monobit rejects | Runs rejects | ApEn rejects | D(adaptive) rejects | D(k=2) rejects | L_max max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC  | 10.68 | 1.94 × 10⁻³ | +0.636 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 12 039 |
| ETH  |  9.56 | 7.93 × 10⁻³ | +0.745 | 13/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15 899 |
| BNB  |  2.49 | 9.98 × 10⁻⁵ | +0.366 | 13/15 | 15/15 | 15/15 | 15/15 | 15/15 |  2 069 |
| DOGE |  2.02 | 1.35 × 10⁻⁵ | +0.477 |  8/15 | 15/15 | 15/15 | 15/15 | 15/15 |  5 071 |
| SOL  |  1.74 | 2.35 × 10⁻⁶ | +0.095 |  4/15 | 15/15 | 15/15 | 15/15 | 15/15 |    792 |

### 主要发现

1. **条件可预测性 + Runs 在全部 75 cell 上一致拒绝.** *D*(adaptive)、*D*(*k* = 2)、ApEn、Runs 四项检验跨 75 cell 全部以 α = 0.01 拒绝,其中 73 个 cell 的 Runs *p* 值下溢到 0。即使 SOL 这类 p(1) 紧贴 0.5、Monobit 仅在 4/15 月拒绝的资产,这四项检验仍然全部拒绝。这是"raw tick 流非随机"最直接、最不依赖边际假设的证据。
2. **Monobit 单独使用会漏检.** 14 个 cell 不被 Monobit 拒绝(SOL 11、DOGE 7、BNB 2、ETH 2、BTC 0),集中于低活跃资产——其 p(1) 紧贴 0.5 且月度比特流更短,边际频率检验功效不足。后续实验不能只依赖 Monobit。
3. **lag-1 自相关每个资产均为正,量级粗粒度随活跃度递增.** Per-asset median 依次 ETH +0.745、BTC +0.636、DOGE +0.477、BNB +0.366、SOL +0.095。方向与 Lillo & Farmer (2004) 的持续同向 order-flow / trade-sign long-memory 一致,而非 Shternshis & Marmi (2025) 在 SNAP/F/CCL 上报告的 bid-ask bounce 反转。后者在月度粒度下不是本论文五个加密货币对的主导特征。
4. **最长 run 远超 i.i.d. baseline 2–3 个数量级.** ETH 15 899、BTC 12 039、DOGE 5 071、BNB 2 069、SOL 792;i.i.d. 期望 E[L_max] ≈ log₂ *n* ≈ 20–25。给出 raw tick 作为密码学随机源的失败模式直觉:若 seed/password 取样窗口落入这类长 run,输出退化为连续全 0 或全 1。
5. **比特产出速率 1–16 bps.** Per-asset median 排序 BTC 10.68 > ETH 9.56 > BNB 2.49 > DOGE 2.02 > SOL 1.74。前两位与 raw trades/s 排序一致,下三者反转——SOL 的 zero-delta ratio 是五者中最高(median ≈ 0.59),drop-zero 之后剩余 bit 事件较少。这一上界是后续任何聚合后吞吐量的天花板。

## 5. 对 Experiment 2 的锚点

Exp 1 给出一个**负向但定量**的结论,为 Exp 2 提供三个直接出发点:

(i) **聚合必要**——Runs 在 75/75 cell 上一致拒绝、lag-1 在所有资产上偏离 0,任何针对 raw tick 流的接受规则都为空集。

(ii) **1 阶残留作为对照目标**——每个资产均为正、量级粗粒度随活跃度缩放的 lag-1 自相关,是 Exp 2 在 transaction-time 与 1-second bar 两条聚合轴之间对比独立性表现的 explicit target。

(iii) **吞吐量上界**——baseline bits/s ∈ [1, 16] 是论文 §3.6 throughput metric 与后续 Experiment 3 entropy-rate 讨论的天花板。

## 6. 产出物

- `scripts/runner_exp1_baseline.py` — per-(asset, month) ThreadPoolExecutor pipeline
- `scripts/plot_exp1_baseline.py` — 5 行 per-asset table + 4 panel 分布图生成
- `data/processed/experiment1/all_assets_summary_exp1_baseline.csv` — 75 行 per-(asset, month) 完整诊断指标
- `data/processed/experiment1/by_asset/<ASSET>/<ASSET>_summary_exp1_baseline.csv` — 每个资产 15 行 per-month 诊断
- `data/processed/experiment1/per_asset_summary.csv` / `per_asset_summary.md` — 论文 Table 4.2 的 5 行 summary
- `data/processed/experiment1/per_asset_distributions.png` — 论文 Figure 4.1
