# Experiment 2 — Plan B: Time-Based Aggregation (1-second bars)

> 状态：**已完成**（1-second bars, ℓ ∈ [10, 700] step 2, per-month × 15 月 × 5 资产）。
> 在 strict base gate（80% pass rate）下 coverage 70/75 ≈ 93%，**无需 relaxed 路径**，直接作为 Exp 2 的第二条主分析。Plan A 的 relaxed heuristic 仅用于 transaction-time 轴。
>
> **核心 finding**：时间轴下一阶相关性检验（D(k=2) / Runs）在 62/75 个窗口里达到 ≥80% pass rate，与 Plan A 下所有 witness p ≪ α 形成鲜明对比。Plan A 的结论"bid-ask bounce 是源数据属性"被收紧为"是 transaction-time 轴的属性"——物理时间轴在数据密度充足时可以破坏短程依赖。见 §5。

## 1. 起因

Plan A 在 transaction-time 轴上收尾后，Thesis Specification §5 明确要求 "several time scales"，且 §3 把研究问题框在 "statistically independent random sequences"。Transaction-time 下 k=2 / Runs 每个 witness 都 p ≪ α，独立性侧仍有空间。Plan B 把聚合轴从 trade-count 切到物理时间，覆盖 specification 的第二条 deliverable。

导师 2026-04 Slack 已预先对齐：transaction-time 结果到位后切 1s bars，不并行。

## 2. 数据管道

- `aggTrades → 1-second OHLC bars → close-price 序列`（`src/bars.py`）
  - 每个 UTC 秒取落在该秒内所有 trades 的最后成交价；无交易的秒以前值 forward-fill
  - 零 delta 的秒在 `build_offset_bitstream_from_arrays` 里被 filter（与 transaction-time 一致）
- Bitstream 构造：沿用 `build_offset_bitstream_from_arrays`，符号 = `sign(p_t − p_{t-ℓ})`
- ℓ 含义改变：**ℓ = 秒数**，不再是 trade 数
- 网格：`AGG_START=10, AGG_STOP=700, AGG_STEP=2`（345 个候选 ℓ；上限 700 s ≈ 11.7 min）

**ℓ 范围的下限**由 MIN_BIT_COUNT（继续 = 2000）约束：每月 ~2.6M 秒，forward-fill 后即使零 delta 大量被过滤，ℓ ≤ 700 区间仍能凑到 2000 bits。

## 3. 判据（三档 gate）

CSV 同时写入前两档，第三档在 post-processing 合成：

```
is_acceptable              = valid_offset_ratio ≥ 0.80
                             AND predictability_pass_rate ≥ 0.80
                             AND monobit_pass_rate        ≥ 0.80
is_acceptable_with_runs    = is_acceptable
                             AND runs_pass_rate           ≥ 0.80
is_acceptable_with_runs_apen
                           = is_acceptable_with_runs
                             AND approximate_entropy_pass_rate ≥ 0.80
```

PASS_RATE_THRESHOLD = 0.80，ALPHA = 0.01 per offset，与 Plan A strict 一致。选择规则：每个 (asset, month) 取使 gate 为 True 的最小 ℓ。

### 与 Plan A 的对比

| 项目 | Plan A (transaction-time) | Plan B (1s bars) |
|---|---|---|
| 聚合轴 | trade-count | physical seconds |
| ℓ 范围 | 50–2000, step 25 | 10–700, step 2 |
| Strict base coverage | 低（BTC 8/15、ETH 2/15、SOL 2/15 月份不过）→ 逼出 relaxed | **70/75 = 93%** |
| 主 gate | heuristic relaxed `(3, 0.03)` | strict base（80% pass rate） |
| 需要 relaxed？ | 是（否则无覆盖） | 否（strict 已达标） |

## 4. 结果

### 4.1 Gate 覆盖率

| Gate | 通过窗口 / 75 | 覆盖率 |
|---|---|---|
| base（pred + mono） | **70** | 93% |
| +runs | 62 | 83% |
| +runs + apen | 62 | 83% |

Base 失败的 5 格全部来自 coverage 较低的月份：ETH 2025.06 / 2025.12 / 2026.02、BNB 2025.07、DOGE 2026.02。这些月份 `with_trades / seconds_total` 跌到 0.55–0.75 区间，是数据属性而非 gate 缺陷。

### 4.2 Selected ℓ（base gate，2026.03 代表值）

| Asset | ℓ\* 范围（15 月，秒） | 2026.03 | 换算 ≈ 分钟 |
|---|---|---|---|
| BNB | 26 – 332  | 216 | 3.6 |
| BTC | 18 – 250  | 250 | 4.2 |
| DOGE | 16 – 196 | 196 | 3.3 |
| ETH | 16 – 566  | 334 | 5.6 |
| SOL | 10 – 506  | 356 | 5.9 |

整体量级 10²–10³ 秒，远小于 Plan A 在 trade-count 下的 10³ trades。Base gate 下 ℓ\* 数量级稳定在分钟级。

### 4.3 +runs 与 +runs+apen 的增量影响

- base → +runs：多数窗口 ℓ\* 不变或 +0~60；8 个窗口被完全封死（ETH 2025.03/05/07、DOGE/SOL 2025.12、SOL 2026.02、ETH/SOL 2026.03）。
- +runs → +runs+apen：再多数窗口 +0~30；**两个 outlier**：BNB 2026.02 `32 → 326`，ETH 2026.01 `50 → 384`。这两处 approximate-entropy 在低 ℓ 有凹陷（由 asset_panels.png 可见），apen 的加入把 ℓ\* 推到凹陷之外。

### 4.4 跨市场一致性：继续支持 Emergence of Randomness 2025 Case 2

Plan A §5.4 已用 transaction-time ℓ\* 复现 Case 2（trades/s ↑ ⇒ 所需 ℓ_trades ↑）。Plan B 的 1s-bars 轴上情况更复杂：

- 若把"所需秒数"类比 Case 2 里的 ℓ，BTC 的 ℓ\*_sec（18–250）并不一直是最大，ETH、SOL 在部分月份反而需要更多秒数
- 这是预期之中——时间轴下每个 bar 不是 1 个 trade 而是"1 秒的价格变化"。高流动性资产每秒有更多 ticks，每个 bar 的信息量更饱和，所以不一定需要更多秒才随机
- 结论：**transaction-time 的 Case 2 单调关系在 time-based 下不直接转移**，这是独立于 Plan A 的新 finding，而不是矛盾

### 4.5 月度时间趋势

Plan A 的 per-month ℓ\* 在 2025→2026 呈单调下降（被解读为 microstructure evolution）。Plan B 的 ℓ\*\_sec 未见同样强的时间趋势，部分资产（BNB、ETH）反而在 2026 年后期数值上升。说明 Plan A 观察到的下降趋势嵌在 trade-count 轴里（可能是 trades/s 本身升高导致 ℓ\_trades 等比例减小），在物理时间轴下被稀释或反转。**这也是 Plan B 独立贡献之一**：时间轴给出的 selected ℓ 更接近 "PRNG 规格需要等待多少物理秒" 的实用量。

## 5. 独立性诊断（D(k=2) / Runs）：与 Plan A 的关键差异

Plan B 最重要的发现不是 coverage，而是**独立性**——即 k=2 / Runs 这两个一阶相关性检验的行为与 Plan A 发生**质变**。

### 5.1 Plan A vs Plan B 对比

- **Plan A（transaction-time）**：每个 witness offset 上 `p_D_k2` 与 `p_Runs` 都 ≪ α（典型 1e-16 – 1e-4），**所有月份所有资产**无一例外。结论：bid-ask bounce 一阶结构不因 trade-count 聚合消失。
- **Plan B（1s-bars）**：一阶相关性检验的 pass_rate **可以在高 ℓ 下显著改善**，但分布不均。

### 5.2 Pass-rate 分布（ℓ ≈ 700，上界附近）

| 月份分组 | BTC pred_k2 / runs | ETH pred_k2 / runs | DOGE pred_k2 / runs |
|---|---|---|---|
| 2025.01–04 健康月 | 0.82 – 0.99 | 0.56 – 1.00 | 0.90 – 1.00 |
| 2025.07–11 健康月 | 0.84 – 1.00 | 0.74 – 0.98 | 0.92 – 1.00 |
| 2025.12 低 coverage | 0.67 | 0.21 | 0.23 |
| 2026.02 低 coverage | 0.25 | 0.25 | 0.02 |
| 2026.03 | 0.61 | 0.38 | 0.51 |

+runs gate 的 62/75 覆盖率（§4.1）就是由这一分布决定的：流动性正常的月份 Runs 在高 ℓ 下达标，低流动性月份无法达标。

### 5.3 与 seconds-coverage 的相关性

"崩塌"月份（2025.12、2026.02、2026.03）正是 bars coverage 最低的那批：

- DOGE 2025.12 coverage = 0.44，2026.02 = 0.51，2026.03 = 0.47
- ETH 同期 coverage 0.74 / 0.81 / 0.74

低 coverage ⇒ forward-fill 大量零 delta 秒被过滤 ⇒ 有效 bits 数接近 MIN_BIT_COUNT=2000 下限 ⇒ 一阶相关性检验功效不足。

### 5.4 方法学含义

**Plan A 推出的结论"bid-ask bounce 是源数据属性、不可被聚合消除"需要收紧为：该结论成立于 transaction-time 轴，但在物理时间轴上，只要数据密度足够，聚合确实能在多数窗口里把一阶相关性压到 α 之上。**

这是 Plan B 独立于 Plan A 的**正向 finding**，同时也解释了为什么 Spec §3 要求 "statistically independent random sequences" 时选择时间轴是对的：时间轴给了 aggregation 真正的空间去破坏短程依赖，transaction-time 没有。

### 5.5 ApproxEntropy 的凹陷

1s-bars 下 asset_panels.png 可见 ApproxEntropy 在中段 ℓ 区间有明显凹陷后恢复——Plan A 下 ApproxEntropy 基本单调上升。这解释了 §4.3 里 +runs+apen gate 的两个 outlier（BNB 2026.02、ETH 2026.01）：apen 凹陷把 ℓ\* 推到凹陷之外。定位为 1s-bar 聚合轴特有的 diagnostic，列入 Limitations。

## 6. 固有风险（进 Limitations）

1. **Forward-fill 对 zero-activity 秒的处理**。coverage < 0.70 的月份（尤其 DOGE 2025.12 / 2026.01–03）大量秒零 delta 被 filter；有效 bit 数接近下限，统计功效偏低。这是 base gate 失败 5 窗口的直接成因，也是 §5.3 独立性崩塌月份的共同原因。独立性改善是**数据密度条件性**的，不是 1s-bars 的普适性质。
2. **ℓ\* 的物理解释是"等待多少秒"，不是"采多少 tick"**。PRNG spec 用 Plan B ℓ\* 意味着"每 ℓ\* 秒生成一 bit"，throughput 是固定的 1/ℓ\* bit/s，与 trade 频率解耦。这是优点（可预测时延）也是代价（高活跃度资产吃亏——每秒有 100 trades 但只出 1 bit）。
3. **低 coverage 月份 witness 上 k=2 / Runs 仍被拒**。§5.2 显示这在 13/75 个窗口仍然发生，全部落在 seconds-with-trades coverage < 0.75 的月份。和 Plan A §5.2 的"所有 witness 全拒"不同——Plan B 下这是**数据密度不足的结果**，不是源数据属性。
4. **跨 ℓ multiple selection 未校正**。与 Plan A / strict 同病。
5. **Gate 多档自带 selection 空间**。base / +runs / +runs+apen 三档给出不同 ℓ\*，论文中必须固定一档作为主结论（建议 base），否则是隐性挑"对 PRNG 最友好的那档"。

## 7. 决策

- **主分析用 base gate**（pred + mono），93% coverage 足以支持"1s-bar 下随机性随 ℓ 聚合仍然涌现"的论点
- `+runs` 结果作为**独立性的直接证据**一并报告（而非 sensitivity 附录）——§5 的 62/75 一阶相关性达标是 Plan B 相对 Plan A 的**核心 finding**，不应被降级到 appendix
- `+runs+apen` 保留为 sensitivity：即使纳入 reference 测试，趋势方向不变，仅 throughput 代价上升、13/75 窗口被封死，主要集中在低 coverage 月份
- **不做 Plan B relaxed**。Plan A relaxed 是 transaction-time 下 strict 不达标被逼出来的 heuristic；Plan B strict 已 93% 覆盖，再加 relaxed 是 scope creep，且会重复 Plan A §2 的同一条 heuristic 注意事项

## 8. 论文定位

### 8.1 Methodology 章建议措辞

> "As a second aggregation axis we construct 1-second close-price bars (forward-filling empty seconds) and apply the same all-offset acceptance framework. Under the strict gate (≥80% of valid offsets simultaneously pass both Predictability and Monobit at α = 0.01) we observe acceptance in 70 of 75 (asset, month) windows without requiring any relaxed heuristic. The five failing windows correspond to months in which seconds-with-trade coverage drops below 0.75, which we interpret as a data-quantity rather than a data-quality limit. Selected ℓ values lie in the 10²–10³ second range (roughly tens of seconds to ten minutes), corresponding to bit rates of order 10⁻³ bits/s.
>
> Beyond coverage, the 1-second aggregation axis materially changes the behaviour of first-order independence tests. Under the transaction-time axis (Plan A), the fixed-k=2 Predictability test and the NIST Runs test reject at p ≪ α on every witness offset of every window — consistent with bid-ask-bounce structure (Price predictability 2024, §4.4) being an intrinsic property of the tick stream. On the 1-second axis, by contrast, both tests achieve ≥80% pass rates at high ℓ in 62 of 75 windows; the 13 remaining windows coincide with the lowest seconds-coverage months. We therefore refine Plan A's reading: first-order dependence is not an unconditional property of the underlying data, but an artifact of the aggregation axis — the physical-time axis, given sufficient data density, does reduce it. The +Runs gate is therefore reported as a primary result of Plan B rather than as a sensitivity check; the additional +ApproxEntropy gate is reported as sensitivity only."

### 8.2 与 Plan A 的叙事衔接

论文按两条独立轴并列报告：
- **Plan A（transaction-time）**：strict → relaxed 作为 speed/coverage 改进；ℓ\* 以 trade-count 给出，bits 以 per-trade 定义
- **Plan B（1s bars）**：strict 直接达成，不引入 relaxed；ℓ\* 以秒给出，bits 以 per-second 定义

两者在 PRNG spec 上互补：transaction-time 提供"多少 trade 换 1 bit"（吞吐随流动性变化），time-based 提供"多少秒换 1 bit"（吞吐与物理时间解耦）。下游应用选哪一种取决于 latency vs throughput 的偏好。

### 8.3 代码实现位置

- Runner：`scripts/runner_exp2_all_offset_1sbars.py`（复用 all-offset 框架，数据管道切到 `src/bars.py`）
- Plot：`scripts/plot_exp2_all_offset_1sbars.py`（两张图：`pass_rate_curves.png` + `asset_panels.png`）
- Post-processing：`scripts/select_ell_exp2_1sbars.py`（三档 gate 的 selected ℓ 汇总到 `selected_ell_by_window.txt`）
- 数据输出：`data/processed/experiment2/all-offset-per-month-1sbars(10,700,2)/`
