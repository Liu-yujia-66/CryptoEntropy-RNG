# Paper Reference: Shternshis, Marmi 2025

**Title**: Price predictability at ultra-high frequency: Entropy-based randomness test
**Authors**: Andrey Shternshis (Uppsala), Stefano Marmi (SNS Pisa)
**Venue**: Commun Nonlinear Sci Numer Simulat 141 (2025) 108469
**DOI**: 10.1016/j.cnsns.2024.108469
**Code / Data**: github.com/AndreyShternshis/predictability-at-ultra-high-frequency; data from lobsterdata.com
**Role in this thesis**: Onofri-Shternshis-Marmi 2025 的**直接前作**（在那篇文档里被记为 ref [23]）。本文奠定了 KL-散度检验的理论基础、资产选择（9 资产同一套）、transaction-time 聚合方案、以及 predictable/unpredictable days 的 stylized-fact 对比。Onofri 2025 是把这套检验"工业化"（补 NIST/TestU01、月级拼接、子串化）；本文是"方法论原型"。

---

## 1. 核心贡献

1. **理论**：提出基于 Kullback–Leibler 散度的 NP-statistics $D$，其渐近分布为 $\chi^2$，不要求符号等概率（Shannon entropy 检验要求）。给出显式自由度 $(s^{k-1}-1)(s-1)$。
2. **实证**：9 资产 × 80 天 LOBSTER tick 数据，显示可预测性随聚合水平（transaction-time）的衰减。
3. **机理**：把"predictable days"与 stylized facts（成交量、波动聚集、jump、t 分布厚尾、符号持续性）做 mean-comparison；按资产分三类行为（高频 symbol repetition 类 / 低频 bid-ask bounce 类 / ETF 类）。
4. **局部化**：用 Šidák 校正在日内寻找可预测子区间。

---

## 2. 方法学细节

### 2.1 符号化（和 thesis 完全一致）

二元离散化（Eq. 6）：
$$s^{(2)}_t = \begin{cases} 0, & r_t < 0 \\ 1, & r_t > 0 \end{cases}$$
其中 $r_t = \ln(P_t/P_{t-1})$，**0-return 直接剔除**（不作为第三个符号）。

### 2.2 两个检验

**(A) Shannon entropy bias（Lemma 1）** — 用**非重叠** block
$$B = 2 n_b (k \ln s - \hat H) \xrightarrow{d} \chi^2_{s^k - 1} \quad \text{（要求符号等概率）}$$

**(B) NP-statistics / KL（Lemma 2）** — 用**重叠** block（Billingsley 1961 风格）
$$D = 2 \sum_{ij} f_{ij} \ln \frac{(n-k+1) f_{ij}}{f_{\cdot j} f_{i\cdot}} \xrightarrow{d} \chi^2_{(s^{k-1}-1)(s-1)}$$
且 $D = 2(n-k+1) \cdot \text{KL}\!\left(\frac{f_{ij}}{n-k+1} \,\Big\Vert\, \frac{f_{\cdot j} f_{i\cdot}}{(n-k+1)^2}\right)$。

**这就是 `stats.py::entropy_predictability_test`**。thesis 当前实现一致。

### 2.3 Block 长度

$k = \lfloor 0.5 \log_s n \rfloor$（Shields 1996, §2.3d 建议的可容许上界）。
二元字母表（$s=2$）下，$n = 10^4 \Rightarrow k \approx 6$；$n = 10^5 \Rightarrow k \approx 8$。

### 2.4 显著性判定

单检验 $p < 0.01$ 即判为 **predictable**。多区间检验用 **Šidák 校正**：
$$\alpha_{\text{eff}} = 1 - 0.99^{1/S}, \quad S \le S_{\max} = \lfloor (n-k+1)/1000 \rfloor$$
最小区间长度 1000 symbols。

### 2.5 数据集（作者自己的选股 / ETF）

| Ticker | 均价 | 日成交量 | 日交易数 | 平均间隔 (s) |
|---|---|---|---|---|
| AAPL | 153 | 12.2M | 136K | 0.165 |
| MSFT | 252 | 4.5M | 84K | 0.269 |
| TSLA | 388 | 8.7M | 179K | 0.127 |
| INTC | 30 | 7.1M | 38K | 0.595 |
| LLY | 327 | 0.37M | 11K | 2.086 |
| SNAP | 11 | 5.0M | 19K | 1.358 |
| F | 14 | 4.5M | 13K | 1.815 |
| CCL | 9 | 5.9M | 15K | 1.518 |
| SPY | 391 | 9.1M | 95K | 0.246 |

时间跨度：2022-08-01 至 2022-11-21，80 交易日。9:30–16:00。ns 精度。

### 2.6 聚合方案（transaction-time，和 thesis 一致）

Aggregation level $a$ = "把第 $a$ 个 transaction 当作一步"；只保留每步的最后一笔价格。$a = 1 \ldots 50$（$a=1$ 即原始 tick）。**没有做 all-offset**（那是 Onofri 2025 的扩展）。

### 2.7 Nanosecond-level 同秒多笔处理

ns 精度下仍有同时刻多笔 → 作者在某些图中把同一 ns 内的成交合并成一笔（取最后价）。**这种合并显著降低可预测性**（Fig 7）——即"ns 同刻多笔"本身是可预测性的一个来源（算法撮合）。

---

## 3. 仿真验证（Appendix A, Figs 8–10）

QQ-plot 三个设置：
- $s \in \{2,3,4\}$；$n \in \{10^2, 10^3, 10^4\}$；$N = 10^5$ 次 MC
- **结论**：$n = 10^4$ 收敛良好；$n = 10^3$ 小 $s$ 下可能偏离；$n = 10^2$ 不可用

→ **thesis 的 crypto bitstream 长度远超 $10^4$，渐近 $\chi^2$ 完全可靠。**

---

## 4. 三个市场微观结构模型（Section 4.1）

用于生成"有已知可预测性结构"的 benchmark：

| 模型 | 机制 | 对聚合的行为 |
|---|---|---|
| **λ model** (Lillo–Mike–Farmer 2005) | Hidden order 分拆，Pareto 量分布 | order-sign 层级可预测性随 lag 衰减 |
| **OD model** (Chiarella–Iori 2002) | 基本面 + 历史 trader | order sign 在 lag>1 即失效；但 **price-return 方向持续可预测到 $a=50$**（因为 mean-reverting 导致符号交替） |
| **TS model** (Bouchaud–Gefen–Potters–Wyart 2003) | Trade superposition + 衰减 propagator | price-return 可预测性随 $a$ 增加**单调衰减** → 与真实 tick 数据最相似 |

**thesis 里 BTC/ETH 的衰减曲线预期更像 TS 模型。**

---

## 5. 主要实证发现（与 thesis 相关性强的）

### 5.1 聚合衰减（Figs 6, 7）— thesis Exp2 的直接对应

- 所有 9 资产在 $a=1$（无聚合）下几乎全部日期 predictable（除 INTC/SNAP/F/CCL 有 30–70% 不 predictable）
- 随 $a$ 增加，predictable 比例单调（非严格）下降
- 收敛速度与资产交易频率高度相关：**高频资产（AAPL/TSLA/MSFT/SPY）需要更大 $a$ 才能洗白**
- **直接启示**：crypto（BTCUSDT 交易频率 > AAPL）需要比 50 更大的 $\ell$，所以 thesis 用 $\ell = 50\ldots 2000$ 是有文献基础的

### 5.2 Predictable 日的 stylized facts（Table 3）

在合适的 $a$ 下（使 predictable/unpredictable 两组大致平衡），predictable 日的共同特征：

| 特征 | 方向 | 涵盖资产 |
|---|---|---|
| 日交易数（非零 return 数）| ↑ | 所有 |
| 日成交量 | ↑ | 除 TSLA/SNAP 外全部 |
| $|ρ_1|$ of 非零 returns | ↑ | 8/9 |
| $|ρ_1|$ of $|r_t|$（波动聚集）| ↑ | AAPL, SNAP, F, CCL |
| 对称 block 概率 $\hat p(0\ldots0)+\hat p(1\ldots1)$ | ↑ | AAPL, MSFT, TSLA, INTC, LLY, SPY |
| 同上 | ↓（即 bid-ask bounce 更强）| SNAP, F, CCL |
| t 分布 $\nu$（厚尾）| ↓ 更厚尾 → SPY predictable；但 CCL/F 相反 | 混合 |
| Jump 比例 | ↑ | 仅 CCL |

**两类"可预测"机理**：
- 高频资产：**符号持续性**（news / order splitting）
- 低频低价资产（SNAP/F/CCL）：**bid-ask bounce** 导致符号反转过强（$\hat p(00)+\hat p(11) < 0.5$）

### 5.3 具体可解释事件（TSLA）

作者检查了 $a=65$ 下残留的 4 个 predictable 日：
- 08-05: 3:1 拆股股东投票
- 09-14: Autopilot 虚假宣传诉讼
- 11-08: 召回 4 万辆车
→ **新闻事件 → 高频可预测性** 的经验证据。

### 5.4 日内局部化（Table 8）

用 Šidák 在日内寻找 $S$ 个等长子区间中的 predictable 子区间：
- 多数 predictable 日只有 1 个 predictable 子区间（不连续）
- **SNAP 是唯一有 "连续多个 predictable 子区间" 的资产**（10-21、10-24 各有 7 个连续）

---

## 6. 与 thesis 的对齐要点

### 6.1 检验方法层

| Shternshis–Marmi 2025 | thesis 当前 |
|---|---|
| Shannon entropy bias $B$ (Eq 2) | 未实现（Onofri 2025 仍保留，属 "optional"）|
| NP/KL $D$ (Eq 3) | ✅ `entropy_predictability_test` |
| $k = \lfloor 0.5 \log_s n \rfloor$ | ✅ thesis 同公式 |
| ns 同刻合并 | ⚠️ thesis 数据来自 Binance 1s/1min agg，已无 ns 问题；但值得在 Methodology 里注明"ns-level clustering 不适用于本 thesis 的数据源" |
| Šidák 日内局部化 | thesis 未做；**可作为 future work 或 Exp3 扩展**  |

### 6.2 结论对齐

- **随 $a$ 增加可预测性下降** → thesis Exp2 主结论一致 ✓
- **交易频率越高，需要的 $a$ 越大** → 解释 thesis 中 BTC vs DOGE 的差异的 direct citation ✓
- **symbol persistence 是主因** → thesis 在高 $\ell$ 下 Runs/ApproxEntropy 的失败模式可以用此机理叙述 ✓

### 6.3 建议引用位置

- **Introduction**：介绍 entropy-based randomness test 的理论基础（Lemma 1 & 2 的出处）
- **Methodology / KL test**：直接引 Eq 3 + Lemma 2 给出自由度
- **Discussion**：解释"高频资产需要更大聚合"时直接引 Fig 6 + Section 5
- **Limitations**：引"predictability 不等于套利机会（transaction cost 抵消）"（Lillo–Farmer 2004, Bouchaud et al. 2003）

---

## 7. 关键公式速查

$$D = 2 \sum_{i=0}^{s^{k-1}-1} \sum_{j=0}^{s-1} f_{ij} \ln \frac{(n-k+1) f_{ij}}{f_{\cdot j} f_{i\cdot}}, \quad D \xrightarrow{d} \chi^2_{(s^{k-1}-1)(s-1)}$$

$$\text{KL} \xrightarrow{d} \text{Gamma}\!\left(\frac{(s^{k-1}-1)(s-1)}{2}, \frac{1}{n-k+1}\right)$$

$$k_{\text{admissible}} = \lfloor 0.5 \log_s n \rfloor \quad \text{(Shields 1996)}$$

$$\alpha_{\text{Šidák}} = 1 - (1-\alpha)^{1/S}$$

---

## 8. 与 Onofri–Shternshis–Marmi 2025（后续工作）的关系

| 维度 | 本文 (2025a) | Onofri 2025 (2025b) |
|---|---|---|
| 检验数 | 2（$B$, $D$）| 46（9 NIST + 9 Alphabit + 26 Rabbit + 2 entropy）|
| 聚合 | 单 offset ($j=1$) | all-offset（每 $\ell$ 用 $\ell$ 个 offset）|
| 序列拼接 | 日内单日序列 | 月级跨日拼接 |
| 子串化 | 无 | t=128 / t=1000 子串化检验 |
| Sanity check | Appendix A 仅 QQ | 三个真随机源 × 4 长度 |
| $\ell$ 范围 | 1–50 | 1–100 |
| 数据集 | 同 9 资产 | 同 9 资产 |

→ **本文是原型，Onofri 2025 是工业化版。thesis 站在 Onofri 2025 的肩膀上，再推进到 crypto + 更大 $\ell$。**

---

## 9. Exp2 实现 vs 本文的逐项比对

### 9.1 完全对齐 ✅

| 维度 | Paper | thesis | 位置 |
|---|---|---|---|
| 符号化 | up=1 / down=0 / remove r=0 (Eq 6) | `nonzero_mask; (delta>0)` | [bitstream.py:45-47](src/bitstream.py#L45-L47) |
| Block 长度 | $k=\lfloor 0.5\log_s n\rfloor$ | `_adaptive_k` | [stats.py:240-250](src/stats.py#L240-L250) |
| NP/KL 统计量 | $D=2\sum f_{ij}\ln\frac{(n-k+1)f_{ij}}{f_{\cdot j}f_{i\cdot}}$ (Eq 3) | `expected = context_counts * p_next`；`2*joint*log(joint/expected)` | [stats.py:215-224](src/stats.py#L215-L224) |
| 自由度 | $(s^{k-1}-1)(s-1)=2^{k-1}-1$ | `num_contexts-1` | [stats.py:227-228](src/stats.py#L227-L228) |
| 显著性 | α=0.01 | `ALPHA=0.01` | [runner_exp2_all_offset.py:74](scripts/runner_exp2_all_offset.py#L74) |
| Transaction-time 聚合 | 每 $a$ 笔取最后价 | `price[offset::agg_level]` | [bitstream.py:41](src/bitstream.py#L41) |

### 9.2 合理扩展（thesis 的贡献点）🔄

| 维度 | Paper | thesis | 评注 |
|---|---|---|---|
| 聚合范围 | $a=1..50$ | $\ell=50..2000$ (step 25/50) | **直接由 Paper §5.1 Case 2 启发**（高频资产需更大 $a$）。需在 methodology 里显式援引。 |
| Offset 结构 | 只用 offset=0 | all-offset (每 $\ell$ 跑 $\ell$ 个 offset)+ single-offset baseline | Onofri 2025 引入；thesis 同时保留两种以做对比 |
| 序列单位 | per-day | per-quarter（跨月拼接） | **潜在隐患**：Paper Lemma 假设 stationary process；跨日边界的 overnight gap 可能破坏这个假设。值得在 Limitations 写一句。 |
| 接受判据 | 单日 $p<0.01$ | pass-rate≥80% across offsets + valid_offset_ratio≥80% + 三个 NIST 检验 | 因为 all-offset 每 $\ell$ 给出 $\ell$ 个 p-value，需聚合；Onofri 2025 用箱形图，thesis 用 pass-rate |
| 检验覆盖 | $B$ + $D$ (2 个) | monobit + runs + ApproxEntropy(m=5) + $D$ (4 个) | $B$ 未实现（建议补，见 §10）；NIST 三件套是 thesis 相对 Paper 的加分项 |

### 9.3 值得修的小问题 ⚠️

1. **`MIN_BIT_COUNT=2000` 低于 Paper Appendix A 经验底线**
   Paper Figs 8–10 QQ 显示 $n=10^3$ 在小 $s$ 下可能偏离 $\chi^2$，$n=10^4$ 才稳。当前 [runner_exp2_all_offset.py:73](scripts/runner_exp2_all_offset.py#L73) 用 2000。对 DOGE/BNB 大 $\ell$ 边缘样本，渐近分布近似可能不牢。

2. **`stats.py:228` 注释/变量名不一致**
   注释写 $2^{k-1}-1$、变量叫 `num_contexts-1`、参数叫 `history_length=m`，三套命名易误读。

3. **Shannon-bias 检验 $B$ 未实现**
   Paper 同时报告 $B$ 和 $D$ 做 cross-check。当前 thesis 只有 $D$。

---

## 10. 行动清单

### 10.1 🔧 建议做（工作量小、收益明确）

| 项 | 为什么 | 工作量 |
|---|---|---|
| **加 Shannon-bias 检验 $B$** | Paper 双检验之一，零理论成本，可在 discussion 做 $B$ vs $D$ cross-check | 半天（一个函数 + 接入 `summarize_bits_full`）已完成|
| **`MIN_BIT_COUNT` 2000 → 5000** | Paper Appendix A QQ 显示 $n<10^4$ 边缘；5000 是折中，但比 2000 稳 | 改一行 + 重跑受影响 $\ell$ |
| **修 `stats.py:228` 注释/变量名一致性** | 注释写 $2^{k-1}-1$、变量叫 `num_contexts-1`、参数叫 `history_length=m`，三套命名易误读 | 10 分钟 已完成|

### 10.2 ⏭️ 写入 future work（不做）

- **Šidák 日内局部化**（Paper §4.5）— Exp2 主线用不上，Exp3/4 才需要
- **λ / OD / TS 仿真 benchmark**（Paper §4.1）— 作为 "positive control" 验证实现正确性很漂亮，但 Paper 已证方法正确，thesis 可以直接引
- **per-day 粒度分析 + predictable-day stylized facts**（Paper §4.3, Table 3）— thesis 是季度级聚合，和 Paper 的日级分析不在一个粒度；如要做等于再开一个 Exp

### 10.3 📝 Methodology 必须讲的

1. **符号化 + $k$ + $D$ + DOF + α** 全部显式援引 Paper Eq 3 / Lemma 2（说明这不是 thesis 发明的）
2. **all-offset + pass-rate 聚合规则** 是 Onofri 2025 引入、thesis 沿用的扩展（避免被质疑"为什么不像 Paper 那样单检验判定"）
3. **$\ell=50..2000$ 的选择理由**：援引 Paper §5.1 Case 2（高频资产需要更大 $a$），crypto 比 AAPL/TSLA 更高频 → 推到 2000 是数据驱动的外推

### 10.4 ⚠️ Limitations 必须写的

1. **跨月拼接可能违反 Paper Lemma 的 stationary 假设**（overnight gap + 月度 regime change）。一句话承认即可；不需修方法。
2. **$n<10^4$ 的样本渐近 $\chi^2$ 近似边缘**（即使把 MIN_BIT_COUNT 提到 5000 仍低于 Paper Appendix A 的 $10^4$ 基准）— 注明"边缘样本，结论需谨慎"
3. **Binance aggTrades 已在交易所端聚合，无 ns-level 信息** → Paper §4.2 的"同 ns 合并"不适用；既是限制也是数据源决定的，写清楚即可
4. **只用二元字母表 ($s=2$)**，未探索 $s=3$（含 flat）或基于中位数的重新编码（Paper §4.3 末尾提到的修正）

### 10.5 一句话总结

**做 3 件小事（加 $B$、提 MIN_BIT_COUNT、改注释），其余全部归 future work 或写进 methodology/limitations 的对应段落。** 不要为 Paper 的方法细节再开新实验。
