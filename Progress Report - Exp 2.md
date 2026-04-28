# Progress Report: Experiment 2 Temporal Aggregation

> 时间：2026-04 | 范围：Experiment 2（时间聚合对随机性的影响）
> 对应 Initial Plan: Exp2（找到聚合临界点）
> 主 Reference：Price predictability 2024；Emergence of Randomness 2025

---

## 1. 实验目标与设计演化

Initial Plan 里 Exp2 的目标是：在多个 aggregation level $\ell$ 下把 crypto 价格序列编码成 bitstream，通过 NIST / predictability 检验寻找"随机性涌现"的 $\ell$ 临界点。

实际实施过程中，检验框架与聚合方式经过两次调整，最终与 Emergence of Randomness 2025 的方法论对齐：

| 阶段 | 聚合方式 | 检验 gate | 来源 |
|---|---|---|---|
| 初版 | single-offset | 直接看 Shannon entropy、p(1)、runs p-value | Initial Plan |
| 中间版 | transaction-time all-offset strict | ≥80% valid + ≥80% pass D + ≥80% pass Monobit（完整 gate 见 §3.1） | Emergence of Randomness 2025 |
| relaxed | transaction-time all-offset relaxed | heuristic ∃-pass gate | 导师 2026-04 建议 |
| 终版 | **1-second bar** all-offset strict | ≥80% valid + ≥80% pass D + ≥80% pass Monobit（base）；另报 +Runs / +Runs+ApEn | Spec §5 "several time scales" + 独立性侧空间 |

数据：5 个 USDT spot 对（BTC, ETH, BNB, SOL, DOGE），2025.01–2026.03（15 个月），来自 Binance aggTrades。所有 gate 均以 per-month 为分析单元。

---

## 2. Single-Offset 阶段

### 2.1 方法

对齐 Initial Plan 的最初设计：每个 asset 只生成一条聚合序列，扫描 $\ell$ 观察 p-value 随 $\ell$ 的演化。

- 固定 `offset = 0`（取每 $\ell$ 个 trade 的第一笔价格）
- $\ell \in \{50, 75, \ldots, 2000\}$，step 25
- Periods：15 个月（2025.01–2026.03）
- 每个 (asset, $\ell$) 上跑完整检验电池：Monobit、Runs、ApproxEntropy (m=5)、Predictability D（adaptive k）、D(k=2)、Shannon-bias
- 实现详见 [scripts/runner_exp2_single_offset.py](scripts/runner_exp2_single_offset.py)

**更早的非正式试探**（使用 Shannon entropy、p(1)、lag-1 autocorrelation 等直接指标）曾给出 $\ell \approx 200 / 500 / 1000$ 的启发性分档。引入正式检验电池后这组启发值被 supersede，下文以 runner 输出的正式 p-value 结果为准。

### 2.2 结果（per-month, single-offset gate）

数据：`data/processed/experiment2/single-offset-per-month(50,2000,25)/selected_ell_by_window.txt`。
判据：在 $\ell$ 网格 $\{50, 75, \ldots, 2000\}$（step 25）上取最小的 $\ell$，使 offset=0 的 bitstream 同时满足 Predictability（adaptive $k$）p ≥ α 和 Monobit p ≥ α，且 `bit_count ≥ MIN_BIT_COUNT = 2000`。"—" 表示 $\ell \leq 2000$ 内无可接受 $\ell$。

| Window | BNB | BTC  | DOGE | ETH  | SOL |
|---|---|---|---|---|---|
| 2025.01 | 275 | —    | 825  | 925  | 750 |
| 2025.02 | 475 | 1650 | 225  | 875  | 500 |
| 2025.03 | 250 | 1800 | 375  | 625  | 275 |
| 2025.04 | 250 | 1700 | 275  | 750  | 225 |
| 2025.05 | 250 | 1500 | 225  | 1250 | 400 |
| 2025.06 | 200 | 1100 | 125  | 525  | 225 |
| 2025.07 | 375 | 1975 | 250  | 600  | 400 |
| 2025.08 | 275 | —    | 250  | 1575 | 475 |
| 2025.09 | 350 | 900  | 250  | 850  | 300 |
| 2025.10 | 850 | 1375 | 175  | 725  | 225 |
| 2025.11 | 300 | 1125 | 150  | 875  | 150 |
| 2025.12 | 275 | 1050 | 75   | 600  | 125 |
| 2026.01 | 250 | 1300 | 125  | 725  | 175 |
| 2026.02 | 250 | 1225 | 100  | 550  | 200 |
| 2026.03 | 175 | 1075 | 100  | 575  | 100 |

Coverage：**73/75** cells（BNB / DOGE / ETH / SOL 15/15，BTC 13/15；BTC 在 2025.01 与 2025.08 单 offset 下不过）。

### 2.3 观察

1. **BTC 是最难的 asset**：单 offset 也只有 13/15 月份过线；过线月份 selected $\ell$ 仍在 900–1975 之间，远高于其它 4 个资产
2. **DOGE / BNB 最容易**：DOGE 后期 selected $\ell$ 已掉到 75–125（2025.12–2026.03），BNB 多月在 200–300 区间
3. **跨月稳定性差**：同一资产相邻月份 selected $\ell$ 跳动剧烈（如 BNB 2025.10 = 850 vs 2025.09 = 350、2025.11 = 300），single-offset 没有"稳定值"概念
4. **跨年下降趋势**：除 BTC 外 4 个资产从 2025.01 → 2026.03 总体呈下降，与微观结构演化一致（per-month 时间分辨率才能看到）

### 2.4 Single-offset 的方法学局限

在进入 all-offset 之前识别出 single-offset 设计本身的三条系统性问题（详见 [Exp2 Limitations.md](Exp2%20Limitations.md)）：

1. **p-value 解释歧义**：$\ell$ 增大时 bitstream 缩短，p-value 上升可能来自"随机性真的改善"或"检验功效下降"。单条曲线无法区分。
2. **Adaptive-k 的横轴不可比**：predictability test 内部 $k = \lfloor 0.5 \log_2 n \rfloor$ 会随 $\ell$ 跳变，拐点的"随机性来源"和"k 变动来源"耦合。
3. **单次抽样**：`offset = 0` 只用了 $1/\ell$ 的原始数据，且没有稳定性的概念。同一 $\ell$ 下换 offset 可能结果不同；single-offset 无法检出这种不稳定性。

结论：single-offset 的 p-value 曲线只作为**诊断性趋势图**，不能作为 $\ell$ 选择的严格依据。这直接推动了向 all-offset + pass-rate 框架的升级（Emergence of Randomness 2025 方法论）。

---

## 3. All-Offset Strict 阶段（对齐 Emergence of Randomness 2025）

### 3.1 方法升级

- 对每个 $\ell$，构造全部 $\ell$ 个 offset 的 bitstream（跨月拼接），每条独立跑检验电池
- **Acceptance gate**（三条 AND）：
  - `valid_offset_ratio ≥ 0.80`（≥80% 的 offset 有 ≥ `MIN_BIT_COUNT = 2000` bits）
  - `predictability_pass_rate ≥ 0.80`（≥80% valid offsets 过 adaptive-k D，α=0.01）
  - `monobit_pass_rate ≥ 0.80`
- Runs 和 D(k=2) 保留计算但**降为 reference**，不入 gate
  - 理由：adaptive-$k$ D 把 1 阶信号稀释到 $2^{k-1} \approx 64$ 个 context；若把 Runs 纳入 gate 会系统性地把 BTC/ETH 挡死。Price predictability 2024 §4.4 已把这种差异识别为 bid-ask bounce 的副产物，不是 gate 设计错误。详细论证见 [Exp2 Limitations.md](Exp2%20Limitations.md) "Acceptance gate 的修订"
- 对每个资产选出最小的 acceptable $\ell$

### 3.2 Grid 设计

- $\ell \in \{50, 75, \ldots, 2000\}$，step 25（共 79 个候选）
- Periods：15 个月（2025.01–2026.03）
- 每 period 内 3 个并发 worker
- 实现详见 [scripts/runner_exp2_all_offset.py](scripts/runner_exp2_all_offset.py)

### 3.3 Selected $\ell$（strict, per-month）结果

数据：`data/processed/experiment2/all-offset-per-month(50,2000,25)/selected_ell_by_window.txt`。

| Month | BNB | BTC | DOGE | ETH | SOL |
|---|---|---|---|---|---|
| 2025.01 | 325  | —    | 1075 | 1900 | —   |
| 2025.02 | 700  | —    | 900  | 1025 | —   |
| 2025.03 | 350  | —    | 500  | 1150 | 425 |
| 2025.04 | 275  | —    | 375  | 975  | 600 |
| 2025.05 | 475  | —    | 650  | —    | 625 |
| 2025.06 | 250  | 1325 | 125  | 850  | 300 |
| 2025.07 | 425  | —    | 650  | 1275 | 550 |
| 2025.08 | 300  | —    | 375  | —    | 650 |
| 2025.09 | 375  | 1500 | 450  | 975  | 425 |
| 2025.10 | 1025 | 1625 | 225  | 1300 | 350 |
| 2025.11 | 450  | 1600 | 200  | 1400 | 225 |
| 2025.12 | 275  | 1275 | 75   | 700  | 150 |
| 2026.01 | 400  | 1825 | 150  | 950  | 225 |
| 2026.02 | 325  | —    | 125  | 650  | 225 |
| 2026.03 | 200  | 1225 | 125  | 750  | 150 |

Coverage：**63/75** cells（BNB 15/15、DOGE 15/15、ETH 13/15、SOL 13/15、BTC 7/15）。BTC 在 8/15 个月份 strict 下不过；ETH（2025.05、2025.08）与 SOL（2025.01、2025.02）各有 2 个月份不过。

### 3.4 Strict 结果的局限

- BTC 8/15 个月份不过；ETH、SOL 各 2 个月份不过。Asset coverage 在月度粒度下仍只有 63/75（84%）
- Selected $\ell$ 跨月份跳动剧烈（e.g., BNB 在能过的月份里 200–1025 之间；BTC 在能过的月份里 1225–1825 之间），regime-dependent
- 吞吐量 ~0.003 bits/s（selected $\ell \sim 1500$ 时），实用性边缘
- D(k=2) / Runs 在大多数 selected $\ell$ 上 pass-rate 贴 0，印证 §3.1 的 bid-ask bounce 机理（Price predictability 2024 §4.4 在 crypto 的再现）；per-asset / per-month 的 `runs_pass_rate` / `predictability_k2_pass_rate` 见 `all-offset-per-month(50,2000,25)/by_asset/<ASSET>/<ASSET>_summary_exp2_k_acceptance.csv`

→ Strict 在月度下 asset coverage 仍不完整，特别是 BTC；这是**不能被 Methodology 规避的结果**，需要方法学调整。

---

## 4. All-Offset Relaxed 阶段

### 4.1 导师建议

> "You technically want to have one random string even in all-offset scenario because the string are mutually correlated. Thus you may check if at least one string is random and passes your criteria."

### 4.2 判据

```
is_acceptable_relaxed =
    num_pass ≥ max(RELAXED_MIN_PASS_ABSOLUTE,
                   ceil(RELAXED_MIN_PASS_FRACTION × N_valid))
```

`num_pass` = 同时过 D + Monobit 的 valid offset 数（α = 0.01，**不校正**）。

- 使用参数：`(3, 0.03)` 和 `(5, 0.05)` 均跑过，结果类似；主分析用 `(3, 0.03)`
- 明确标注为 **heuristic**，不是正式 multiple-testing correction（"∃-pass" 规则无对称标准校正）
- 详见 [Exp2 Plan A - Relaxed Gate.md](Exp2%20Plan%20A%20-%20Relaxed%20Gate.md)

### 4.3 Selected $\ell$（relaxed, per-month, step 2）

数据：`data/processed/experiment2/relaxed-all-offset-per-month(3,0.03)-(10,2000,2)/selected_ell_by_window.txt`。
Per-asset $\ell$ 网格：BNB / DOGE / SOL = (10, 2000, 2)；ETH = (300, 2000, 2)；BTC = (700, 3000, 2)。

| Month | BNB | BTC  | DOGE | ETH  | SOL |
|---|---|---|---|---|---|
| 2025.01 | 244 | 1750 | 594  | 800  | 596 |
| 2025.02 | 286 | 1550 | 172  | 610  | 312 |
| 2025.03 | 180 | 1576 | 214  | 436  | 180 |
| 2025.04 | 176 | 1370 | 162  | 444  | 196 |
| 2025.05 | 198 | 1248 | 156  | 550  | 226 |
| 2025.06 | 146 | 924  | 72   | 400  | 104 |
| 2025.07 | 268 | 1376 | 220  | 576  | 298 |
| 2025.08 | 212 | 1314 | 214  | 1194 | 388 |
| 2025.09 | 256 | 900  | 238  | 698  | 270 |
| 2025.10 | 464 | 1150 | 124  | 714  | 164 |
| 2025.11 | 232 | 988  | 72   | 660  | 108 |
| 2025.12 | 206 | 870  | 48   | 470  | 98  |
| 2026.01 | 218 | 1030 | 66   | 556  | 110 |
| 2026.02 | 158 | 998  | 56   | 420  | 76  |
| 2026.03 | 128 | 880  | 48   | 442  | 66  |

### 4.4 Relaxed 阶段的主要 findings

1. **全覆盖**：5 asset × 15 month = 75/75 月份全部 selected（含 BTC、ETH 所有窗口）。对比 monthly strict 的 63/75（BTC 7/15、ETH 13/15、SOL 13/15），relaxed 把剩下 12 个未覆盖 cell 全部补齐
2. **吞吐量提升**：bits/s 从 strict 的 ~0.003 抬升到 ~0.02，约 **7×**
3. **Witness-offset k=2 / Runs 仍拒绝**：75/75 的 witness 在 D(k=2) 和 Runs 上 p ≪ α；这与 strict 下相同，说明这条 1 阶依赖**是 transaction-time 聚合轴的属性**（Price predictability 2024 §4.4 的 bid-ask bounce 机理），不是 relaxed gate 的问题。Paper Table 4 的 predictable-day k=2 p 值 = 0.0014 / 2.67e-10 / 0.044 在 SNAP/F/CCL 上一致呈现，Paper 明说 adaptive-k 会稀释 1 阶信号。本 thesis 在 crypto 上复现了这个 stylized fact。**后续 1-second bar 分析（§5 补充）显示该 1 阶结构在物理时间轴上可被破坏**——因此不是"源数据属性"，而是"transaction-time 轴属性"

### 4.5 Bonferroni / Šidák sensitivity（不采纳为主分析）

数据：`data/processed/experiment2/relaxed-all-offset-per-month-bonferroni-(10,2000,2)/selected_ell_by_window.txt`（仅跑 2025.01–03 三个月作为对照）。判据：保留 ∃-pass 规则，但 per-offset 阈值改为 $\alpha / N_\text{valid}$（Bonferroni）或 $1 - (1-\alpha)^{1/N_\text{valid}}$（Šidák）。$\ell$ 网格 step 2（BNB/DOGE/SOL: (10, 2000, 2)；ETH: (300, 2000, 2)；BTC: (700, 3000, 2)），与 §4.3 主分析共用同一网格分辨率，可直接比较。

| Month | BNB | BTC  | DOGE | ETH | SOL |
|---|---|---|---|---|---|
| 2025.01 | 218 | 1364 | 274  | 500 | 334 |
| 2025.02 | 190 | 1144 | 132  | 422 | 208 |
| 2025.03 | 156 | 1252 | 102  | 338 | 154 |

与 §4.3 同月对照（heuristic vs Bonferroni，同 step=2）：

| 2025.01 | BNB | BTC | DOGE | ETH | SOL |
|---|---|---|---|---|---|
| heuristic (3, 0.03) | 244 | 1750 | 594 | 800 | 596 |
| Bonferroni | 218 | 1364 | 274 | 500 | 334 |

Bonferroni 系统性给出**更小**的 selected $\ell$。理由是缩小 per-offset α 在 ∃-pass 规则下让单 offset **更容易**过线（$p \geq \alpha/N$ 比 $p \geq \alpha$ 严格更弱），与"防止偶然通过"的初衷方向相反。这是 Type-I-vs-Type-II 不匹配的实证表现，详细论证见 [Plan A §8.2](Exp2%20Plan%20A%20-%20Relaxed%20Gate.md#82-bonferroni--šidák-作为-sensitivity-mode)。**Šidák 在本 N 量级下数值与 Bonferroni 几乎一致**（$\alpha/N \approx 1 - (1-\alpha)^{1/N}$）。

---

## 5. 1-Second Bar（time-based aggregation）阶段

### 5.1 动机

Thesis Specification §5 明确要求在 "several time scales" 上做聚合；§3–§4 只覆盖 transaction-time 轴（trade-count），时间轴尚未做。另外 transaction-time 下 D(k=2) / Runs 在每个 witness 上 p ≪ α，独立性侧仍有空间。

### 5.2 数据管道

- `aggTrades → 1-second close-price bar`（空秒 forward-fill）`→ 交易符号 bit 流`
- ℓ 网格 = 10..700 step 2（ℓ 单位：秒）
- 仍是 all-offset 构造
- Gate 与 transaction-time 一致：≥80% offset 同时通过 D_adaptive 和 Monobit（α=0.01）
- 数据：5 个 USDT spot × 15 个月（2025.01–2026.03）
- 实现详见 [scripts/runner_exp2_all_offset_1sbars.py](scripts/runner_exp2_all_offset_1sbars.py)

### 5.3 三档 gate

| Gate | 判据 | 位置 | 通过窗口 |
|---|---|---|---|
| base | pred + mono | CSV 列 `is_acceptable` | **70/75** |
| +Runs | base AND runs ≥ 0.80 | CSV 列 `is_acceptable_with_runs` | 62/75 |
| +Runs+ApEn | base + runs AND apen ≥ 0.80 | post-processing 合成 | 62/75 |

Base gate 失败的 5 个窗口全部落在 seconds-with-trades coverage < 0.75 的月份（DOGE/ETH 2025.12、2026.02–03；BNB 2025.07）——属数据密度问题，不是 gate 问题。

### 5.4 Selected $\ell$（base gate, 单位：秒）

| Month | BNB | BTC | DOGE | ETH | SOL |
|---|---|---|---|---|---|
| 2025.01 | 148 |  54 |  32 |  58 |  32 |
| 2025.02 |  70 |  88 |  84 | 204 | 506 |
| 2025.03 |  70 |  70 |  36 | 414 |  42 |
| 2025.04 |  64 |  46 |  22 |  16 |  22 |
| 2025.05 | 332 |  76 |  92 | 566 | 200 |
| 2025.06 | 120 |  52 |  18 |  —  |  18 |
| 2025.07 |  —  | 114 |  48 | 110 | 322 |
| 2025.08 | 118 | 110 |  44 |  36 |  54 |
| 2025.09 | 254 |  80 |  64 |  74 |  70 |
| 2025.10 |  38 |  62 |  16 |  34 |  28 |
| 2025.11 |  26 |  26 |  22 |  50 |  10 |
| 2025.12 |  92 |  34 |  24 |  —  | 468 |
| 2026.01 |  76 |  50 |  16 |  36 |  20 |
| 2026.02 |  32 |  18 |  —  |  —  | 354 |
| 2026.03 | 216 | 250 | 196 | 334 | 356 |

$\ell$\* 量级 10²–10³ 秒（分钟级），对应 bits/s ≈ 10⁻³。

### 5.5 核心 finding：独立性在 1-second bar 轴上可被破坏

- Transaction-time（§3–§4）：D(k=2) / Runs 在所有窗口的所有 witness 上 p ≪ α
- 1-second bar：两个检验在 **62/75** 个窗口达到 pass-rate ≥ 0.80

这条对比**收紧** §3.1 / §4.4 / §6.2 中的 "bid-ask bounce 1 阶结构" 定位：

- 这条依赖**不是源数据的不可破坏属性**
- 它是 **transaction-time 聚合轴**的属性
- 物理时间轴在数据密度充足时可以打散它

失败的 13/75 个 +Runs 窗口与 base gate 失败相关联——都落在 coverage < 0.75 的月份，说明独立性的改善是**数据密度条件性**的，不是 1-second bar 的普适性质。

### 5.6 方法学含义

两条轴给论文两个互补 PRNG 规格：

- **transaction-time**：每 ℓ\_trades 个 tick 出 1 bit，吞吐随流动性变化
- **1-second bar**：每 ℓ\_sec 秒出 1 bit，吞吐与 trade 频率解耦（PRNG latency 友好）

下游按 "latency vs throughput" 偏好选。详见 [Exp2 Plan B - Time-Based Aggregation.md](Exp2%20Plan%20B%20-%20Time-Based%20Aggregation.md)。

---

## 6. 三重一致性：本实验在两篇 Reference 框架下的定位

### 6.1 Paper 内部：trades/s ↑ → 所需 $\ell$ ↑（Emergence of Randomness 2025 Case 2）

Price predictability 2024 / Emergence of Randomness 2025 的 9 支美股（2022-08 至 2022-11，6.5h 交易日）：

| Ticker | trades/s | Emergence of Randomness 2025 分档 |
|---|---|---|
| TSLA | 7.9  | N=1M（最难）|
| AAPL | 6.1  | N=500K |
| SPY  | 4.1  | N=1M |
| MSFT | 3.7  | N=500K |
| INTC | 1.7  | N=100K |
| SNAP | 0.74 | 低频 + bid-ask bounce |
| CCL  | 0.66 | 低频 + bid-ask bounce |
| F    | 0.55 | 低频 + bid-ask bounce |
| LLY  | 0.48 | 最低频 |

Paper 使用的 aggregation range：**Price predictability 2024: $a = 1\ldots50$**；**Emergence of Randomness 2025: $\ell = 1\ldots100$**。

Emergence of Randomness 2025 明确陈述：高交易活动资产收敛慢。AAPL/TSLA 在 $\ell=100$ 仍有许多检验失败；CCL/LLY 在小 $\ell$ 即收敛。

### 6.2 本 thesis 内部：同一规律

数据来源：§4.3 relaxed per-month step=2（覆盖 5 asset × 15 月）。

| Asset | 日均 trades/s（量级） | selected $\ell$ 范围（15 mo）| 2026.03 代表 |
|---|---|---|---|
| BTCUSDT | ~50–200 | 870–1750 | 880 |
| ETHUSDT | ~30–100 | 400–1194 | 442 |
| SOLUSDT | ~20–80  | 66–596   | 66  |
| BNBUSDT | ~5–30   | 128–464  | 128 |
| DOGEUSDT| ~5–30   | 48–594   | 48  |

**$\ell$ 排序 = trades/s 排序**（BTC > ETH > SOL ≈ BNB ≈ DOGE）。

### 6.3 跨市场外推

- crypto trades/s ≈ 股票的 10×（BTC ~100+ vs TSLA ~8）
- 所需 $\ell$ 也 ≈ 10×（Paper 的 ~100 → 本 thesis 的 ~1000 量级）

→ 本 thesis 的 **$\ell = 50\ldots2000$** 不是任意上限选择，而是 Price predictability 2024 §5.1 外推预测（"crypto 比 AAPL 更高频 → 需要比 50 更大的 $\ell$"）的兑现。

### 6.4 小结

Exp2 的实验结果在三个层面上与 Reference 一致：
1. 复现 Price predictability 2024 §4.4 的 SNAP/F/CCL bid-ask bounce（k=2 / Runs 残留）
2. 复现 Emergence of Randomness 2025 Case 2 的 trades/s vs $\ell$ 单调关系
3. crypto 到 $\ell \sim 2000$ 的外推兑现 Price predictability 2024 §5.1 的预判

注：上述跨市场一致性论证**限定在 transaction-time 聚合轴**。1-second bar 轴上每个 bar 的信息量随 trades/s 饱和，trades/s ↑ ⇒ $\ell_\text{sec}$ ↑ 的单调关系不直接转移（见 [Plan B §4.4](Exp2%20Plan%20B%20-%20Time-Based%20Aggregation.md#44)）。

---

## 7. Limitations（进论文 Limitations 章节）

1. **Offset 方法学上必须固定**。PRNG 部署不能事后挑最佳 offset；selected witness offset 仅作诊断用。
2. **D(k=2) / Runs 在 transaction-time 下残留 1 阶结构**。这条依赖是 transaction-time 聚合轴的属性（bid-ask bounce）；1-second bar 轴上在 62/75 窗口被打散（见 §5）。因此不是源数据的不可破坏属性，但 transaction-time 下若要 post-processing-free 的 PRNG，仍需加 debiasing（von Neumann 等）。
3. **跨 $\ell$ 的 multiple selection 未校正**。候选 $\ell$ 网格的 selection 维度未做 Bonferroni / FDR 校正；属已知 limitation。
4. **Relaxed gate 是 heuristic**，不是正式 multiple-testing correction；"∃-pass" 规则在标准理论中无对称校正。

---

## 8. 下一步

综合 [Thesis Specification](thesis_specification.md) §5（"Financial time series will be aggregated at **several time scales**"）和 [Initial Plan](notes/Initial%20Plan.txt) 的 Deliverable：

### 8.1 Exp2 内必做（Spec 义务）

- ~~**Time-based aggregation（1-second bars）**~~：**已完成**，见 §5。
- **Exp2 结稿**：将本 report 整合进 thesis Methodology + Results 章节；Limitations 章节吸收 §7；Discussion 章节引用 §6 三重一致性（cross-market replication）和 §5.5（时间轴破坏 1 阶依赖）作为两个正面贡献。

### 8.2 后续 Experiments（都要做）

顺序：**Exp3 → Exp4 → Password Generator**。理由：

- Exp4 的 narrative 是"融合加速"，必须先有 Exp3 的 per-asset baseline bits/day 作对照，才能量化 fusion 的 throughput 提升。Initial Plan 原文 "dual-asset fusion to **accelerate** bit-stream generation" 已隐含这一对比
- Exp4 的输入是 Exp3 在每个 (asset, month) 上选出的 (selected $\ell$, witness offset) bitstream，依赖关系是单向的
- KL independence 检验是成对做的，Exp3 的结果还能告诉 Exp4 "哪几个 asset 在哪些月份有可用的 selected $\ell$"，避免挑到某 asset 在某月没 $\ell$ 的无效配对
- Exp3 计算成本很低（bitstream 已在 Exp2 里生成，只需在 selected $\ell$ 上做一次汇总），不会挤压 Exp4 的时间

所以把 Exp3 做成**轻量章节**（只在 selected $\ell$ 上汇总 bits/day），Exp4 作为论文"RNG 产出"主章节。

- **Exp3（Entropy Production Rate）**：在每个 asset × month 的 selected $\ell$ 上，量化 bits/day 吞吐。Initial Plan Deliverable #2，bits/s ≈ 0.02 对应每天 ~1700 bits，约每月可产 1–2 个 256-bit 种子
- **Exp4 多资产融合**：Initial Plan 的 BTC+ETH（及扩展）KL independence 分析 + 多源拼接。目标是把单资产的 per-month bitstream 融合成更长、更独立的 entropy 流，回应 Spec §5 "independence of random number sequences" 评估维度
- **Password Generator prototype**：Spec §4 + Initial Plan Deliverable #3，基于 Exp3/Exp4 的 entropy bit 产出做一个最小可用脚本

### 8.3 加分项（时间允许则做）

- **选点 TestU01 Rabbit**：在 selected $\ell$ 的 witness bitstream 上做外部验证（单点跑，非 $\ell$ sweep）
- **Post-processing 层**：针对 §7.2 的 bid-ask bounce 残留，实现 von Neumann debiasing；重测 k=2 / Runs 是否能抬到 α 以上
- **NIST battery 补全**：按 Emergence of Randomness 2025 Table 4 补齐 Block Frequency、Cumulative Sums、Longest Run、DFT、Serial、Non-overlapping Template 6 个（substring-based）
- **Economic cost analysis**：Initial Plan Deliverable #4，可写成 Discussion 一节而非独立实验

### 8.4 时间评估

| 项 | 状态 | 估计工作量 |
|---|---|---|
| 1-second bar 主分析 | **已完成** | — |
| Exp2 thesis 写作（含 transaction + time-based 双线对比） | 进行中 | 1 周 |
| Exp3 entropy rate 分析 + 写作 | 下周起 | 1 周 |
| Exp4 多资产融合 + KL independence 分析 | 待排 | 1.5 周 |
| Password generator 最小 prototype | 待排 | 1 天 |
| 整合 + Discussion + Limitations | 待排 | 1 周 |
| TestU01 Rabbit 单点验证（加分） | 待排 | 0.5 天 |
| von Neumann extractor + 重测（加分） | 待排 | 2–3 天 |
| NIST battery 补 6 个（加分） | 待排 | 3 天 |
| **剩余必做合计** | — | **~4.5 周** |

符合导师"being on time is more important than details of the setup"的建议。

---

## 9. 当前结论

Experiment 2 已达到 Initial Plan 的核心目标（识别 $\ell$ 对随机性的影响），并在 Reference 框架下获得三条主要 findings：

1. **方法学可迁移**：Emergence of Randomness 2025 的 all-offset 检验框架在 crypto spot 市场可用，selected $\ell$ 在 transaction-time relaxed gate 下对所有 5 个 asset × 15 个月份全覆盖；在 1-second bar strict base gate 下覆盖 70/75
2. **Cross-market replication**：trades/s ↑ ⇒ 所需 $\ell$ ↑ 的 Emergence of Randomness 2025 Case 2 规律在 crypto 上再现；transaction-time 下 bid-ask bounce 导致的 k=2 残留在 crypto 上再现 Price predictability 2024 §4.4 的 SNAP/F/CCL 模式
3. **独立性可在时间轴被打散**（Plan B 新增 finding）：transaction-time 下 D(k=2) / Runs 在每个 witness 都 p ≪ α，1-second bar 下同样两个检验在 62/75 窗口达到 pass-rate ≥ 0.80。这把 Plan A 里"bid-ask bounce 是源数据属性"的表述收紧为"是 transaction-time 聚合轴的属性"；物理时间轴在数据密度充足时可破坏它

下一步以进入 Exp3（entropy rate）+ 论文写作为主，按 §8.4 时间表执行。
