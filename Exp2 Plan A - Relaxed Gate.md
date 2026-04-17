# Experiment 2 — Plan A: Relaxed All-Offset Gate

> 状态:**已完成**(per-month + (3, 0.03) 实现 75/75 全覆盖)。作为 strict (80% pass rate) 的**补充启发式分析**,不替换主结果。下一步切到 **1-second bars**(见 §7)。

## 1. 起因

导师在 Slack 中提出的 Plan A(2026-04,全文见 `notes/conversation.txt`):

> "You technically want to have one random string even in all-offset scenario because the string are mutually correlated. Thus you may check if at least one string is random and passes your criteria. The problem here is that then you really need to adjust your significance level because you do multiple testing and thus string can be classified as random just by chance."

导师授权路径:先做 relaxed,结果不够好再切 1-second bars,不并行。

## 2. 为什么是 heuristic,不是正式校正

"∃ reject" 规则有 Bonferroni / Šidák 的标准族内 Type-I 控制;**"∃ pass" 规则没有对称的教科书校正**,原因:

- "High p-value" 不等于"更支持随机",只等于"更不能被拒绝"。把高 p 当成"通过强度"做正式校正,统计意义不干净。
- Type-II(H1 下的 false accept)控制依赖未知 alternative 的效应量,纯用 α 调不出来。

所以导师那句"adjust significance level"字面可以套公式,但**任何硬套的正式校正都经不起推敲**。论文里必须显式标注为 heuristic。

## 3. 判据

```
is_acceptable_relaxed =
    num_pass ≥ max(RELAXED_MIN_PASS_ABSOLUTE,
                   ceil(RELAXED_MIN_PASS_FRACTION × N_valid))
```

其中 `num_pass` = 同时满足 `p_D ≥ 0.01` 且 `p_monobit ≥ 0.01` 的 valid offset 数(α 不校正)。

实际跑用的参数组:`(3, 0.03)` 和 `(5, 0.05)`,在多个网格步长下都跑过。结果见 §5。

### 两层作用

- **绝对下限 floor**:挡小 N(小 ℓ)下"1-2 个偶然通过"被接受
- **比例下限**:挡大 N(大 ℓ)下"占比极小也算"的稀释
- N 过小(< floor/fraction 的交叉点)时 floor 主导;N 过大时 fraction 主导

### 与其它规则的对比 (以 ℓ=2000 为例)

| 规则 | 最低通过数 | 语义 |
|---|---|---|
| strict 80% pass rate | 1600 | 绝大多数 offset 都随机 |
| **relaxed (3, 0.03)** | **60** | 少数但非平凡比例 offset 随机 |
| **relaxed (5, 0.05)** | **100** | 同上,略严 |
| 纯 ∃1 pass | 1 | 偶然一个通过(导师担心的情形) |

中间带清晰:比 ∃1 严两个数量级,比 strict 松约 20 倍。

## 4. 预期评估(事前)

- ✓ 简单,两个 magic number 都可一句话解释
- ✓ 比 ∃1 严两个数量级,部分回应导师"just by chance"担忧
- ✓ 比 strict 放宽,给 BTC/ETH 纳入分析的机会
- ✓ 可诚实标注为 heuristic,不冒 formal correction 风险
- ✗ 不是正式校正,不能对抗审阅者"statistical rigor"层面的追问(但硕士论文级别不致命)

### 会被追问的点 + 准备答案

| 追问 | 答 |
|---|---|
| 为什么这个 fraction,不是别的? | Heuristic 中点,保留计数意义同时允许少数比例通过。不声称最优 |
| 为什么要 floor? | 防止小 N(小 ℓ)下"1-2 个偶然通过"被接受;floor 是区分"抽样偶然"与"稳定少数"的经验最小值 |
| 这是多重校正吗? | 明确**不是**,是 heuristic robustness check,见第 2 节为何不硬做校正 |
| 跨 ℓ 维度还做了多重选择? | 是,候选 ℓ 的 selection 也未校正;此规则只处理 offset 维度 |

## 5. 事后结果

实际跑过的配置(详见 `data/processed/experiment2/relaxed-*`):

| 配置 | 覆盖率 | 备注 |
|---|---|---|
| Quarterly, (3, 0.03), step 2 | BTC 5/5,ETH 5/5 | BTC 季度 ℓ 落在 1292-2356 |
| Quarterly, (5, 0.05), step 10 | BTC 5/5,ETH 5/5 | 略高,BTC 1330-2610 |
| Quarterly, (5, 0.05), step 25 | BTC 2/6(粗网格漏) | 网格太粗,边界 ℓ 被跳过 |
| **Per-month, (3, 0.03), step 2** | **5 asset × 15 month 全覆盖** | 主分析版本 |
| Per-month, (3, 0.03), step 5 | 同上 | 数值和 step 2 几乎一致 |

### 5.1 Per-month 主结果

- **全 75 个 (asset, month) 都 selected**:Plan A 在 asset coverage 层面完全达成目标
- BTC per-month ℓ 范围 870-1750,呈**跨时间单调下降**(2025.01 = 1750 → 2026.03 = 880)
- DOGE、SOL 等流动性较低的资产也有类似下降趋势
- Throughput ~0.02 bits/s(对比 strict ~0.003,约 7× 提升)

### 5.2 Witness 诊断(k=2 / Runs 残留)

每个被选中的 (ℓ, witness offset) 上跑全电池:

| 诊断 | p 范围 | 超过 α=0.01 |
|---|---|---|
| `witness_pD` (gate 条件) | 0.023 – 0.31 | 75/75 |
| `witness_pMono` (gate 条件) | 0.017 – 1.00 | 75/75 |
| `witness_pD_k2` | 1.1e-16 – 3.4e-4 | 0/75 |
| `witness_pRuns` | 1.1e-16 – 3.4e-4 | 0/75 |

witness 在 k=2 和 Runs 上一致被拒,最"好"一行(DOGE 2025.10)p ≈ 3.4e-4。

**这不是 Plan A 的缺陷,而是两篇 Reference 都已记录的 stylized fact**:

- **Price predictability 2024 §4.4**:把 fixed-k=2 D 定位为**诊断工具**(不是 acceptance test),为 SNAP/F/CCL 三支低频股**额外**跑 k=2 以**解释** bid-ask bounce 机理。Paper 明说 "this characteristic diminishes as k increases to around 5 or 6",即作者自己承认 adaptive-k(≈6-7)会稀释 1 阶信号。Paper Table 4 里 SNAP/F/CCL 的 predictable-day k=2 p 值分别是 0.0014 / 2.67e-10 / 0.044,也都 ≪ α,Paper 照样发表。
- **Emergence of Randomness 2025**:Runs 是 NIST battery 的组件,不单独作为 accept/reject 判据。AAPL/TSLA 这类高频股"许多检验到 ℓ=100 仍失败"(Case 2),Paper 作为 stylized fact 报告,不是失败。

因此 witness k=2 / Runs 爆表的正确定位是:**在 crypto 上复现了 Price predictability 2024 的 SNAP/F/CCL bid-ask bounce 模式**。是一个被 Reference 背书的 positive finding,**不是 Plan A(或 strict)的失败**。

Strict gate 下的 k=2 / Runs pass-rate 本就贴 0,说明这是 transaction-time 聚合轴的属性,与 gate 的松紧无关。**注**:后续 1-second bar 分析(见 [Exp2 Plan B](Exp2%20Plan%20B%20-%20Time-Based%20Aggregation.md) §5)显示同样两个检验在物理时间轴上 62/75 窗口能达到 pass-rate ≥ 0.80——所以这条 1 阶依赖不是**源数据**的不可破坏属性,而是 transaction-time **聚合轴**的属性。

### 5.3 bits/s 对比

| 方案 | bits/s(典型) |
|---|---|
| strict 80%, quarterly | ~0.003 |
| relaxed (3, 0.03), monthly | ~0.02 |

### 5.4 跨市场一致性:复现 Emergence of Randomness 2025 Case 2("高交易活动资产收敛慢")

Emergence of Randomness 2025 Case 2 明确陈述:randomness 收敛速度与 trades/s 呈**单调负相关**(trades/s ↑ ⇒ 所需 ℓ ↑)。以下对比表明本 thesis 的 crypto 数据**在 Paper 方法论下被严格预测出来**,不是 outlier:

**Price predictability 2024 / Emergence of Randomness 2025 的 9 只美股**(2022-08 至 2022-11,6.5h 交易日):

| Ticker | trades/s | Emergence of Randomness 2025 分档 |
|---|---|---|
| TSLA | 7.9 | N=1M(最难) |
| AAPL | 6.1 | N=500K |
| SPY  | 4.1 | N=1M |
| MSFT | 3.7 | N=500K |
| INTC | 1.7 | N=100K |
| SNAP | 0.74 | 低频 + bid-ask bounce |
| CCL  | 0.66 | 低频 + bid-ask bounce |
| F    | 0.55 | 低频 + bid-ask bounce |
| LLY  | 0.48 | 最低频 |

Paper 使用范围:**a = 1…50**(Price predictability 2024),**ℓ = 1…100**(Emergence of Randomness 2025)。

**本 thesis 的 5 个 crypto**(Binance Spot,per-month relaxed selected ℓ):

| Asset | 日均 trades/s(量级) | selected ℓ 范围(15 mo) | 2026.03 代表值 |
|---|---|---|---|
| BTCUSDT | ~50–200 | 870–1750 | 880 |
| ETHUSDT | ~30–100 | 420–1194 | 442 |
| SOLUSDT | ~20–80  | 66–598   | 66 |
| BNBUSDT | ~5–30   | 128–464  | 128 |
| DOGEUSDT| ~5–30   | 48–594   | 48 |

本 thesis 使用范围:**ℓ = 50…2000, step 2**。起点即 Emergence of Randomness 2025 上限,上限是 Emergence of Randomness 2025 的 20×、Price predictability 2024 的 40×。

**三重一致性**:
1. Paper 内部:股票 trades/s ↑ ⇒ 所需 ℓ ↑(Emergence of Randomness 2025 Case 2)
2. 本 thesis 内部:crypto trades/s ↑ ⇒ 所需 ℓ ↑(BTC > ETH > SOL/BNB/DOGE)
3. 跨市场:crypto trades/s ≈ 股票的 10× ⇒ 所需 ℓ ≈ 10×(即 Paper 的 ~100 → 本 thesis 的 ~1000 数量级)

**ℓ 范围扩展是 data-driven 的**,不是任意选择。Price predictability 2024 §5.1 已预判:"crypto 交易频率 > AAPL,需要比 50 更大的 ℓ"。本 thesis 推到 2000 兑现了这一外推,且兼作论文贡献之一(Emergence of Randomness 2025 方法论 + 新 ℓ 区间 + 新市场)。

## 6. 固有风险(要进 Limitations)

1. **Offset 必须方法学上固定**。PRNG 不可"use the best offset post-hoc",必须按 deterministic rule 指定(例如 offset=0)。Selected offset 只是诊断,不是 PRNG spec。
2. **D(k=2) / Runs 在 transaction-time 下残留 1 阶结构**。见 §5.2,定位为复现 Price predictability 2024 §4.4 的 bid-ask bounce stylized fact。意味着 transaction-time 下若想做 post-processing-free 的 PRNG,仍需加 debiasing(von Neumann 等);这超出两篇 Reference 的方法论范围,Reference 自己的 Application 章节(Emergence of Randomness 2025 §3.5)也没有声称不需要后处理。**注**:1-second bar 轴上该 1 阶依赖被 62/75 窗口打散(见 [Exp2 Plan B](Exp2%20Plan%20B%20-%20Time-Based%20Aggregation.md) §5),所以这条 limitation 只对 transaction-time 轴适用。
3. **正相关 offset**。all-offset 序列共享底层 tick,正相关会压低 num_pass 的方差 → fraction 门槛的有效"证据量"比理论值低;但这是保守偏差(更难通过),对"防误判"方向 safe。
4. **跨 ℓ 的 multiple selection 未校正**。与 strict 同病,不是 relaxed 独有。
5. **月度 ℓ 时间趋势**。Per-month ℓ 在 2025-2026 呈单调下降,反映市场流动性/tick 结构演化。**独立于 gate 的真实发现**,可作正面叙事;但意味着 selected ℓ 没有"资产稳定值",PRNG spec 需带时间标注。

## 7. 决策:切 1-second bars(已完成)

Plan A 在 transaction-time 轴上已达成所有可声明的目标:

- Asset coverage 75/75 全覆盖(原痛点)
- bits/s 较 strict 提升 7× (~0.003 → ~0.02)
- 月度 ℓ 下降趋势 = 独立 finding(microstructure evolution)
- k=2 / Runs 残留 = 复现 Price predictability 2024 SNAP/F/CCL 的 bid-ask bounce stylized fact
- 资产 ℓ 排序 = 复现 Emergence of Randomness 2025 Case 2(见 §5.4)
- ℓ = 50–2000 是 Price predictability 2024 §5.1 外推预测的兑现

1-second bars 作为第二条聚合轴已实现(Thesis Specification §5 的 "several
time scales" 义务 + Spec 的 "statistically independent random sequences"
独立性侧补充),详见 [Exp2 Plan B - Time-Based Aggregation.md](Exp2%20Plan%20B%20-%20Time-Based%20Aggregation.md)。

**关键后续 finding(见 Plan B §5)**:1-second bar 下 D(k=2) / Runs 在
62/75 个窗口达到 pass-rate ≥ 0.80,与本节 Plan A 观察到的 "每个 witness
p ≪ α" 形成鲜明对比。因此 §5.2 里 "k=2 / Runs 残留是源数据属性" 的表述
需要**收紧**为 "是 transaction-time 轴的属性";物理时间轴在数据密度充足
时可以打散它。

## 8. 论文定位

导师 2026-04 Slack 确认:methodology 按**时间顺序**组织,strict → relaxed,作为 speed / coverage 改进。Relaxed 以 heuristic 身份进主章节(不是 Appendix),Bonferroni/Šidák 作**代码内 sensitivity mode**一并报告。

### 8.1 Methodology 章建议措辞(含 Plan A 主判据)

> "As a heuristic supplementary analysis we also report acceptance under a relaxed gate requiring at least `max(F, f · N_valid)` valid offsets to simultaneously pass both the Predictability (adaptive k) and Monobit tests at α = 0.01 (we used `(F, f) = (3, 0.03)` and `(5, 0.05)`). This is a sensitivity check, not a formal multiple-testing correction; the ∃-pass rule raised by our advisor admits no clean correction in standard theory because high p-values do not constitute positive evidence of randomness. Under the relaxed gate, acceptance extends to all five assets across all monthly windows, with selected ℓ exhibiting a monotone downward trend over 2025-2026 that we interpret as reflecting market microstructure evolution. The witness-offset bitstreams continue to fail the fixed k=2 Predictability test and the NIST Runs test at p ≪ 10⁻³ in every window. Following Price predictability 2024, §4.4, we interpret this as a diagnostic of bid-ask-bounce-induced first-order dependence — the same pattern that paper reports for SNAP, F, and CCL — rather than as a rejection of the selected ℓ by the main acceptance criterion. Adaptive-k D (k ≈ 6-7) is known to dilute first-order signal across 2^(k-1) contexts; the fixed-k=2 test is reported here as a mechanistic diagnostic, not as an acceptance criterion."

### 8.2 Bonferroni / Šidák 作为 sensitivity mode

导师在 Slack 中询问"Bonferroni / Šidák 是否能处理 multiple testing"后,代码内实现了一个 **sensitivity mode**:per-offset 阈值改为 α / N_valid(Bonferroni)或 1 - (1-α)^(1/N_valid)(Šidák),仍沿用 ∃-pass 规则。实际跑过 2025-01 一个月作为对照。**没有采纳为主分析**,理由如下(建议论文 Methodology 或 Appendix 中明写):

> "We also implemented classical Bonferroni and Šidák corrections as a sensitivity mode (per-offset thresholds of α/N and 1−(1−α)^(1/N) respectively), retaining the ∃-pass rule. We did not adopt them as the main analysis for two reasons:
>
> (1) **Direction mismatch**: Bonferroni / Šidák control the family-wise probability of falsely rejecting H₀ (Type I error) by shrinking α. Under an ∃-pass rule, shrinking α makes each offset *easier* to pass (p ≥ α/N is a strictly weaker bar than p ≥ α), so the family-wise probability of falsely *accepting* a non-random sequence *increases* rather than decreases. The correction goes in the wrong direction for the 'random by chance' concern it is meant to address. This is essentially a Type-I-vs-Type-II mismatch: classical α-correction does not directly address the Type-II side, which is the side relevant to ∃-pass.
>
> (2) **Empirical check**: On the 2025-01 window, Bonferroni mode with per-offset α = 0.01 / N_valid produced systematically *smaller* selected ℓ than the heuristic gate (BNB 218 vs 244, BTC 1364 vs 1750, DOGE 274 vs 594, ETH 500 vs 800, SOL 334 vs 596). As predicted by (1), the lower ℓ reflects a more permissive threshold rather than a stronger randomness claim. Šidák produces essentially identical numbers for our N (where α/N ≈ 1 − (1−α)^(1/N))."

### 8.3 代码实现位置

- 主分析:`scripts/runner_exp2_all_offset_relaxed.py`,heuristic gate `max(F, ⌈f·N_valid⌉)`
- Sensitivity mode:`data/processed/experiment2/relaxed-all-offset-per-month-bonferroni-(10,2000,2)/` 下保存 Bonferroni 实测结果
- 代码内以模块级常量或 CLI flag 切换 gate 模式,不同 mode 输出到不同目录避免覆盖
