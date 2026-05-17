# Progress Report — Experiment 2: Temporal Aggregation

**论文题目:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation
**学生:** Yujia Liu (yujia.liu.9362@student.uu.se)
**导师:** Andrey Shternshis
**Subject Reviewer:** Parosh Abdulla
**报告日期:** 2026-05-16
**状态:** 实验、数据、写作均已完成,对应论文 Ch 4 §4.3 + Appendix A.1–A.5。

---

## 1. 实验目标

回应 RQ1 的正向部分与 RQ2:在何种聚合层级 ℓ 上,加密货币 tick 序列开始通过标准随机性检验?在哪条聚合轴上通过得更稳健?目标是选出每个 (asset, month) cell 的 selected ℓ\* 与 witness offset,作为下游 Experiment 3 / 4 与 Password Generator Prototype 的输入配置。

## 2. 方法论摘要

**数据.** 与 Exp 1 共享同一规格:5 资产 × 15 月 = 75 个 (asset, month) cell。

**两条聚合轴.**

- **Transaction-time 轴(按成交笔数聚合):** 对每个聚合层级 ℓ 与起始 offset o,采样子序列 *q*ⱼ = *p*_{o + jℓ},取差分符号,drop-zero 后得 bitstream。
- **Physical-time 轴(按 UTC 整秒聚合,1-second bar):** 先把 `aggTrades` 按整秒分桶,空秒前向填充得 per-second close-price 序列,然后在该序列上执行与 transaction-time 相同的编码。ℓ 的单位由"笔数"变为"秒"。

**主统计量与全 offset 构造.** 沿用 Shternshis & Marmi (2025) 的熵驱动可预测性检验 *D*(adaptive *k* + fixed *k* = 2)以及 Onofri et al. (2025) 的"ℓ-samplings"全 offset 构造:对每个 ℓ 构造 ℓ 条 offset 比特流并独立检验,以通过率作为接受判据。Monobit、Runs、ApEn 作为辅助诊断。显著性水平 α = 0.01;`MIN_BIT_COUNT = 2000` 作为单条 offset 的最低长度门槛。

## 3. 决策链条与迭代历史

Experiment 2 经过四个阶段递进,每一阶段都直接回应前一阶段暴露的不足。每一步均与导师反复确认。

| 阶段 | 聚合轴 | 接受规则 | ℓ 网格 | 触发动机 |
|---|---|---|---|---|
| (1) Single offset | transaction-time | 固定 o = 0,*D*(adaptive) 与 Monobit 同时 *p* ≥ α | [50, 2000] step 25 | Exp 1 给出聚合必要;先定位 ℓ\* 量级 |
| (2) All-offset **strict gate** | transaction-time | 全 offset 构造,要求 ≥ 80% 同时通过 *D* 与 Monobit | [50, 2000] step 25 | Single offset 在 BTC 的 2 个月完全无解;无法量化 offset 稳健性 |
| (3) All-offset **relaxed gate** | transaction-time | heuristic 冗余判据 n_pass ≥ max(F, ⌈f · N_valid⌉),(F, f) = (3, 0.03) | [10, 2000] step 2 | Strict gate 在 BTC 8 月 + ETH 2 月 + SOL 2 月失败(12 cell 无解);粗网格限制 ℓ\* 估计精度 |
| (4) **1-second bars** | physical-time | 全 offset + 80% pass rate(*D* + Monobit) | [10, 600] step 1 | Transaction-time 所有 witness 上 *D*(*k* = 2) / Runs 普遍被拒,提示一阶残留可能为采样轴属性;且 transaction-time 吞吐随 trades/s 浮动,不易写为固定 SLA |

**两个关键迭代判断点.**

(i) **Relaxed gate 的 heuristic 性质.** 在导师建议"all-offset 实际只需要 1 条 offset 通过,但需要做多重检验校正"后,我先尝试 Bonferroni / Šidák,但发现方向相反:这两种校正控制的是"family 内 ≥ 1 条假拒绝 H₀"的 Type-I 错误;在我们关心的"∃-pass"判据下,收紧 α 会让每条 offset *更容易*通过,使族内"被错误接受为随机"的概率反而上升。我跑了 2025 Q1 三个月作为方向性对照(论文 Table A.4),Bonferroni 版本在所有 cell 上给出系统性更小的 selected ℓ\*,印证该方向判断。因此采用 heuristic max(F, ⌈f · N_valid⌉) 冗余判据,以"多 offset 冗余确认 + 高于 α 噪声地板"为指导原则取 (F, f) = (3, 0.03),并在论文中明确标注为 heuristic robustness check 而非形式校正。

(ii) **Physical-time 是关键独立性结果的来源.** 同口径 +Runs 对照下,transaction-time strict gate 覆盖率从 63/75 跌到 48/75(within-axis 损失 24%);physical-time base gate 从 70/75 仅跌到 62/75(损失 11%)。该不对称表明:transaction-time 下持续被拒的 *D*(*k* = 2) / Runs 残留更可能是采样轴属性,而非源数据固有属性。这一发现把先前 transaction-time 下的"持续 1 阶残留"重新框为"采样轴选择的代价",并直接决定 physical-time 作为后续实验的主部署口径。

## 4. 关键结果

### Table — Selected ℓ\* per-asset summary(跨 15 月汇总)

| Asset | Strict (笔数) n_pass / median ℓ\* | Relaxed (笔数) n_pass / median ℓ\* | 1-second bar base (秒) n_pass / median ℓ\* |
|---|---:|---:|---:|
| BTC  |  7/15 / 1500 | 15/15 / 1150 | 15/15 / 62 |
| ETH  | 13/15 /  975 | 15/15 /  556 | 12/15 / 65 |
| BNB  | 15/15 /  350 | 15/15 /  212 | 14/15 / 84 |
| SOL  | 13/15 /  350 | 15/15 /  180 | 15/15 / 54 |
| DOGE | 15/15 /  375 | 15/15 /  156 | 14/15 / 33 |

完整 per-(asset, month) 表见论文 Appendix Tables A.1–A.5(含 +Runs 与 +Runs+ApEn 对照);Bonferroni 方向性对照见 Table A.4。

### 主要发现

1. **跨资产排序稳定:BTC > ETH ≫ BNB / SOL / DOGE.** 三档 gate 下粗粒度结构一致;BTC 与 ETH 与其余三者之间存在大幅 gap,而 BNB / SOL / DOGE 之间不严格单调。该方向与 Onofri et al. (2025) Case 2 在 8 只美股 + 1 ETF 上报告的"trades/s 越高、所需 ℓ\* 越大"为同向关系,在加密货币市场上构成跨市场复现。
2. **Relaxed gate 把覆盖率从 strict 的 63/75 推到 75/75.** Strict gate 在 BTC 8 月、ETH 2 月、SOL 2 月共 12 cell 失败;relaxed gate 全部找到 acceptable ℓ\* ∈ [48, 1750]。Selected ℓ\* 整体压低 23%(BTC)–58%(DOGE),per-cell bit rate 从约 0.012 bps 提升到 0.021 bps(约 1.8×)。
3. **Physical-time 轴在 62/75 cell 上消化一阶残留.** Transaction-time 下,所有 witness 的 *D*(*k* = 2) / Runs 几乎一律被拒;切换到 1-second bar 后,这两项在 62/75 cell 达到 ≥ 0.80 通过率。Base gate 失败的 5 cell 全部落在 seconds-with-trades coverage < 0.75 的月份(DOGE/ETH 2025.12、2026.02–03;BNB 2025.07),属数据密度条件性,而非 gate 设计问题。
4. **吞吐量量级 10⁻² bps.** Transaction-time strict ≈ 0.012 bps,relaxed ≈ 0.021 bps;1-second bar base 落在 0.01–0.03 bps 区间。Selected ℓ\* 对应 wall-clock latency 在分钟级,符合面向密码生成的合理 latency 上界(论文 §3.5 规定 ℓ 上限 600 秒 = 10 分钟)。

## 5. 方法学含义 / 对后续实验的锚点

(i) **Physical-time 作为主聚合轴.** Transaction-time 吞吐随 trades/s 浮动,适合作为统计构造和补充对照;physical-time 的 1/ℓ\* 直接对应 wall-clock sampling schedule 与 per-bit latency,适合作为后续 PRNG 部署口径。

(ii) **Transaction-time relaxed gate 作为 fallback.** 它证明笔数轴上可以通过 heuristic offset 冗余得到完整 acceptable cell,可作为 physical-time base 失败 cell 的潜在 fallback;具体是否在 Experiment 3 中投入,留待 §4.4 给出。

(iii) **后续 cross-battery 验证应在 selected ℓ\* 上做.** Per-offset bitstream 长度通常不足以支撑 TestU01 Alphabit / Rabbit 的 sanity check 适用范围;Experiment 3 / 4 在 selected ℓ\* 上做跨月 / 跨资产拼接,使长度满足 Onofri (2025) Table 3 适用范围后,启用 Alphabit / Rabbit。

## 6. Limitations(已并入论文 §5.2)

1. **Offset 方法学上必须固定.** PRNG 部署不能事后挑最佳 offset;selected witness offset 仅作诊断。
2. **Transaction-time 残留 1 阶结构.** *D*(*k* = 2) / Runs 在该轴下持续被拒;1-second bar 在 62/75 cell 上消化此残留,但若选用 transaction-time 构造 PRNG 且对一阶相关性敏感,需附加 von Neumann 等 debiasing。
3. **跨 ℓ multiple selection 未做形式校正.** 该限制 strict 与 relaxed 共有。
4. **Relaxed gate (F, f) = (3, 0.03) 是 design choice.** 未做 (F, f) 敏感性扫描;形式多重检验校正在"∃-pass"方向无对称解。
5. **边缘样本长度.** 月度 offset 比特流 *n* ∈ [2 × 10³, ~10⁴],处在 Shternshis & Marmi (2025) Appendix A Q-Q 仿真的边缘区间;p 值精度比 *n* ≥ 10⁴ 时差,临界附近的判定需谨慎。

## 7. 产出物

- `scripts/runner_exp2_single_offset.py` / `runner_exp2_all_offset.py` / `runner_exp2_all_offset_relaxed.py` / `runner_exp2_all_offset_1sbars.py` — 四阶段 runner
- `data/processed/experiment2/single-offset-per-month(50,2000,25)/` — 阶段 (1) 完整 15 月 selected ℓ\*
- `data/processed/experiment2/all-offset-per-month(50,2000,25)/` — 阶段 (2) strict gate
- `data/processed/experiment2/relaxed-all-offset-per-month(3,0.03)-(10,2000,2)/` — 阶段 (3) relaxed gate(主分析)
- `data/processed/experiment2/relaxed-all-offset-per-month-bonferroni-(10,2000,2)/` — Bonferroni 方向性对照
- `data/processed/experiment2/1sbars-all-offset-per-month(10,600,1)/` — 阶段 (4) 1-second bar
- 论文 Tables A.1–A.5、Figures 4.2–4.5 均由上述 CSV / runner 输出生成。
