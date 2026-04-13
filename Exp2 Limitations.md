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

如果后续需要补 robustness check，可增加一个固定 `history_length`（例如 `h=1` 或 `h=2`）的小规模对比图，作为附录材料，而不是替代主分析。

## Approximate Entropy 的 block size 固定为 2 可能偏小

当前 `approximate_entropy_test()` 使用固定 `block_size = 2`。这意味着检验主要关注长度为 2 到 3 的局部 bit 模式频率，而对更高阶的重复结构并不敏感。

随着 `\ell` 变化，不同 bitstream 的样本长度 `n` 差异很大。在大样本情形下，固定 `m = 2` 的 Approximate Entropy 可能在统计上仍然能工作，但在方法解释上存在一个明显问题：

- 它使用的是一个很短的局部模式窗口；
- 因此更像是“低阶复杂度检查”；
- 对长度 5 到 10 左右的高阶重复结构缺乏辨识能力。

从 NIST SP800-22 的经验规则看，`m` 不应固定得过小。对于当前 Experiment 2 中的大多数序列长度，固定 `m = 2` 明显偏保守，因此：

- 当前 `Approx. Entropy` 更适合作为一个低阶 sanity check；
- 不适合被过度解读为对“更高阶随机结构”的充分检验。

需要注意的是，这个问题和 predictability 的 adaptive `k` 不完全相同：

- predictability 是主判据，而且 adaptive 规则有较明确的文献支撑；
- approximate entropy 在当前框架中属于辅助 sanity check。

因此当前更稳妥的结论是：

- 先把 `m = 2` 明确标注为固定、低阶的辅助检验；
- 论文中需要说明它可能低估高阶模式依赖；
- 如果后续时间允许，更合理的增强方式是增加一个固定 `m = 3` 或 `m = 4` 的对比版本，用作 robustness check；
- 不建议在当前阶段直接把 Approximate Entropy 改造成主分析中的自适应核心指标。

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

## Runs 检验缺少 NIST 前置条件

按照 NIST SP800-22，运行 Runs test 之前应先检查频率前置条件：

- `|p1 - 0.5| < 2 / sqrt(n)`

只有在这一条件满足时，Runs test 的标准形式才严格成立。当前代码中没有显式执行这一步，而是直接对所有 bitstream 运行 Runs test。

这个问题的影响目前判断为有限，原因是：

- `monobit` 已经被单独计算；
- 如果频率偏差非常明显，通常 `monobit` 本身就会先失败；
- 因此，Runs test 缺少前置条件检查更多属于实现规范性不足，而不是当前主结论的核心风险。

不过从方法严谨性角度，论文中需要知道这一点：

- 当前 Runs p-value 不是完全按照 NIST 的前置流程执行的；
- 更规范的实现应先检查频率条件；
- 若条件不满足，可将 Runs test 结果记为 `NaN`，或单独记录 `runs_prerequisite_met`。

当前决定：

- 暂不为了这一个问题打断主分析流程；
- 把它作为一个低优先级、但应在方法说明中承认的规范性问题保留下来；
- 如果后续还有时间，可在 `src/stats.py` 中顺手补上这一 gate。

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
