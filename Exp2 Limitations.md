# 实验 2：时间聚合

## 统计解释注意事项

在解释 `p-value` 随 aggregation level `\ell` 变化的曲线时，必须明确指出一个重要歧义。

随着 `\ell` 增大，生成的 bitstream 往往会变短。因此，`p-value` 上升可能来自两种完全不同的原因：

1. 时间聚合后的序列确实更接近随机。
2. 有效样本长度下降，导致统计检验功效下降，更不容易拒绝原假设。

这个问题在 `single-offset` 图中尤其明显。否则读者很容易把 `p-value` 上升直接理解为“随机性显著改善”。  
对于 entropy-based predictability test，还多一层复杂性：当 `\ell` 变化时，有效样本长度也在变化，因此自适应内部 block length `k` 也会随之变化。

## 实际含义

- 不能把 `p-value` 曲线单独当作随机性提升的直接证据。
- 在论文正文中，需要把这一点明确写成 `p-value` 解释上的限制。
- 如果后续需要做轻量级 robustness check，可以同时查看检验统计量本身，例如 `monobit_z`、`runs_z`，用来区分“效应本身变弱”和“检验功效下降”这两种来源。

## Adaptive k 随 `\ell` 变化导致的横轴不可比问题

对于 entropy-based predictability test，目前采用的是自适应 block length：

- `k = floor(0.5 * log2(n))`
- `history_length = k - 1`

这意味着随着 aggregation level `\ell` 增大，bitstream 长度 `n` 下降时，predictability test 内部使用的 `k` 也会发生跳变。

因此，`Predictability vs \ell` 这条曲线并不是“同一个固定阶数检验”在不同 `\ell` 下的严格可比结果，而是：

- `\ell` 在变化；
- 有效样本长度 `n` 在变化；
- 检验内部的 `k` / `history_length` 也在变化。

这会带来一个具体风险：曲线上的某些“陡降”或“拐点”，不一定完全来自随机性提升，也可能部分来自内部 block length 下降、自由度变化以及检验功效变化。

因此需要在论文中明确写出：

- `single-offset` 的 predictability 曲线应被理解为一种遵循文献设定的诊断性趋势图；
- 不能把它当成固定阶数条件下的严格可比曲线；
- 正式的选择结论应更多依赖 `all-offset` 的 pass-rate / selected-`\ell` 结果，而不是单条 `single-offset` predictability 曲线的拐点位置。

为缓解此问题，`summarize_bits_full` 同时输出 adaptive-$k$ 的 `predictability_pvalue` 与固定 $k=2$ 的 `predictability_k2_pvalue`，后者对应 Price predictability 2024 §4.4 "pairs of signs" 检验，用于跨 $\ell$ 的严格可比诊断。两条曲线在 plot 中并列显示。

## Approximate Entropy 的 block size（已由 m=5 取代 m=2）

采用默认 `block_size = 5`，对齐 Emergence of Randomness 2025 Table 4 的 NIST STS 参数设置。当前样本长度（`MIN_BIT_COUNT = 2000` 起步，大多数 `\ell` 下远高于 $2^{m+2}=128$ 的最低要求），固定 `m = 5` 是可行且更信息量更大的选择；早期版本曾用 `m = 2`，对高阶重复结构不敏感。

如果后续希望再做 robustness，更合理的增强是**多个 `m` 值的稳定性对照**（例如 `m \in \{3, 5, 7\}`），而不是单一 `m`。

## 多重比较未校正的问题

当前 Experiment 2 会同时跨多个维度重复进行假设检验，例如：

- 多个资产；
- 多个 aggregation level `\ell`；
- 多个统计检验；
- 多个 period。

在这种设置下，如果仅根据“某一个单独 `p-value` 首次超过阈值”的时刻来下结论，就会面临明显的多重比较风险。即使真实序列完全随机，也可能因为重复检验次数很多而出现一部分偶然的“首次通过点”。

这意味着：

- 某条曲线在某个 `\ell` 首次超过 `0.01`，不应被直接解释为稳健的随机性转折点；
- 特别是在 `single-offset` 情形下，某个 `\ell` 通过、下一个 `\ell` 又失败，很可能只是统计波动；
- 因此，`single-offset` 图中的 crossing point 更适合被理解为经验上的过渡区间，而不是严格显著的“临界点”。

当前框架对这一问题的缓解方式，不是做正式的多重比较校正，而是：

- 不把单个 `p-value` crossing 当成主要结论；
- 更依赖 `all-offset` 下的 pass-rate 规则；
- 要求大量 offsets 同时通过，而不是个别 offsets 偶然通过；
- 结合多个检验共同判断，而不是依赖单一检验。

因此目前的立场是：

- 需要在论文中明确承认多重比较风险；
- 但当前不优先引入 Bonferroni / Holm / FDR 等正式校正作为主分析框架；
- 正式结论应建立在 `all-offset` 的稳定性判据上，而不是 `single-offset` 某条曲线的第一次过线；
- 如果后续时间允许，可把多重比较校正作为 supplementary robustness analysis，而不是 thesis 主体的核心步骤。

## Acceptance gate 的修订：Runs 降为 reference，加入 D(k=2) 诊断

### 原 gate vs 新 gate

| 版本 | `is_acceptable` 条件 |
|---|---|
| 旧 | `valid_offset_ratio ≥ 0.80` AND `predictability_pass_rate ≥ 0.80` AND `monobit_pass_rate ≥ 0.80` AND **`runs_pass_rate ≥ 0.80`** |
| 新 | `valid_offset_ratio ≥ 0.80` AND `predictability_pass_rate ≥ 0.80` AND `monobit_pass_rate ≥ 0.80` |

Runs 的 `pass_rate` 仍然计算并写入 CSV，只是不再进入 `is_acceptable` 的 AND。D(k=2) 的 `pass_rate` 同样输出但不进 gate。

### 修订理由：Runs 与 adaptive-$k$ D 的系统性分歧

跨 6 个 period × 5 个资产的 all-offset 实验中出现一个稳定模式：

- `predictability_pass_rate`（adaptive $k \approx 6$–$7$） 常在大 $\ell$ 下达到 >0.90
- `runs_pass_rate` 在同一 $\ell$ 下常 <0.30（BTC 常为 0）
- 同一份 bitstream、同一批 offsets

机理（Price predictability 2024 §4.4 的加密货币再现）：

- Runs 本质上是**一阶马尔可夫依赖检验**（相邻两位的转移概率），DOF=1，信号集中
- Adaptive-$k$ 的 $D$ 把同样的一阶信号**摊到 $2^{k-1} \approx 64$ 个 context** 上（DOF=63），每个 context 只有 ~400 个观测，$\chi^2$ 被稀释
- 结果：存在一阶结构（典型如 bid-ask bounce 式的符号交替）时，Runs 直接捕获，adaptive-$k$ D 看不见

这正是 Paper §4.4 为 SNAP / F / CCL 三个低价股单独跑 $k=2$ 诊断的原因。他们观察到 $\hat p(00)+\hat p(11) < 0.5$（预测日符号反转过强），在我们高 $\ell$ 的 crypto 数据里预期有同类现象。

### 新增诊断：D(k=2)

按 Paper §4.4 直接复用，不是 ad-hoc：

- `summarize_bits_full` 输出 `predictability_k2_pvalue`、`predictability_k2_g_stat`、`predictability_k2_mutual_information_bits`
- All-offset runner 输出 `predictability_k2_pass_rate`
- 两个 plot 脚本加了 D(k=2) 面板

D(k=2) 与 Runs 的 pass-rate 预期高度相关（两者都测一阶，只是统计形式不同）。这种一致性**反向证明 Runs 的拒绝不是 bug 而是真实结构**，方法学上为"把 Runs 降为 reference 但不删除"提供了支撑。

### 后续 1-second bar 分析的收紧

上述"Runs / D(k=2) 在 crypto 上持续拒绝"的结论最初被解读为**源数据的 1 阶依赖属性**。1-second bar（time-based aggregation）分析显示，该 1 阶依赖在 62/75 个 (asset, month) 窗口下被 1s-bar 聚合打散（两个检验 pass-rate ≥ 0.80）。因此该结论需要**收紧**为：

> bid-ask bounce 导致的 1 阶依赖是 **transaction-time 聚合轴**的属性，不是 **源数据**的不可破坏属性；物理时间轴（1-second bar）在数据密度充足时可以打散它。

详见 `Exp2 Plan B - Time-Based Aggregation.md` §5。论文里本节的 Runs-降级论证仍有效（只针对 transaction-time 轴），但 Limitations / Discussion 里应补上轴相关性的说明。

### 论文写作要点

- Methodology：transaction-time acceptance gate 用 adaptive-$k$ $D$ + Monobit（Paper 推崇 $D$ 作为主统计量）
- Results：报告所有 5 个 test 的 pass-rate 曲线，Runs 和 D(k=2) 在 transaction-time 下标注为 reference；1-second bar 下 +Runs 作为主结果（见 Plan B §5）
- Discussion：用 D(k=2) ≈ Runs 的经验一致性解释 transaction-time 下 adaptive-$k$ D 的盲区，引 Paper §4.4 为方法学依据；**1-second bar 下独立性改善**作为本 thesis 相对 Reference 的方法学贡献
- Limitations：transaction-time 下的 Runs gate 修订**放宽**了 1 阶结构的通过门槛；如果下游应用（PRNG）选 transaction-time 轴且对 1 阶相关性敏感，需要额外 post-processing；1-second bar 轴本身把这类下游需求内化了一部分

### 关于 Runs NIST 前置条件（保留说明）

严格 NIST 实现应先检查 `|p1 - 0.5| < 2 / sqrt(n)`。当前未显式执行这一步。由于 Runs 已不在 gate 内，这一规范性差距对主结论影响为零；但方法说明中仍应承认实现不完全按 NIST 前置流程，以保持准确性。

## 不继续盲目扩展 aggregation level 上界

对于最难的资产（尤其是 BTC），当前结果可能显示在 `\ell <= 2000` 的范围内，某些检验（特别是 Runs / Approximate Entropy）仍未完全达到理想通过状态。一个直接反应是继续把 aggregation level 上界扩展到 `5000` 甚至更高。

但当前 thesis 的目标不是“把所有检验都推到通过”，而是：

1. 证明随机性会随着时间聚合逐步涌现；
2. 在随机性改善与 entropy throughput 保留之间，选择一个合理的 aggregation level。

因此需要明确：

- 更大的 `\ell` 确实可能进一步改善随机性指标；
- 但与此同时，`bits_per_second` 会持续下降，实用性会明显恶化；
- 如果某个资产只有在极大的 `\ell` 下才接近满足全部检验，这本身也是一个有意义的研究结果：说明该资产更难被时间聚合“打散”，并且达到更强随机性需要付出更高的吞吐量代价。

所以当前不将“继续把上界推高直到某资产通过”为默认策略，原因是：

- 这会让分析目标从“寻找合理值”滑向“寻找最大可通过值”；
- 可能得到统计上更漂亮、但工程上几乎不可用的结果；
- 也会削弱 thesis 中关于 trade-off 的核心论点。

当前立场：

- `single-offset` 结果只需支持“随着 `\ell` 增大，随机性总体上呈改善趋势”这一现象；
- 最终选择应基于 `all-offset` 的稳定性与 bit rate 共同判断；
- 不为 BTC 或其他 hardest case 默认把全局 grid 一路扩展到非常大的 `\ell`；
- 如果后续确实需要确认极端高 `\ell` 的远端行为，更适合做成某个资产的补充性 exploratory run，而不是主分析配置。

## 当前决定

- 现在不围绕这个问题重构 Experiment 2 的主分析框架。
- 先把这点作为论文中的显式解释风险保留下来。
- 当前优先级仍然是 `all-offset` 的 acceptance logic，以及最终 selected-`\ell` 结果的整理与表达。

## Relaxed all-offset gate（Plan A，启发式补充；已完成）

按导师 Slack（2026-04）建议补充的 relaxed 路径：判据为 `num_pass ≥ max(F, ceil(f × N_valid))`，α=0.01 per offset 不校正。实际跑过 `(F, f) = (3, 0.03)` 与 `(5, 0.05)`，主分析版本是 **per-month (3, 0.03)**，5 asset × 15 月全覆盖（75/75）。**设计理由、评估、下一步、固有局限**详见独立文档：`Exp2 Plan A - Relaxed Gate.md`。

要点：

- 明确是 **heuristic robustness check**，不是正式多重校正（"∃ pass" 在标准理论中无对称校正，任何硬套公式都经不起推敲；Bonferroni/Šidák 实证测试了仍不采纳，方向问题见 Plan A doc §2）
- strict (80%) 仍为主 gate，relaxed 作 asset coverage 的补充证据
- PRNG 实用上 offset 必须固定，不能事后挑；selected offset 上 D(k=2)/Runs 通常仍 ≪ α，作为 Price predictability 2024 §4.4 SNAP/F/CCL bid-ask bounce 的 crypto replication 报告

## Time-based aggregation（1-second bars，已完成）

Plan A 只覆盖 transaction-time 轴（trade-count）。Thesis Specification §5 明确要求 "several time scales"，且 Specification §3 把研究问题框在 "statistically independent random sequences"；Transaction-time 下 k=2 / Runs 每个 witness 都 p ≪ α，独立性侧仍有空间。

实现：`scripts/runner_exp2_all_offset_1sbars.py` 复用 all-offset strict 框架，数据管道改为 `aggTrades → 1-second bars（src/bars.py）→ close price 序列`；ℓ 范围 `(10, 700, step=2)`，5 asset × 15 月全覆盖。

## Gate taxonomy（四档 acceptance rule）

到当前版本为止，Exp 2 的可选 gate 共四档，由松到严。**注意 gate 与聚合轴绑定**：`relaxed` 仅用于 transaction-time（Plan A），`+runs` / `+runs+apen` 仅用于 1s-bars（Plan B）；`is_acceptable` (base) 是两条轴的共用主 gate。

| Gate | 适用聚合轴 | 判据 | 出处 | 用途 |
|---|---|---|---|---|
| `relaxed` | **transaction-time only** | `num_pass ≥ max(3, ⌈0.03·N_valid⌉)` on pred + mono, α=0.01 per offset | `runner_exp2_all_offset_relaxed.py` | Plan A heuristic，asset coverage 的补充证据 |
| `is_acceptable`（base） | transaction-time / 1s-bars 共用 | `valid_offset_ratio ≥ 0.80` AND `pred_pass_rate ≥ 0.80` AND `monobit_pass_rate ≥ 0.80` | `runner_exp2_all_offset{,_1sbars}.py` | 主 gate |
| `is_acceptable_with_runs` | **1s-bars only** | base AND `runs_pass_rate ≥ 0.80` | `runner_exp2_all_offset_1sbars.py` | 1s-bars CSV 的额外列；Plan B 下报告独立性改善的核心证据（不是 sensitivity） |
| `is_acceptable_with_runs_apen` | **1s-bars only** | base + runs AND `approximate_entropy_pass_rate ≥ 0.80` | `select_ell_exp2_1sbars.py`（post-processing 合成，不写回 CSV） | 进一步收紧到高阶 block 结构；实测会明显推高 ℓ\*，仅作 sensitivity 参考 |

Bonferroni / Šidák 不在表内，因为它们是 `relaxed` 在 transaction-time 下的 sensitivity mode（per-offset α 改为 α/N_valid 或 1−(1−α)^(1/N_valid)，仍走 ∃-pass 规则）。结果保存于 `data/processed/experiment2/relaxed-all-offset-per-month-bonferroni-(10,2000,2)/`，不采纳为主分析的方向性论证见 [Plan A §8.2](Exp2%20Plan%20A%20-%20Relaxed%20Gate.md#82-bonferroni--šidák-作为-sensitivity-mode)。

实证结论（1s-bars，15 窗口 × 5 资产）：
- base → +runs：大部分窗口 ℓ\* 不变或小幅上移，少数被完全封死（无可行 ℓ）
- +runs → +runs+apen：多数窗口 ℓ\* 再上移 0–60；少数资产（BNB 2026.02、ETH 2026.01）因 ApproxEntropy 在低 ℓ 有凹陷被推高数百 ℓ

**论文立场**：正文只用 base gate；`+runs` 与 `+runs+apen` 作为 robustness 附录，说明即使把 reference 测试纳入门槛，结论方向不变，仅 throughput 代价上升。
