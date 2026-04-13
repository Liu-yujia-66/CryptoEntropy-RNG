> **Scope note — master thesis, not publication**
>
> 本文档以 Paper 的完整方法为参考上限，但这是一篇硕士毕业论文，不需要与 Paper 一对一复刻。实际的 master thesis 尺度：
>
> - **必做**：保留当前 4 个检验（3 NIST + KL），将 ApproxEntropy 的 m 从 2 改为 5 以对齐 Paper 参数；Exp2 的 selected-ℓ + pass-rate 主线；Exp3 的 entropy production rate 展开讨论。
> - **可选加分**：补 2–3 个 NIST 测试（Block Frequency / Cumulative Sums 等）；在每个资产的 selected-ℓ 上单点跑一次 TestU01 Rabbit 作为外部验证（**不**跑整个 ℓ sweep）。
> - **不必做 / 写成 future work**：完整 9 个 NIST；Alphabit + Rabbit 全 35 个检验；TestU01 全 ℓ sweep；自建 sanity check（直接引用 Paper Table 3）；Exp4 多资产融合；password generator prototype。
>
> thesis 核心贡献不是复刻 Paper，而是：(i) 把方法从股票推广到加密货币；(ii) 在更高 ℓ 区间观察现象；(iii) 量化 randomness-throughput trade-off。检验覆盖够用即可。
>
> 下面清单按 Paper 原貌记录，用作对标参考，**不是行动清单**。

---

# Paper Reference: Onofri, Shternshis, Marmi 2025

**Title**: Emergence of Randomness in Temporally Aggregated Financial Tick Sequences
**Authors**: Silvia Onofri (SNS Pisa), Andrey Shternshis (Uppsala), Stefano Marmi (SNS Pisa)
**arXiv**: 2511.17479v1 (21 Nov 2025)
**Role in this thesis**: 直接对标工作。proposal 中那张 "-log(p) vs aggregation level" 的示意图即出自此论文（或其前作 ref [23]）。

---

## 1. 检验总清单（46 个）

### 1.1 NIST SP800-22 STS — 15 个中用了 9 个

| # | 测试 | Paper 的参数 | 跳过理由（若跳过）|
|---|---|---|---|
| 1 | Frequency (Monobit) | t=128 | ✓ used |
| 2 | Block Frequency | t=128, M=20 | ✓ used |
| 3 | Cumulative Sums | t=128 | ✓ used |
| 4 | Runs | t=128 | ✓ used |
| 5 | Longest Run of Ones | t=128, M=8 | ✓ used |
| 6 | Approximate Entropy | t=128, **m=5** | ✓ used |
| 7 | Serial | t=128, m=2 | ✓ used |
| 8 | DFT (FFT) | t=1000 | ✓ used |
| 9 | Non-overlapping Template | t=1000, m=9 | ✓ used |
| 10 | Binary Matrix Rank | — | skip: 需要 ≥38,912 bits |
| 11 | Overlapping Template | — | skip: 需要 ≥10⁶ bits |
| 12 | Maurer's Universal | — | skip: 需要 ≥387,840 bits |
| 13 | Linear Complexity | — | skip: 需要 ≥10⁶ bits |
| 14 | Random Excursions | — | skip: 需要 ≥10⁶ bits |
| 15 | Random Excursions Variant | — | skip: 需要 ≥10⁶ bits |

**重要：Paper 的 ApproxEntropy 用 m=5，不是当前 `stats.py` 里的 m=2。这是一个需要改的地方。**

### 1.2 TestU01 Alphabit — 全部 9 个

| # | 测试 |
|---|---|
| 1 | MultinomialBitsOverlapping, L=2 |
| 2 | MultinomialBitsOverlapping, L=4 |
| 3 | MultinomialBitsOverlapping, L=8 |
| 4 | MultinomialBitsOverlapping, L=16 |
| 5 | HammingIndependence, L=16 |
| 6 | HammingIndependence, L=32 |
| 7 | HammingCorrelation, L=32 |
| 8 | RandomWalk1, L=64 |
| 9 | RandomWalk1, L=320 |

### 1.3 TestU01 Rabbit — 全部 26 个

| # | 测试 | # | 测试 |
|---|---|---|---|
| 1 | MultinomialBitsOverlapping | 14 | HammingCorrelation, L=128 |
| 2 | ClosePairsBitMatch, t=2 | 15 | HammingIndependence, L=16 |
| 3 | ClosePairsBitMatch, t=4 | 16 | HammingIndependence, L=32 |
| 4 | AppearanceSpacings | 17 | HammingIndependence, L=64 |
| 5 | LinearComp | 18 | AutoCorrelation, d=1 |
| 6 | LempelZiv | 19 | AutoCorrelation, d=2 |
| 7 | Fourier1 | 20 | Run |
| 8 | Fourier3 | 21 | MatrixRank, 32×32 |
| 9 | LongestHeadRun | 22 | MatrixRank, 320×320 |
| 10 | PeriodsInStrings | 23 | MatrixRank, 1024×1024 |
| 11 | HammingWeight, L=32 | 24 | RandomWalk1, L=128 |
| 12 | HammingCorrelation, L=32 | 25 | RandomWalk1, L=1024 |
| 13 | HammingCorrelation, L=64 | 26 | RandomWalk1, L=10016 |

### 1.4 自家 entropy-based 检验 — 2 个

| 测试 | 说明 |
|---|---|
| ShannonEntropy test | Y1 = 2Nb(k ln 2 − Ĥ), χ²(2^k − 1), 要求 0/1 均衡 |
| KL test | Y2 = 2 Σ f_ij ln(No·f_ij / (f_·j·f_i·)), χ²(2^(k-1) − 1), 不要求 0/1 均衡 |

**KL test 就是你 `stats.py` 里的 `entropy_predictability_test`。实现已一致，无需改动。**

---

## 2. 关键方法学细节

### 2.1 Bitstream 构造（和你完全一致）

- 对每一天的价格序列 {s₁, ..., s_N}
- 对每个聚合级别 ℓ = 1...100（Paper 的范围，你用 50...2000）
- 对每个 offset j = 1...ℓ
- 构造比特：r = s_{j+iℓ} / s_{j+(i-1)ℓ}，r<1 → 0，r>1 → 1，r=1 → 跳过

### 2.2 跨日拼接（你是跨月拼接，类似）

Paper：每月内的日级 bitstream 串接成月级序列 b^m = b^d1 || b^d2 || ... || b^dn
你：每季度内的月级 bitstream 串接成季度级序列

### 2.3 Substring-based 检验 ⚠️

**这是你当前实现没做的关键一步**：

- Paper 把月级长序列按 **t=128 bits**（多数 NIST 测试）或 **t=1000 bits**（DFT、NonOverlapping）切成子串
- 每个子串独立出一个 p-value
- 每个 ℓ 得到一个 p-value 分布（可画箱形图）

你当前是整条序列跑一次得一个 p-value，这和 NIST SP800-22 标准流程不一致。

### 2.4 Sanity check 流程

Paper 用三个真随机源做 sanity check：
1. **Quantis QRNG USB**（量子）
2. **Linux /dev/urandom**（环境噪声）
3. **Möbius 函数**（纯数学，基于 Riemann Hypothesis 相关性）

在 N = 50K / 100K / 500K / 1M bits 下跑所有检验。误拒率 > 2% 的检验即判定为"在该比特量下不可用"，不在真实数据上跑。

**结果（Paper Table 3）— 你可以直接引用**：

| Test | 50K | 100K | 500K | 1M |
|---|---|---|---|---|
| Frequency | ✓ | | | |
| BlockFrequency | ✓ | ✓ | | |
| CumulativeSums | ✓ | ✓ | | |
| Runs | ✓ | ✓ | ✓ | |
| LongestRun | ✓ | ✓ | ✓ | |
| Approx. Entropy | ✓ | ✓ | ✓ | ✓ |
| Serial | ✓ | ✓ | ✓ | ✓ |
| FFT | ✓ | ✓ | | |
| NonOverlappingTemplate | ✓ | ✓ | | |

空白 = 在该长度下不可靠。

**对应到你的资产**（Paper 的映射规则）：
- N=50K 适用于：交易较少的资产
- N=100K：INTC/LLY 类中等
- N=500K：AAPL/MSFT 类高频
- N=1M：SPY/TSLA 类最高频

你的加密货币交易量普遍比股票高（BTC 尤其），因此大多数资产对应 **N=500K 或 1M** 一档。

### 2.5 数据集规模

| Paper 的 | 你的 |
|---|---|
| 80 交易日 | 3 个月 ≈ 90 日 |
| 9 资产（股票） | 5 资产（加密货币） |
| ℓ = 1...100 | ℓ = 50...2000 |
| 每月月级序列 | 每季度季度级序列 |

### 2.6 可视化

Paper 对每个 (asset, month, test) 画箱形图：x 轴 ℓ，y 轴每个 offset 的 -log10(p) 分布。
你当前用 pass-rate vs ℓ，信息量略低于箱形图。**可以补一张**。

---

## 3. Paper 的关键发现（对你的研究有直接启发）

### 3.1 一致的主结论

随机性总体上随 ℓ 增加而增强（Case 1）。**和你的 Exp2 结论一致。**

### 3.2 高交易活动资产收敛慢（Case 2）

AAPL（6 trades/s）和 TSLA（8 trades/s）即使在 ℓ=100 时许多检验仍失败；低频资产 CCL（0.6 trades/s）和 LLY（0.5 trades/s）容易收敛。

**对应到你的数据**：BTCUSDT 是最高频资产，这直接解释了你为什么 BTC 需要 ℓ >> 2000 才能通过 Runs/ApproxEntropy。**这是论文里已确立的 stylized fact，你可以直接引用解释 BTC 的行为。**

### 3.3 非单调 Predictability 曲线（Case 3）

Fourier3 测试在某些股票上显示可预测性的最大值不在 ℓ=1，而是在更高的 ℓ。归因于算法交易的周期性或订单拆分的微观结构。

**对应**：你如果接 Rabbit，Fourier3 测试可能在 BTC/ETH 上出现类似模式。

### 3.4 Hamming 类检验对 0/1 不均衡敏感（Case 4）

INTC 八月数据中，HammingCorrelation 随 ℓ 增加反而更不随机。根本原因是 0/1 频率严重偏离 0.5。Paper 提出了一个基于中位数的重新编码方法（非在线，需等日终）作为修正。

**对应**：如果你的 DOGE 或某些资产也有频率偏差，需要考虑类似修正。

### 3.5 Application 部分

Paper 声称：在 ℓ=100 下，每天可提取约 **500 bits of entropy**（10,000 bits / 月 ÷ 20 trading days），作为 model-free PRNG。

**对比你**：Exp2 的 bits/s 直接给出你的 entropy rate，这一节是你 thesis 的核心定位（crypto vs 股票，higher volume → ?）。

---

## 4. 你当前状态 vs Paper 对标

### 4.1 已完成

| 你有的 | 对应 |
|---|---|
| monobit_test | NIST Frequency ✓ |
| runs_test | NIST Runs ✓ |
| approximate_entropy_test (m=2) | NIST Approximate Entropy（Paper 用 m=5，需改）|
| entropy_predictability_test | KL test ✓（完全一致） |
| longest_run（函数） | 未做成正式 χ² 检验 |

### 4.2 缺失

**NIST STS（6 个）**：Block Frequency, Cumulative Sums, Longest Run of Ones, DFT, Non-overlapping Template, Serial

**TestU01 Alphabit**：全部 9 个

**TestU01 Rabbit**：全部 26 个

**Entropy-based**：ShannonEntropy test（KL 已有）

### 4.3 方法学差异

| Paper | 你当前 |
|---|---|
| NIST 对 t=128/1000 子串独立检验 | 整序列一次检验 |
| 有 sanity check 流程筛选适用测试 | 无（可引用 Paper Table 3 省掉）|
| 箱形图 (-log10(p) across offsets vs ℓ) | pass-rate vs ℓ |
| ℓ = 1...100 | ℓ = 50...2000（贡献点）|
| 用 m=5（ApproxEntropy）| 用 m=2（需改）|

---

## 5. 行动项

### 5.1 必做（对齐 Paper 检验覆盖）

1. **修 `approximate_entropy_test`：默认 m 改 5 或设为参数**
2. **NIST 改为 substring-based 检验**：按 Paper Table 4 参数切块（大多数 t=128，DFT/NonOverlapping t=1000）
3. **补齐 6 个 NIST STS 测试**：Block Frequency, Cumulative Sums, Longest Run, DFT, Non-overlapping Template, Serial
4. **接 TestU01**：C driver + 二进制文件管道 → Alphabit + Rabbit

### 5.2 Sanity check 处理

**不重跑，直接引用 Paper Table 3**。在 methodology 章节写：

> "Following Onofri et al. (2025), we determine the applicability of each test at different string lengths using their sanity-check results (Table 3 in the original paper), which validated tests against three independent random sources (quantum, /dev/urandom, Möbius function) with a 2% false-rejection threshold."

### 5.3 可视化补充

在 all-offset plot 基础上补一张箱形图版本（每个 ℓ 的 -log10(p) 分布 across offsets），直接对比 Paper 的 Figures 1-7。

### 5.4 ApproxEntropy 参数

Paper 用 **m=5**，你的 `stats.py` 默认 **m=2**。Paper Table 4 明确说 m<⌊log₂ t⌋-5，你当前串长 n >> 2⁷，m=5 完全合规且更敏感。**改掉。**

---

## 6. 论文定位（methodology 章节草稿）

> "We follow the methodology of Onofri, Shternshis, and Marmi (2025) for assessing the randomness of temporally aggregated financial tick sequences. Price sequences are symbolized to binary strings via the up/down indicator of consecutive price ratios, and aggregation is performed by sampling every ℓ-th transaction across all ℓ offsets. We apply the same subset of nine NIST STS tests together with the full TestU01 Alphabit and Rabbit sub-batteries, at the parameters specified in their Table 4, and rely on their Table 3 sanity-check results to determine test applicability at each string length.
>
> We extend their analysis in three directions: (i) we apply this methodology to the cryptocurrency market (BTC, ETH, BNB, SOL, DOGE) rather than U.S. equities; (ii) we explore a substantially larger aggregation range (ℓ = 50 to 2000, vs. 1 to 100 in the original work), motivated by the finding that high trading activity slows the emergence of randomness and by the observation that crypto tick data have transaction rates an order of magnitude higher than the stocks studied in [Paper B]; and (iii) we quantify the trade-off between the randomness threshold and the effective entropy-bit throughput at each aggregation level, informing the practical feasibility of using aggregated crypto ticks as a randomness source."

---

## 7. 时间估算

| 任务 | 工作量 |
|---|---|
| 修 ApproxEntropy m=5 + substring 化 | 1 天 |
| 补 6 个 NIST STS 测试 | 3 天 |
| TestU01 集成（C driver + Python 管道）| 1-2 周 |
| 箱形图可视化 | 0.5 天 |
| 整合到 runner / 验证脚本 | 2 天 |
| **合计** | **2.5-3 周** |

这部分对应 Deliverable #2 (NIST/TestU01 statistical report)，必做。TestU01 是对标 Paper 的关键组件，不能砍。
