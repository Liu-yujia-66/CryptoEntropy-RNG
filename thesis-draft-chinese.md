# Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation

**Author:** Yujia Liu — Uppsala University
**Repository:** https://github.com/Liu-yujia-66/CryptoEntropy-RNG
**Supervisor:** Andrey Shternshis
**Subject Reviewer:** Parosh Abdulla
**Status:** Working draft (Chinese-content version);章节标题保持英文,正文中文。

---

## Completion Status(写作进度速览)

| 章节                                                | 状态                | 备注                                                                                                                                                                                                                   |
| ------------------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Abstract                                          | ✅ 已写              | 中文三段;镜像 Introduction + Conclusion:背景 → 方法 → 数据 → Exp1–4 + Prototype 关键结果 → conditional yes                                                                                                                                                                           |
| Ch 1 — Introduction                               | ✅ 已写              | Motivation / Brief Lit Review / Research Questions 三节齐全                                                                                                                                                              |
| Ch 2 — Background                                 | ✅ 已写(2026-05-31 二次重构)              | §2.1 Literature Review(三层抽象 + microstructure + entropy aggregation + blockchain 路线)、§2.2 Background Information(glossary + 新增 Cryptographic conditioning / Password output strength 两 block);Bouchaud 已补入 §2.1 order-book 语境,Benedetto 移至 §6.4 Future Work                                                                                       |
| Ch 3 — Methods                                    | ✅ 已写              | 7 节:Encoding / All-Offset / Tests / Gates / 1s Pipeline / Multi-Asset XOR / Output Metrics(HKDF notation 2026-06 合并入 §2.2 Cryptographic conditioning block;Reproducibility 小节已删,repo link 放在标题页)                                                                                       |
| Ch 4 §4.1–4.3 — Setup + Data + Exp 1              | ✅ 已写              | Approach A 自包含;含 2 张数据表(trades/s + Exp 1 baseline 诊断)                                                                                                                                                                |
| Ch 4 §4.3 — **Experiment 2**                      | ✅ 已写(第一稿)         | 按 4 步链条写完:single offset → all-offset strict → all-offset relaxed → 1-second bars + Implications;含 4 张 Figure(spec)+ 3 张 5-行 summary 表 + Bonferroni 3 月对照(脚注);旧稿留在 `notes/ch4_exp2_through_prototype_old_draft.md` 备查 |
| Ch 4 §4.4 — **Experiment 3**(扩展检验电池)              | ✅ 已写              | 当前口径 = 至多 29 个 sub-test 的扩展电池 universe;sanity matrix + 62-cell battery + base/+Runs sensitivity 数据全在 `data/processed/experiment3/`;叙事骨架见本文件 §4.4 + `notes/Ch4-叙事draft.md`                                            |
| Ch 4 §4.5 — **Experiment 4**(多资产 XOR combination) | ✅ 已写              | 全链路跑完:MI matrix → calibration → all-subsets(26)→ validation(24 cell)→ min-entropy;3 张图就位;plan v3.4 冻结;正文术语统一用 combined / combination,文件名中的 `fused_stream.bin` 保留                                                     |
| Ch 5 — **Password Generator Prototype**           | ✅ 已写              | 独立成章(不是 Exp 5):应用层 end-to-end demonstration;n = 2/3/5 三档 market combined stream + B1/B2 baselines;共 3000 个 password;HKDF + 卡方/熵评估已完成;输入文件名仍为 `validation/n{N}/{month}/fused_stream.bin`                              |
| Ch 6 §6.1 — Main Finding and Scope                | ✅ 重写              | thesis-level success 开篇 + chronological 串 Exp 1–4 + Chapter 5;scope 用 plain "passive statistical setting" 取代 Level 1/2 二元术语                                                                                          |
| Ch 6 §6.2 — Answers to the Research Questions     | ✅ 重写              | RQ1/RQ2/RQ3 各一段加粗 lead;cross-market observations 已提升为独立 §6.3                                                                                                                                                       |
| Ch 6 §6.3 — Secondary Observations                | ✅ 已写              | 两条与 UHF 文献跨市场呼应的方法学观察(粗粒度活跃度分层;1 阶残留是采样轴属性);精简至 ~5 行,详情下放 §6.4 Future Work                                                                                                                                                            |
| Ch 6 §6.4 — Limitations & Future Work             | ✅ 已写              | 5 条 limitation + 4 条 future work(从原 8 + 4 收紧;主动操纵 / VDF 等不再展开)                                                                                                                                                            |
| Ch 7 §7.1 — Recap                                 | ✅ 重写              | 3 段:核心 question + 方法基础(Shternshis / Onofri) + "有条件 yes" 高层结论;与 Ch 6 §6.1 互补不重复                                                                                                                                          |
| Ch 7 §7.2 — Summary of Contributions              | ✅ 重写              | 三层结构:(1) 方法学贡献(relaxed gate / 1s pipeline / XOR combination / output metrics);(2) 应用贡献(end-to-end password prototype);(3) Secondary 观察(粗粒度分层 / 1 阶残留是轴属性)                                                              |
| References                                        | ✅ 已扩展至 39 条          | 14 既有(按 PDF 对照、修正 Shternshis & Marmi 2024→2025、Onofri 章节号、Landis & Bonneau venue)+ 25 条 2026-05-31 新增(标准规范、统计 / 信息论、cryptographic conditioning、password、microstructure);完整 bibliography 见 `thesis/references.bib`                     |


---

> **Abstract.** 随机数是安全系统的基础需求,但真随机源通常依赖专用硬件,伪随机生成器又仍然需要高熵种子。本论文研究公开的加密货币市场数据能否作为这样的熵来源,并以强密码生成作为应用目标。加密货币现货市场具有 24 小时连续交易、公共 API 可直接获取逐笔交易等特点,因此在工程上具有吸引力。核心困难在于,原始价格变动符号并不独立:bid-ask bounce 等微观结构效应会使相邻符号强相关,所以这些数据不能被直接当作随机比特使用。
>
> 方法上,本文复用近期高频金融研究中的熵驱动可预测性检验 *D* 与 all-offset 构造,并针对加密货币场景加入 relaxed acceptance gate、1-second bar 物理时间聚合流水线、多资产 XOR combination,以及 throughput 和 min-entropy 输出指标。数据来自 Binance 上 5 个 USDT 现货交易对的 15 个月 aggregated trades。
>
> 实验结果呈现清晰递进。原始 tick 符号在所有月度 cell 上被拒绝。1-second bar 聚合在 75 个 cell 中有 62 个通过 *D* + Monobit + Runs gate;随后,29-sub-test 扩展电池显示主要残留已集中在高阶、多符号结构上,并由 NIST SP800-22 与 TestU01 两套独立测试库共同检出。进一步的多资产 XOR combination 给出三个可部署配置(*n* ∈ {2, 3, 5}),而 *n* = 4 暴露出非平稳性边界。最后,prototype 使用 HKDF-SHA256 对这些 deployable streams 做 conditioning,生成约 98-bit 的密码,其字符统计与理想 baseline 对齐。总体结论是:在 passive statistical setting 下,答案是有条件的 yes;cryptographic conditioning 是整个设计的必要组成部分。

---

## Chapter 1 — Introduction

### Motivation

随机数在密码学、数字签名、数据脱敏、模拟仿真等场景中无处不在,是确保系统安全和正确性的最底层依赖之一。

常用的随机源大致分两类。第一类是确定性算法驱动的伪随机生成器(PRNG):它从一个简短的初始值出发——这个初始值称为*种子*(seed)——并把它扩展成一段看起来随机的长序列。只要种子保持秘密,PRNG 的输出就是不可预测的。问题在于种子本身必须真正难以猜测——这在技术上称为*高熵*(high-entropy),意思是它包含足够多的真不可预测性,让攻击者无法复现。所以 PRNG 并没有消除对真随机的需求,只是把这个需求转移到了"如何产生一个好的种子"上。

第二类是基于物理过程的真随机生成器(TRNG),例如电子噪声(代表性工程实例是现代 Intel CPU 的片上 RDRAND/RDSEED 指令,Mathew et al., 2012)或量子源(包括光子探测、真空涨落测量等,综述见 Herrero-Collantes & Garcia-Escartin, 2017,已被商业化为 ID Quantique Quantis 等产品)。TRNG 提供真正的不可预测性,但依赖专用硬件、部署成本高、不易在普通用户终端按需获取。

近年来一个具有研究价值的折中方向是:能否从已经存在、且公开可访问的高熵自然数据源中提炼随机性?文献中讨论过的候选包括区块链数据(例如 Bitcoin 区块哈希,Bonneau et al., 2015; Pierrot & Wesolowski, 2018)与金融市场数据;本论文聚焦后者。金融市场数据由海量参与者在极高频率下产生,带有难以建模的微观结构噪声,且其复杂性超出基础统计结构后难以被进一步压缩。已有工作把这一思路具体化为"financial randomness beacon"(金融随机灯塔),试图把市场公开数据转化为可信的随机源(Clark & Hengartner, 2010; Chiba & Ichikawa, 2024; Landis & Bonneau, 2025)。

然而,直接把价格变动符号当作随机比特流并不可行:多数研究指出,高频交易序列虽然在边际意义上看似平衡(例如涨跌频次接近 1:1),但其相邻符号之间存在强烈的短程依赖,典型机理是 bid-ask bounce 等微观结构噪声(Cont, 2001; Shternshis & Marmi, 2025)。要把这种"看起来随机但条件可预测"的数据转化为可用随机比特,需要一条清楚的处理流水线:先取市场价格,把价格变化符号编码为比特,再通过聚合降低短程依赖,随后对聚合后的比特流做随机性检验,最后才把通过筛选的序列送入标准 cryptographic conditioning。

这条流水线原则上并不绑定某一个市场,可应用于多种金融数据源。本论文选择加密货币现货市场,是出于实际数据条件:相比股票市场,加密货币市场全天 24 小时连续运行、无交易所休市断点,且公共 API(如 Binance)可直接拉取逐笔交易数据,中间没有传统券商的批处理或路由层介入,市场活动对终端用户直接可见。因此,加密货币数据适合作为本论文检验该流水线的对象。随之而来的方法问题是:**聚合应该在哪条时间轴上进行,聚合到什么粒度才合适?**

应用层目标方面,本论文把这条 randomness 通路落点在**强密码生成(strong password generation)**。已有文献为这一选择提供了可定位的背景:早期大规模 web 密码习惯研究(Florêncio & Herley, 2007)与后续 guessing-corpus 分析(Bonneau, 2012)报告用户自选密码常集中在 ~20–30 bits entropy 区间,随机生成是文献中讨论的一类对策。把市场衍生 randomness 通过标准 cryptographic conditioning 接到密码生成,因此构成一个 scope 明确、可在本论文内端到端验证的 application target。

### Brief Literature Review

本节定位本论文相对既有工作的位置。

**Financial / public randomness 路线。** 把公开金融数据(及类比的链上数据)作为 randomness 源已有多条工作:Clark & Hengartner (2010) 把 Dow Jones 30 设计为可验证灯塔(public beacon);Bonneau et al. (2015) 与 Pierrot & Wesolowski (2018) 评估 Bitcoin 区块哈希作为类似公共源的可行性与可塑性;Chiba & Ichikawa (2024) 把加密货币价格与 LFSR 结合做比特提取;Landis & Bonneau (2025) 在主动攻击者模型下评估金融灯塔的安全成本。这些工作覆盖协议层、比特提取层与对抗安全层,但都没有打通"原始数据 → 可验证应用 prototype"的工程通路。

**Statistical market-randomness 路线。** 另一条线索研究金融时间序列本身在 randomness / aggregation 视角下的统计性质。Shternshis & Marmi (2025) 引入基于 KL 散度的熵驱动可预测性检验 *D*,经验证实相邻成交方向之间存在 bid-ask bounce 引起的 1 阶负相关;Onofri et al. (2025) 把该框架升级为"全 offset"聚合构造,在 8 只美股加 1 只 ETF 上观察到 trades/s 与所需聚合层级 ℓ\* 同向。这两篇是本工作的直接方法学先行者。

**Gap.** 综合两条线索的缺口可归为两点:

- **(i) 跨市场方法迁移。** 基于 *D* + 全 offset 的随机性检验框架已在美股上验证,但在 24/7 连续交易的加密货币市场上是否同样适用、需要何种聚合轴与层级,尚未被系统性研究。
- **(ii) 端到端工程通路。** 协议层金融灯塔(Clark & Hengartner, 2010; Chiba & Ichikawa, 2024; Landis & Bonneau, 2025)与底层统计验证(Shternshis & Marmi, 2025; Onofri et al., 2025)在加密货币数据上尚未被以一条从"聚合参数选择"贯通到"密码生成器"的端到端流水线连起来。

本论文通过一个分阶段的 empirical design 回应 (i) 与 (ii)。Chapter 4 包含四个实验:第一个实验检验 raw baseline,第二个实验选择聚合轴与聚合层级,第三个实验用更大的 test battery 审计被选中的 streams,第四个实验进行多资产 combination 并在 held-out months 上验证。Chapter 5 再把可部署 streams 接入 password generator prototype。承接以上 gap,§1.3 给出本工作回答的三个研究问题。

### Research Questions

承接上述动机与文献缺口,本工作回答三个研究问题:

- **RQ1.** 如何设计聚合算法,从加密货币价格数据中抽取统计上独立的随机序列?
- **RQ2.** 这些序列能在多大程度上通过标准随机性检验?
- **RQ3.** 这种数据驱动的随机性能否被有效地应用于安全密码生成?

关于 RQ3 的 scope 说明:**统计测试是必要的,但不足以保证密码学安全性;本论文的原型将市场衍生的比特视为密码学组件的熵输入,而非直接作为密码字符串**。RQ3 的"有效应用"因此被限定在"为标准 password conditioning 流程提供合格 entropy",而非替代该流程。

---

## Chapter 2 — Background

### Literature Review

本节回顾与金融时间序列统计性质和随机性相关的文献,承接 Brief Literature Review 的"两类文献"划分:**统计验证线**(Cont, 2001; Shternshis & Marmi, 2025; Onofri et al., 2025; Shternshis et al., 2022)关注金融时间序列本身的随机性结构;**应用 / 协议线**(Clark & Hengartner, 2010; Bonneau et al., 2015; Pierrot & Wesolowski, 2018; Chiba & Ichikawa, 2024; Landis & Bonneau, 2025)关注把它转化为密码学组件。下文按主题分 4 个 block 展开。

**Stylized facts and microstructure noise.** 关于高频金融时间序列的统计性质,Cont (2001) 从 returns 视角归纳了一组"stylized facts":重尾分布、波动率聚集、绝对收益的幂律自相关缓慢衰减,以及——本论文最关心的——**超短滞后(微观结构尺度)下因 bid-ask bounce 引起的负自相关**:成交价在买一卖一之间频繁切换,使以 Δp 符号编码的比特序列在相邻位上呈强负相关。Bouchaud et al. (2002) 从 order-book 视角描述同一类问题:价格变化由限价订单簿结构塑造,并非独立抽样。Shternshis & Marmi (2025) 把这一负自相关形式化为可检验的 1 阶残留诊断,并在 SNAP / F / CCL 三只低价股上给出经验证据。

除 bid-ask bounce 之外,微观结构层面另一项被充分文献化的 stylized fact 是 **trade-sign 的 long-memory**。Lillo & Farmer (2004) 在伦敦交易所数据上证明,executed market orders 的符号服从 long-memory 过程,自相关衰减缓慢;他们将其归因于 order splitting 与 herding behavior。这两条 stylized facts 对价格变化符号的 lag-1 自相关作用方向**相反**:bid-ask bounce 通过 buy / ask 交替造成负自相关,而持续 trade-sign 自相关在 sustained order flow walk-the-book 时累积出正自相关。哪种机制 dominate 取决于资产的活跃度区间。

上述工作共同表明:任何想直接把"价格涨跌符号"当成 i.i.d. 随机比特的方案,在原始 tick 粒度上几乎一定会失败——这正是本工作把"聚合"作为方法核心的根本原因。

**Financial data as a randomness source.** 这条线索可拆成三个互补的抽象层:

- **协议层。** Clark & Hengartner (2010) 用计算金融工具估计 Dow Jones 30(由 30 只美国大盘股构成的股指)中每只股票每日提供 6–9 bits 熵,并据此设计 128-bit 可验证灯塔(verifiable beacon)协议——回答"金融数据中确实存在 randomness、能转化为密码学种子吗"。链上数据是同一抽象层的并行路线:Bonneau et al. (2015) 评估 Bitcoin 区块哈希作为公共灯塔的可行性,Pierrot & Wesolowski (2018) 进一步分析其 entropy 在矿工 / 对抗下的可塑性(malleability);本论文不进入链上路线,只用 financial market data 作为 entropy input。
- **比特提取层。** Chiba & Ichikawa (2024) 用加密货币价格扰动 LFSR 的采样间隔,产出比特流并以 Diehard 检验(经典随机性检验电池,NIST STS 的历史前身)做 sanity check——回答"如何把市场信号工程化漂白成可用的随机比特"。
- **对抗安全层。** Landis & Bonneau (2025) 在 active attacker 模型下展示,操纵 S&P 100(由 100 只美国大盘股构成的股指)灯塔需要数十亿美元资本与数百万美元 slippage 损失——把问题从"有多少熵"推进到"熵在对抗下是否可信"。**本论文不进入对抗安全层**(scope 详见 §6.1):passive statistical setting 下评估即可满足 password generator 的应用层条件,active-attacker 模型留给公共灯塔类研究。

三者各自工作在不同抽象层,**但都没有打通从'底层统计验证'到'应用层 password prototype'的端到端通路**——这正是 Brief Lit Review Gap (2) 在加密货币数据源上的具象化。本论文落在比特提取层,但与 Chiba & Ichikawa (2024) 不同的是,在随机性评估阶段不依赖额外 LFSR 后处理,而是直接评估"通过聚合后的原始数据本身是否满足现代随机性检验"。

**Entropy-based predictability and the all-offset construction.** Shternshis & Marmi (2025) 提出了一种基于 Kullback–Leibler 散度的熵驱动可预测性检验 *D*(正式定义见 §2.2 Background Information)。该检验把 *k* 当成用户自选超参数;Shternshis & Marmi (2025) 在其 §4.4 中取固定 *k* = 2 来检视前述 bid-ask bounce 引起的相邻符号配对可预测性。本论文沿用这一 *k* = 2 设定作为 1 阶诊断,与 adaptive-*k* 主统计量互补,这构成了把 1 阶与高阶结构区分开的方法学起点。本文在 adaptive *k* 与固定 *k* = 2 两种取值下分别运行 *D* 检验。

Onofri et al. (2025) 进一步把这一框架升级为"全 offset"构造(Onofri 原文称之为 "ℓ-samplings"):对每个聚合层级 ℓ,按 ℓ 个不同起始 offset 各构造一条比特流并独立检验,然后用一个"通过率门槛"作为 ℓ 的接受规则。这一构造把"单条 *p* 值是否过线"换成了"绝大多数 offset 是否同时过线",并以 -log₁₀(p) 的箱线图直接展示 ℓ 增长下的 p 值分布。该论文在 8 只美股加 1 只 ETF(Exchange-Traded Fund,交易所交易基金,把一篮子资产当作一个证券在交易所交易)上得到一条稳健的经验观察:资产的 trades/s 越高,所需的最小聚合层级 ℓ\* 越大(原文同时指出某些资产存在 non-monotonic 行为)。本论文直接复用此全 offset 构造与通过率门槛框架,但在三个具体方面与 Onofri et al. (2025) 不同:市场是加密货币而非美股;聚合时间轴在 transaction-time 之外加入了 physical-time(1-second bar);Onofri 中的定性接受判定在本论文中被实例化为定量的固定阈值 strict gate,并附加一个 heuristic relaxed gate(详见 §3.4 与 §3.5)。

**Market efficiency under stress.** Shternshis et al. (2022) 通过 Shannon 熵 + KL 距离 + 蒙特卡洛模拟,展示了 2012–2021 年莫斯科交易所效率随时间显著变化、且依赖行业部门——这是另一类市场上"金融时间序列性质并非 stationary"的独立证据。这一观察支持本论文以月度时间窗口报告 selected ℓ* 而非将其视作稳定值。

### Background Information

本节回顾后续 Methods 用到的核心概念。所有 randomness 检验都基于同一个 H_0 = 序列独立同分布的假设,每个检验给出 p 值,本论文统一以 α = 0.01 作为接受门槛。

**Shannon entropy and conditional unpredictability.** 对一个二值随机变量 X ∈ {0, 1},Shannon 熵定义为 H(X) = −Σ p(x) log₂ p(x)(Shannon, 1948),在 p(0) = p(1) = 0.5 时取最大值 1。值得强调的是:**单点(边际)熵接近 1 不蕴含序列不可预测**——一个仅在 0 与 1 之间交替的序列其边际分布也是 0.5/0.5,但条件熵 H(X_t | X_{t−1}) ≈ 0。本论文中"是否随机"的判据始终建立在条件分布或多体统计上,而不是仅依赖 H。本论文中以偏离量 |H(X) − 1| 命名为 *Shannon-bias*,仅作为汇总指标使用,不进入接受判据。互信息、条件熵与 min-entropy 的形式化定义参见 Cover & Thomas (2006)。

**Predictability D.** Shternshis & Marmi (2025) 提出的熵驱动可预测性检验,基于 Kullback–Leibler 散度——衡量序列中长度 *k* 的连续符号块的联合分布与独立同分布下应有分布的偏离;在 H_0 下渐近服从自由度为 (s^{k−1} − 1)(s − 1) 的 χ² 分布(二元下 = 2^{k−1} − 1)。窗口长度 *k* 为用户选择的 hyper-parameter。

**NIST SP800-22 STS.** NIST 发布的 randomness 测试电池(Statistical Test Suite, Bassham et al., 2010),共 15 个子检验,分 5 大类:频率(Frequency)、模式(Pattern)、熵 / 复杂度(Entropy)、谱(Spectral)、随机游走(Random Walks)。常用代表性子检验包括:**Monobit**(频率类:|S_n|/√n 的标准正态近似检测 1 比特频率与 0.5 的偏离)、**Runs**(模式类:序列拆为极大同符号段,以"段数偏离 i.i.d. 期望"作为统计量,对相邻比特相关性敏感)、**Approximate Entropy**(熵 / 复杂度类:按长度 m 与 m + 1 的窗口出现频率做差衡量序列复杂度;窗口长度 m 为用户选择的 hyper-parameter;原始定义见 Pincus, 1991)。

**TestU01 batteries.** TestU01 是一组 randomness 检验库(L'Ecuyer & Simard, 2007;Onofri et al. (2025) 在金融数据上用过)。据 TestU01 用户文档,它包含 **Alphabit**(9 子检验,small-sample 友好)与 **Rabbit**(26 子检验,综合)等子电池,跟 NIST STS 互补。本论文主分析启用 Alphabit;Rabbit 因长度与 scope 约束不纳入当前实验,列入 Future Work。

**Aggregated trades and 1-second bars.** Binance 提供两种主要数据视图:逐笔成交(`trades`)与聚合成交(`aggTrades`);后者把同一价格、同一方向、同一时刻簇拥到一起的成交合并为一条记录,既减小数据量又保留了价格变化与符号信息。基于这两种视图,可分别在 transaction-time 轴(按笔数)与 physical-time 轴(按秒)上做聚合。

**Multiple testing.** Bonferroni (1936) 与 Šidák (1967) 校正用于控制族内 Type-I 错误率,把单次显著性水平 α 收紧到 α/N 或 1 − (1 − α)^{1/N}。它们回答的是"在 *N* 个 test 中,*至少有一个* 假拒绝 H_0 的概率有多大"这个问题。对相反的问题——"在 *N* 个 test 中,*至少有一个* 假通过的概率有多大"——并没有对称的校正,因为收紧 α 会让每个 test 单独更容易通过,反而把族内"假通过"概率推向相反方向。控制 false discovery rate 的另一思路是 Benjamini & Hochberg (1995) 的 BH 程序;本论文未采用 FDR 校正,理由见 §3.4。

**Cryptographic conditioning.** 标准做法把粗 entropy 输入(min-entropy 不一定接近 1 bit/symbol)通过密码学构造转化为可作密钥材料使用的 pseudo-random 输出。本论文采用 **HKDF**(HMAC-based Extract-and-Expand Key Derivation Function, Krawczyk & Eronen, 2010, RFC 5869;安全性分析见 Krawczyk, 2010),底层哈希为 **SHA-256**(NIST FIPS 180-4, 2015)。HKDF 分两步:**Extract** 把不一定均匀的 entropy input 压缩成一个 pseudo-random key;**Expand** 把该 key 与 context 标识扩展成所需长度的输出比特。**在 IKM 具有足够 min-entropy 且满足 HKDF 使用假设时**,这一组合可作为 cryptographic conditioning / extraction component。本论文沿用 HKDF 标准命名:

- **salt** —— Extract 步骤的随机或伪随机字节串。标准 HKDF 允许 salt 公开;但若 HKDF 输出本身需要保密,conditioning 阶段还必须结合某种不公开的 deployment-secret material。该 secret 可以由 salt 承担,也可以作为独立 secret input 进入系统设计。
- **IKM(input keying material)** —— Extract 步骤的 entropy input,也是 min-entropy budget 所 sizing 的对象。
- **PRK(pseudo-random key)** —— `HKDF-Extract(salt, IKM)` 输出的 32-byte 中间结果。
- **info** —— Expand 步骤的 context 标识。
- **OKM(output keying material)** —— `HKDF-Expand(PRK, info, L)` 输出的变长 byte 序列。

输入熵的下界用 **NIST SP800-90B**(Turan et al., 2018)推荐的 min-entropy estimator;**本文只采用其中 Most Common Value(MCV)与 Markov 两个 estimator 的简化子集**(取较小者),用于 deployment set sizing,详见 §3.7 与 §4.5——不实施完整 SP800-90B entropy validation flow。

**Password output strength.** 随机生成的密码与人选密码的强度衡量口径不同。**随机生成密码**的强度由 search-space entropy 决定:对长度 L、字符集大小 n 的均匀采样密码,strength = L × log₂(n) bits。**人选密码**强度依赖 guessability 模型,实证集中在 ~20–30 bits 量级(Bonneau, 2012; Florêncio & Herley, 2007),两者不能混淆。verifier 端的现代推荐(NIST SP800-63B-4, 2025)把重点从固定 composition rule 转向长度、blocklist、rate limiting 与 verifier-side 存储保护等机制。本论文后文使用 ≳ 80 bits 作为 strong-password 的经验工作 benchmark——显著高于 human-chosen 估计区间、远离已知 offline-cracking 实用上界。

---

## Chapter 3 — Methods

本章按"编码 → 构造 → 检验 → 接受规则 → 时间轴对照 → 多资产组合 → 输出口径(throughput + min-entropy)"的顺序,描述本论文用于把价格序列转化为可被检验的随机比特流的全部方法。HKDF-SHA256 作为标准 cryptographic conditioning / extraction component(已在 §2.2 引入),只在下游 Chapter 5 的 password prototype 中使用,不重复定义。

- **复用 prior work**:Shternshis & Marmi (2025) 的熵驱动可预测性检验 *D*,在 adaptive *k* 与固定 *k* = 2 两种取值下分别运行;Onofri et al. (2025) 的全 offset 构造,包括其 ApproxEntropy m = 5 的窗口选择;以及来自 NIST SP800-22 STS 电池(Monobit、Runs、Approximate Entropy 与扩展电池项)与 TestU01 Alphabit 的经典 sub-tests。本论文的 strict gate(§3.4)在 Onofri 的全 offset 框架上 operationalise 出固定 0.80 通过率门槛。
- **针对加密货币市场的方法学增量**:整体方法学思路是把熵驱动的 *D* 检验与经典的 NIST / TestU01 sub-tests 放进同一个 all-offset 接受规则与审计框架中,并在 24/7 连续的加密货币市场上评估这一组合电池的表现。在复用部分之上,具体的新内容包括:Relaxed gate(§3.4)、1-second bar physical-time pipeline(§3.5)、multi-asset XOR combination(§3.6),以及 Output Metrics 口径——throughput 与简化 min-entropy 估计(§3.7)。HKDF-SHA256 作为标准 cryptographic conditioning component(§2.2 已引入),只在 Chapter 5 的 password prototype 中使用,不计入本论文的新内容。

### Aggregation and Encoding

记原始 tick 序列为 {(t_i, p_i)}_{i=0}^{N-1},其中 t_i 为时间戳,p_i 为成交价(0-based 索引,与代码实现保持一致)。聚合层级 ℓ 与起始 offset o ∈ {0, 1, …, ℓ − 1} 联合定义一条采样子序列

$$
q^{(\ell, o)}_j = p_{o + j\ell}, \qquad j = 0, 1, \ldots, \lfloor (N - o - 1) / \ell \rfloor
$$

其差分 Δq^{(ℓ, o)}_j = q^{(ℓ, o)}_j − q^{(ℓ, o)}_{j−1},  j = 1, 2, …, ⌊(N − o − 1) / ℓ⌋。比特编码取符号:

$$
b^{(\ell, o)}_j = \mathbb{1}\!\left[\Delta q^{(\ell, o)}_j > 0\right]
$$

若 Δq^{(ℓ, o)}_j = 0,则该位被剔除(*drop-zero*,与 Shternshis & Marmi (2025) 一致),后续位前移以保持比特流连续。该剔除是必要的:零差分占比在低 ℓ 时显著,若以任何确定规则映射到 0 或 1 都会注入显著偏差。

在 transaction-time 轴上,ℓ 的单位是"成交笔数";在 physical-time 轴上,p_i 先经 §3.5 描述的 1-second bar 流水线转换为"每秒收盘价",于是 ℓ 的单位变为"秒数"。两条轴上其余编码步骤完全一致,这使得后续结果可以在同一编码逻辑下直接对照。

**算法 1: Aggregation and bit encoding (single offset).**

```
Input:  tick prices {p_0, p_1, ..., p_{N-1}}, level ℓ, offset o
Output: bit stream b

q ← [p_o, p_{o+ℓ}, p_{o+2ℓ}, ...]
b ← []
for j = 1 to |q|−1:
    Δ ← q[j] − q[j−1]
    if Δ > 0:    append 1 to b
    elif Δ < 0:  append 0 to b
    else:        skip                  # drop-zero
return b
```

### All-Offset Construction

本节描述的全 offset 构造直接来自 Onofri et al. (2025) 中提出的 "ℓ-samplings" 框架——对每个聚合层级 ℓ,按 ℓ 个不同起始 offset (o = 0, 1, …, ℓ − 1) 各构造一条比特流。本论文沿用此构造,仅在加密货币数据上做参数调整(per-asset ℓ 网格、step、上限)。

对固定 ℓ,共有 ℓ 个候选 offset。该构造同时考察这 ℓ 条比特流,记每条上的检验 *p* 值为 p^{(o)},通过率定义为

$$
r_{\text{pass}}(\ell, \alpha) = \frac{1}{N_{\text{valid}}(\ell)}
\sum_{o \in \mathcal{O}_{\text{valid}}(\ell)} \mathbb{1}\!\left[p^{(o)} \ge \alpha\right]
$$

其中 𝒪_valid(ℓ) 是比特数 ≥ `MIN_BIT_COUNT = 2000` 的 offset 集合。该阈值是保守的工程地板,确保有足够样本支撑 *D* 检验的 χ² 渐近近似。由于不同 offset 共享同一份底层 tick 数据,ℓ 条比特流是高度相关的(尤其在大 ℓ 下);它们的同时通过给出"序列在多个起点都通过"的稳健性证据,但*不能*被解释为独立检验的复合结果。这一点决定了 §3.4 中"接受规则"的设计取向。

### Test Battery

本论文的检验电池如下:

- **Predictability D (adaptive k)** — 主统计量,*k* = ⌊0.5 log₂ n⌋。
- **Predictability D (fixed k = 2)** — 1 阶诊断,检测相邻符号配对依赖(同时覆盖 bid-ask bounce 反转与持续 order-flow 同向相关两类 stylized fact;详见 §4.3 R3)。
- **Monobit** — 基础频率检验,检测整体 0/1 平衡。
- **Runs** — NIST 形式,检测相邻比特相关性。NIST 的前置 frequency check 未单独实现,因为 Monobit 在 α = 0.01 通过等价于 |π − 0.5| ≤ 1.288/√n,严于 NIST 阈值 2/√n;前置检查在所有被接受的 ℓ 上都被 Monobit gate 等价吸收。
- **Approximate Entropy (m = 5)** — 多窗口复杂度差(Pincus, 1991),与 Onofri et al. (2025) 表 4 对齐。NIST 默认 m = 2(对短样本更稳),m = 5 对短程结构更敏感但需要 n ≳ 10·2^m ≈ 320 才能保证渐近分布可靠;本论文 n ≥ 2000 远超此阈值。
- **TestU01** (L'Ecuyer & Simard, 2007) — 扩展审计与 validation 阶段的 cross-battery 外部验证;引入 Alphabit,而 Rabbit 保留为 Future Work。

在扩展电池口径下,本论文使用一个固定的 **29-sub-test universe**:core 5 项(D adaptive-*k*、D(*k* = 2)、Monobit、Runs、ApEn)、NIST SP800-22 (Bassham et al., 2010) 扩展 7 项(BlockFrequency、CumSum forward/backward、LongestRun、DFT、Serial *m* / *m*−1),以及 TestU01 Alphabit 按统计量展开后的 17 项。Alphabit 官方包含 9 个检验,但 RandomWalk1 在 L64 与 L320 两档各输出 5 个统计量,因此本论文按统计量口径把 Alphabit 展开为 17 个 sub-tests。三部分合计 5 + 7 + 17 = 29。短长度下 TestU01 会自动 length-skip 长 block 子项,相应项不进入 admissible 分母。

**Sub-test 选择的长度预算约束.** 本论文 cell 的可达 bit 长度约在 2K–200K 区间(单 offset 流约 2K–25K bit;跨 offset、跨月或跨资产拼接后约 25K–200K bit)。NIST SP800-22 STS 全套(15 项)与 TestU01 Crush 全套中,若干 sub-test 推荐输入长度在 10⁶ bit 量级——例如 Non-overlapping Template Matching、Universal Statistical、Random Excursions 系列以及 Crush 的多数 sub-test——超过本文 cell 可达范围,无法在 selected ℓ\* 下稳定执行。本论文因此在 NIST SP800-22 中只选长度需求 ≤ 200K bit 的 7 个(BlockFrequency、CumulativeSums 前向 / 后向、LongestRun、DFT、Serial *m* / *m*−1),在 TestU01 中只启用 Alphabit 子电池。这 7 项 NIST SP800-22 sub-test 跨越 STS 的几大检验家族——frequency(BlockFrequency)、累积偏移(CumulativeSums)、runs(LongestRun)、频域(DFT)、entropy / 多符号结构(Serial),使 length-budget 过滤后仍保留 family-level 覆盖。这是由 cell bit-length 决定的方法学过滤,不是对未纳入项理论重要性的否定;未纳入项见 §6.4 Future Work。

**TestU01 启用条件.** 沿用 Onofri et al. (2025) 的 cross-battery 设计,本论文方法学进一步包括 TestU01 的 **Alphabit** 子电池作为 cross-battery 外部验证手段。Selection-grid 阶段不启用 TestU01:per-(asset, ℓ, offset) bitstream 只是参数搜索过程中的中间输出,长度通常低于 cross-battery sanity-check 的适用范围,不是 cross-battery 验证的合适输入。扩展审计与 validation 阶段在 selected ℓ\* 上做跨月、跨资产或跨 offset 拼接,使长度满足 sanity-check 的适用范围,再启用 Alphabit 中相应子检验子集。Rabbit 子电池需要更长、更稳定的 bitstream,当前不进入主分析。

**Why both fixed *k* = 2 and adaptive *k*?** Adaptive *k* = ⌊0.5 log₂ *n*⌋ 在 ultra-high-frequency 月度样本下通常取 5–6,*D* 检验对应 2^{k−1} ≈ 16–32 个 context;1 阶相关性会被稀释到十几到几十分之一的位置,统计功效迅速下降。Shternshis & Marmi (2025) 提供了与此一致的经验证据:在 predictable days 上,固定 *k* = 2 时 p̂(00) + p̂(11) < 0.5 的"符号反转过强"模式显著;而当 *k* 提到 ≈ 5–6 时该模式不再显著。因此,本论文保留 *D*(*k* = 2) 作为相邻符号配对依赖的 1 阶诊断,与 *D*(adaptive *k*) 互补:前者捕捉短程结构,后者刻画整体可预测性。后续 baseline 结果将进一步验证,加密货币 tick signs 中的 1 阶残差需要单独诊断,不能只依赖 adaptive-*k* 主统计量。

### Acceptance Gates

接受规则是 all-offset 框架中把"通过率"映射到"ℓ 是否被接受"的关键步骤。本论文采用两档 gate,按时间顺序引入。

**Strict gate.** Onofri et al. (2025) 采用**定性接受判定**。本论文在同一框架内采用一个**定量对应版本**:固定 0.80 pass-rate 阈值,贯穿全部 (资产, 时间窗口) cell 统一使用。Strict gate 要求三条同时成立:

$$
\begin{aligned}
r_{\text{valid}}(\ell)            &\ge 0.80 \\
r_{\text{pass}}^{D}(\ell)         &\ge 0.80 \\
r_{\text{pass}}^{\text{Mono}}(\ell) &\ge 0.80
\end{aligned}
$$

其中 α = 0.01 取自 Onofri et al. (2025)。Runs 与 *D*(*k* = 2) 仅作补充诊断、不进入接受判据,理由见 §3.3。

**Relaxed gate(本论文新增 heuristic).** 全 offset 比特流之间高度相关,从工程使用角度,最终系统只需要选择一条可用的 witness offset;但在统计选择过程中,单纯的"至少一条通过"规则会引入严重的 selection bias —— 如果底层序列仍含有结构性依赖,只要 offset 数足够多,也可能出现某一条 offset 因样本波动或检验功效不足而通过 α 阈值。

对此,按 §2.2 末段 *Multiple testing* 所述的方向不对称(Bonferroni / Šidák 收紧 α 会让"假通过"概率反向上升),本论文**既不采用"至少一条通过"规则(selection bias),也不采用 Bonferroni / Šidák 形式校正(方向相反)**,而采用如下启发式冗余判据:

$$
\text{accept}_{\text{relaxed}}(\ell) \iff
n_{\text{pass}}(\ell) \ge \max\!\left(F,\; \lceil f \cdot N_{\text{valid}}(\ell) \rceil\right)
$$

其中 n_pass(ℓ) 为同时通过 *D* 与 Monobit(α = 0.01,不校正)的 offset 数;(F, f) 为两个调控参数。本论文取 (F, f) = (3, 0.03):F 给出多 offset 共同确认的最低冗余,f 约为 α = 0.01 噪声地板的 3 倍。**这一取值是 design choice,而非由形式理论推出**——如前所述,"至少一条通过"方向的多重检验校正在标准理论中无对称解,因此 (F, f) 的具体取值无法从 Type-I / Type-II 控制中机械推导;本论文以"多 offset 冗余确认 + 高于 α 噪声地板"为指导原则选取了一组保守值,完整的方法学限制(包括对其他 (F, f) 取值未做敏感性分析)在 §6.4 中记录。该规则在论文中被显式标注为 *heuristic robustness check*,不作为正式校正。

**算法 2: All-offset acceptance check at level ℓ.**

```
Input:  tick prices {p_i}, level ℓ, gate ∈ {strict, relaxed}, α = 0.01
Output: accept(ℓ) ∈ {true, false}; witness offset (if accepted)

O_valid ← ∅
for o = 0 to ℓ−1:
    b ← Algorithm 1 with (p, ℓ, o)
    if |b| ≥ MIN_BIT_COUNT (= 2000):
        compute and store p^D(o), p^Mono(o) on b   # reused by both gates below
        add o to O_valid

N_valid ← |O_valid|
r_valid ← N_valid / ℓ

if gate = strict:
    r_pass^D    ← #{o ∈ O_valid : p^D(o)    ≥ α} / N_valid
    r_pass^Mono ← #{o ∈ O_valid : p^Mono(o) ≥ α} / N_valid
    return  r_valid ≥ 0.80  ∧  r_pass^D ≥ 0.80  ∧  r_pass^Mono ≥ 0.80

if gate = relaxed:
    n_pass ← #{o ∈ O_valid : p^D(o) ≥ α  ∧  p^Mono(o) ≥ α}
    return  n_pass ≥ max(F, ⌈f · N_valid⌉)         # (F, f) = (3, 0.03)
```

**ℓ\* 选择规则.** 将使算法 2 返回 true 的最小 ℓ 记为 selected ℓ\*。具体的 ℓ 网格(per-asset 取值、step、上下限)在 Ch4 Experiments 中给出。

### Time-Based Aggregation Pipeline

**针对加密货币市场的方法学增量。** 为利用加密货币市场 24/7 连续运行这一特性,本论文在 transaction-time 轴之外引入一条基于 1-second bar 的 physical-time 聚合轴。在 transaction-time 轴上,吞吐随交易频率变动,因此每出一个 bit 所需的时间也随市场冷热变化;在 physical-time 轴上,1/ℓ\* 给出固定 sampling rate 与直观的 wall-clock waiting-time 口径,但它不是最终有效 bit/s。由于 drop-zero 会剔除零差分秒,实际有效 bit/s 会略低于 1/ℓ\*。

1-second bar 流水线(算法 3)把 trades 按 UTC 整秒(Coordinated Universal Time,Binance 使用的全球时间戳标准)分桶。对每个不含 trade 的秒,该秒的 bucket 用最近一次成交的价格填充(forward-fill)。然后在得到的每秒收盘价序列上执行与 §3.1 相同的差分 + 符号编码 + drop-zero 流程。前向填充过的秒与其前一秒的差分为 0,会在 drop-zero 中被剔除,因此不向比特序列贡献任何 bit;最终的比特序列只包含来自实际交易秒之间真实价格变化的 bit。

**算法 3: 1-second bar pipeline (physical-time axis).**

```
Input:  trade stream {(t_i, p_i)}, level ℓ (seconds)
Output: bit streams {b^(ℓ, o)} for o = 0, ..., ℓ−1

# Step 1: bucket by UTC second + forward-fill empty seconds
# (the first observed second always contains a trade,
#  since data starts at the first trade)
group trades by floor(t_i)               # to whole UTC seconds
for each second s in order:
    if s has trade(s):  c_s ← price of last trade in s
    else:               c_s ← c_{s−1}    # forward-fill

# Step 2 + 3: encode each offset via Algorithm 1
for o = 0 to ℓ−1:
    b^(ℓ, o) ← Algorithm 1 with ({c_s}, ℓ, o)
return {b^(ℓ, o)}
```

ℓ 网格取 [10, 600] 步长 1,既覆盖"秒级聚合即足够"的乐观情形,又给出更长聚合(分钟级)的对照。ℓ 的上限 600 秒(= 10 分钟)对应一个面向密码生成的合理 latency 上界。

### Multi-Asset XOR Combination

本论文还在单资产 physical-time bit streams 之上定义 multi-asset combination 算子。给定资产子集 S,先对每个资产 a ∈ S 构造每秒价格序列(由 §3.5 的 1-second bar pipeline 产出)并计算符号

$$
s_{a,t} = \operatorname{sign}(c_{a,t} - c_{a,t-1}) \in \{-1, 0, +1\}.
$$

这里的 0 表示该秒与前一秒价格相同(包括 forward-fill 后无真实价格变化的秒)。与单资产编码不同,multi-asset combination 不能先对每个资产各自 drop-zero,否则不同资产的比特流长度会不同、UTC 秒级对齐会丢失。因此本论文先在 UTC 秒上对齐资产子集,再执行 **drop-any-zero**:只有当所有 a ∈ S 都满足 s_{a,t} ≠ 0 时,该秒才进入组合流。Drop-any-zero 可视为 §3.1 中 drop-zero 规则在多资产情形下的推广;当 |S| = 1 时,它退化为普通 drop-zero。

保留下来的每个秒 t 被编码为

$$
x_{S,t} = \bigoplus_{a \in S} \mathbb{1}[s_{a,t} > 0],
$$

其中 ⊕ 表示 XOR。所得 {x_{S,t}} 称为 combined stream。随后,对该 combined stream 再执行 ℓ-level XOR aggregation:对每个 offset o ∈ {0, …, ℓ − 1},把连续 ℓ 个 combined bits 分为一组并 XOR-reduce,

$$
y^{(\ell,o)}_{S,j}
= \bigoplus_{r=0}^{\ell-1} x_{S,\,o+j\ell+r}.
$$

这一步对应 piling-up 直觉(Matsui, 1994):若输入近似独立,XOR 会压低边际 bias。但该直觉在本文中只作为工程假设,不作为安全证明;资产间相关性仍需通过 mutual information 与 out-of-sample validation 做经验证查。

**算法 4: Multi-asset XOR combination and ℓ-level aggregation.**

```
Input:  per-asset 1-second close prices {c_{a,t}} for asset subset S,
        aggregation level ℓ, offset o
Output: aggregated combined stream y

# Step 1: per-asset signs with zeros preserved
for each asset a ∈ S:
    for each UTC second t:
        s_{a,t} ← sign(c_{a,t} − c_{a,t−1})      # −1, 0, or +1

# Step 2: align and drop-any-zero
T ← common UTC-second range covered by all assets in S
x ← []
for each t ∈ T:
    if s_{a,t} = 0 for any a ∈ S:
        skip
    else:
        append XOR_{a∈S} 1[s_{a,t} > 0] to x

# Step 3: ℓ-level XOR aggregation on the combined stream
y ← []
for j = 0 while o + (j+1)ℓ ≤ |x|:
    append XOR_{r=0}^{ℓ−1} x[o + jℓ + r] to y
return y
```

正文中称 {x_{S,t}} 为 **combined stream**。代码与部分文件名沿用早期术语 `fused_stream.bin`,二者指同一类 multi-asset XOR output。

**ℓ-aggregation 在本论文中有两种实现,需要区分。** §3.1 算法 1 的 ℓ 在价格域上工作:先按 offset 每隔 ℓ 个观测取一次价格,再对相邻采样价格做差分并取符号;这等价于在编码*之前*对窗口内的 price increments 做实数求和,再取 sign 编成 1 bit(linear sum + sign)。本节算法 4 的 ℓ-level aggregation 则在比特域上工作:先得到 multi-asset combined bits,再对连续 ℓ 个 {0,1} bits 做 GF(2) XOR-reduce。两者共用符号 ℓ,但所处管线位置与代数结构不同:单资产 pipeline 使用前者(price-domain aggregation),multi-asset combined pipeline 使用后者(bit-domain XOR aggregation)。

### Output Metrics

本节给出两个对 output bit stream 的统一评价口径:**Throughput**(单位时间产出的 bit 数,关心 bit-production rate 与 waiting time)与 **Min-entropy budget**(单 bit 的 min-entropy 下界,关心 entropy input 是否足以驱动下游 cryptographic conditioning component)。

**Throughput.** 为了把方法学结果与下游应用对齐,本文记录每个被接受的 ℓ\* 上的吞吐量 r_b,定义为该 ℓ\* 下 witness offset 比特流的有效产出速率(bits/s)。在 transaction-time 轴上,r_b 是由市场活动实际驱动的 realized rate,会随资产和月份的 trades/s 变化。在 physical-time 轴上,1/ℓ\* 给出固定 sampling-rate 与每个 candidate bit 的近似等待时间;实际有效 r_b 还要扣除 drop-zero 后没有产出 bit 的秒,因此通常略低于 1/ℓ\*。

**Min-entropy budget.** 本论文采用一个简化的 min-entropy 估计口径,用于判断产出的 bit stream 是否携带足够 randomness 以驱动下游 cryptographic conditioning component。对每条 stream,估计值取 NIST SP800-90B (Turan et al., 2018) non-IID 流程中**两个最常用的 estimator** 中较小者:Most Common Value(MCV)度量 0/1 比例的不均衡,Markov estimator 度量相邻 bit 之间的依赖。选这两个 estimator 的理由是它们覆盖 binary stream 中两类最常见的偏置来源——单 bit 偏置与邻位相关。结果以 per-symbol 下界 h∞ 形式给出,用于确定下游 cryptographic conditioning component 所需的 IKM 字节数。对 binary stream,h∞ 的理论上限是 1 bit/symbol(只有完全独立且均衡的理想流才达到);本论文以 "h∞ 越接近 1 越好" 作为 stream 质量的判断方向。若 deployment 需要 T bits 的 target entropy,则所需输入字节数为 ⌈T / (h∞ × 8)⌉——h∞ = 1 给出下限 ⌈T / 8⌉ 字节,h∞ 离 1 越远所需字节越多。这不构成完整 SP800-90B non-IID 认证(完整流程包含更多 estimator),是本论文 scope 下的简化版本。

---

## Chapter 4 — Experiments

本章先在 Overview(§4.1)中描述实验设置与数据,然后依次给出 Experiment 1 baseline(§4.2)、Experiment 2(§4.3)、Experiments 3-4(§4.4-§4.5)的结果。Password Generator Prototype 作为应用层实现另列 Chapter 5;本章只处理统计实验链条。

### Overview

**Experiments.** 每组实验对应 Ch 1 Research Questions 中的一个或多个研究问题:

- Experiment 1(§4.2)回答 RQ1 的负向部分——*未经聚合的原始数据是否足够随机*?其结论(否)直接动机化 Experiment 2。
- Experiment 2(§4.3)回答 RQ1 与 RQ2:在何种聚合层级 ℓ 上,序列开始通过随机性检验?在哪条轴上聚合更有效?
- RQ3 由三个层次共同回应:Experiment 3(§4.4)扩大 randomness battery 并暴露高阶残留;Experiment 4(§4.5)验证 multi-asset deployable streams;Chapter 5 给出应用层 password generator prototype。

**Common parameters.** 各实验通用的显著性水平为 α = 0.01,`MIN_BIT_COUNT` = 2000,通过率门槛为 0.80;这些参数的定义见 §3.2–§3.4。所有 runner 用 Python + NumPy 实现,结果可由仓库内 `scripts/runner_*.py` 复现。

**Source.** 全部数据来自 Binance Spot 公开 API 的 `aggTrades`(聚合成交)。为确保数据完整性,数据从月度归档 zip 文件下载,而非按日抓取实时流。每条 `aggTrades` 记录提供时间戳、价格、成交量、买卖方向标记;本工作仅使用时间戳和价格。

**Asset universe.** 五种高流动性 USDT 现货对:`BTCUSDT`、`ETHUSDT`、`BNBUSDT`、`SOLUSDT`、`DOGEUSDT`。这五个资产覆盖了广泛的流动性与微观结构区间(Table 4.1),使方法行为能够在不同 trades/s 量级上被检验。

**Period.** 2025 年 1 月至 2026 年 3 月,共 15 个月。Experiment 1 与 Experiment 2 均以月度为单位、覆盖全部 15 个月,因此两个实验共享同一个 (asset, month) cell 单元。下表给出五种资产在 15 个月样本期内 raw trades/s(每条记录 = 一个 maker 被 fill 的事件)与 aggTrades/s(本论文 §3.1 编码 pipeline 实际响应的速率)的中位数与 [p5, p95] 区间。

**Table 4.1 — Per-asset trades/s for the five USDT spot pairs.**

| Asset    | Raw trades/s median | Raw [p5, p95] | aggTrades/s median | aggTrades [p5, p95] | raw/agg median |
|----------|--------------------:|--------------:|-------------------:|--------------------:|---------------:|
| BTCUSDT  |              50.8   |  [25.1, 68.6] |              14.3  |        [8.7, 21.1]  |          3.3   |
| ETHUSDT  |              43.9   |  [31.0, 70.9] |              13.7  |       [10.9, 19.0]  |          2.9   |
| SOLUSDT  |              25.0   |  [14.2, 36.8] |               4.1  |        [2.9, 7.5]   |          5.4   |
| DOGEUSDT |              15.3   |   [9.0, 24.5] |               3.6  |        [1.5, 7.1]   |          4.2   |
| BNBUSDT  |              12.6   |   [8.4, 25.7] |               4.3  |        [2.9, 8.4]   |          2.8   |

> *Note.* 这里的 `/s` 表示 per second。对每条速率(raw trades/s 与 aggTrades/s),表中报告资产跨 15 个月度归档的中位数与 [5th, 95th] 分位区间,样本期为 2025-01 至 2026-03。资产按 raw trades/s 中位数降序排列。

**aggTrades vs raw trades.** aggTrades/s 是 Binance 公开 API 把"同时戳、同价、同方向"的 raw fill 簇合并后的聚合粒度;raw trades/s 通过对每条 aggTrades 的 `last_trade_id − first_trade_id + 1` 求和直接还原,无需重下 raw `trades` 端口,与 LOBSTER message-file 计数(Onofri et al., 2025; Shternshis & Marmi, 2025)同粒度。SOL / DOGE 的 raw/agg ratio 显著高于 BTC / ETH / BNB,反映其单个 taker 单一次性 walk-the-book 时一次吃掉的 maker fill 数更多,与较低的价位 / 较细的 tick 相对粗的成交规模一致。

**Pre-processing.** 对 transaction-time 轴:把月度 `aggTrades` 按时间排序,丢弃零差分 tick。对 physical-time 轴:在排序后按 UTC 秒分桶,空秒前向填充,然后丢弃零差分秒。两条轴上的"零差分剔除"是必要的,因为不同的零值映射(0 或 1)都会引入偏差(详见 §3.1)。

### Experiment 1 — Baseline

Experiment 1 直接回应 RQ1 的负向部分:把"原始 tick 的符号序列直接当随机比特流"作为最朴素 baseline,检验它是否已经能在标准随机性指标下成立。如果答案是 "yes",后续的聚合就是无用功;如果答案是 "no",则需要给出"必须聚合"的*定量*动机。本节的结论是后者。

#### Setup

- **Configuration.** 算法 1 在 ℓ = 1, o = 0 上的特例,即:`aggTrades` 按时间排序 → Δp → 剔除零差分 → 取符号编码为 bit。无聚合,无后处理。
- **Asset universe.** 本论文统一使用的五种 USDT 现货对(`BTCUSDT`、`ETHUSDT`、`BNBUSDT`、`SOLUSDT`、`DOGEUSDT`),覆盖 Table 4.1 全部 trades/s 量级区间。5 资产样本是后文跨资产观察成立的前提:单资产 baseline 看不到活跃度差异驱动的跨资产模式。
- **Window.** 全 15 个月样本,2025-01-01 至 2026-03-31。诊断粒度为月度:每个 (asset, month) cell 一条比特流,共 5 × 15 = 75 个 cell。
- **Diagnostics.** 每条月度比特流上计算:bit 长度 *n*、bits/s、p(1)、Shannon-bias |H − 1|、Monobit p、Runs p、lag-1 自相关 ρ₁、最长 0-run 与 1-run 长度 L_max,以及条件可预测性 battery——Approximate Entropy 与 entropy-predictability 检验 D(adaptive *k* 与 fixed *k* = 2)的 p 值;各检验的定义、参数与出处见 §3.3。其中 bit 长度 *n* 与 bits/s 是关于比特流本身的描述性元数据;lag-1 自相关与 longest run 作为 baseline 诊断扩展引入——前者直接量化短程依赖,后者给"长结构"的密码学风险直觉。ApEn 与 D 用来检验条件结构,避免只用边际熵或 0/1 频率判断原始比特流是否随机。

#### Results

**Table 4.2 — Experiment 1 baseline - per-asset summary.**

| Asset | bps median | 1−H max     | ρ₁ median |  Monobit rejects | Runs rejects | ApEn rejects | D rejects | D(k=2) rejects | L_max max |
|-------|-----------:|------------:|----------:|-----------------:|-------------:|-------------:|----------:|---------------:|----------:|
| BTC   |     10.68  | 1.94 × 10⁻³  |   +0.636 |          15/15   |       15/15  |    15/15     |   15/15   |     15/15      |   12 039  |
| ETH   |      9.56  | 7.93 × 10⁻³  |   +0.745 |          13/15   |       15/15  |    15/15     |   15/15   |     15/15      |   15 899  |
| BNB   |      2.49  | 9.98 × 10⁻⁵  |   +0.366 |          13/15   |       15/15  |    15/15     |   15/15   |     15/15      |    2 069  |
| DOGE  |      2.02  | 1.35 × 10⁻⁵  |   +0.477 |           8/15   |       15/15  |    15/15     |   15/15   |     15/15      |    5 071  |
| SOL   |      1.74  | 2.35 × 10⁻⁶  |   +0.095 |           4/15   |       15/15  |    15/15     |   15/15   |     15/15      |      792  |

> *Note.* 每行汇总 15 个 (asset, month) cell(2025-01 至 2026-03):bit 产出速率(bps)中位数、Shannon-bias 最大值(1−H 跨 15 月最大值)、lag-1 自相关中位数、Monobit / Runs / ApEn / D(adaptive *k*) / D(*k* = 2) 在 α = 0.01 下拒绝的月数(共 15 月)、跨 15 月观察到的最长 0-run 或 1-run 长度 L_max。行按 bps median 降序排列。Per-(asset, month) 分布见 Figure 4.1。D(adaptive *k*) 的 *k* = ⌊0.5 log₂ n⌋ 在本样本上落在 10–12。

**Figure 4.1 — Experiment 1 baseline · per-(asset, month) distributions.** 分四个 panel 展示 75 个 cell 的分布:bps boxplot、ρ₁ boxplot(标零线)、Monobit −log₁₀(p) 的 ECDF(标 α = 0.01 阈值)、L_max 直方图。文件:`data/processed/experiment1/per_asset_distributions.png`,thesis 中复用为 `thesis/figures/exp1_per_asset_distributions.png`。

75 个 baseline cell 的边际分布整体接近平衡(1 − H 全部 ≤ 7.93 × 10⁻³,低活跃资产可低至 ~10⁻⁵ 量级)。但 Shannon-bias 只描述 0/1 比例,不能检验相邻依赖或更长结构;因此它仅作为汇总指标,不进入接受判据。下面按证据链给出五条观察。

**条件可预测性与 Runs 在每个 cell 上拒绝。** Entropy-predictability 检验 D(adaptive *k* 与 *k* = 2)检验"下一个 bit 是否依赖于历史";Approximate Entropy 检验短模式复杂度;Runs 检验相邻 bit 的游程结构。四项检验在全部 75 个 cell 上一律以 α = 0.01 拒绝——五个资产均为 15/15(Table 4.2),其中 73 个 Runs p 值下溢到 0。与 Monobit 不同,这些检验不只依赖边际频率偏离 0.5:即便 SOL 这类 p(1) 紧贴 0.5、Monobit 仅在 4/15 月拒绝的资产,D、ApEn 与 Runs 仍在全部 15 月拒绝。这组结果是"raw tick 流非随机"最直接、也最不依赖边际假设的证据。

**Monobit 单独使用会漏检。** 75 个 cell 中有 22 个不被 Monobit 拒绝(α = 0.01):SOL 11、DOGE 7、BNB 与 ETH 各 2、BTC 0;但上一条显示,这些 cell 并没有通过条件可预测性或 Runs 层面的随机性检查。Monobit 不拒绝主要集中在低 bps 资产,原因是其 p(1) 更接近 0.5,且月度比特流更短、Monobit 对小幅边际偏离的功效更低。因此,"Monobit 拒绝数随 bps 递增"不应被解释为低 bps 资产更随机,而是说明边际频率检验本身不足以判定随机性。

**lag-1 自相关给出一阶依赖的诊断信号。** 5 个 per-asset median 均为正:ETH +0.745、BTC +0.636、DOGE +0.477、BNB +0.366、SOL +0.095(Table 4.2)。其量级与 bps 大体同向,但并非严格单调;在 per-month 层面(Figure 4.1 右上),BTC、ETH、DOGE、BNB 的分布稳定在零线之上,SOL 则紧贴零线。这一结果的作用不是把"活跃度决定自相关"作为主结论,而是给 raw tick 流的非独立性提供直观诊断:即便边际频率接近 0.5,相邻 bit 仍呈现正相关。该模式与持续同向 order-flow 一致——大 taker 单 walk-the-book 时可能连续多档同向成交,trade-sign long-memory(Lillo & Farmer, 2004)也会累积出正自相关。因此,这里的 lag-1 自相关主要作为 raw tick 流短程依赖的诊断指标。

**最长 run 给出结构性密码学风险信号。** Table 4.2 的 L_max 列给出每个资产 15 月中的最大 run 长度:BTC 12 039、ETH 15 899、DOGE 5 071、BNB 2 069、SOL 792。i.i.d. 随机期望 E[L_max] ≈ log₂ n,本论文月度比特流 n ~ 10⁶ 至 4 × 10⁷,该期望约在 20 至 25 之间。每个观测到的 L_max 都比该 baseline 高 2–3 个数量级。L_max 是 15 月的极值统计、本身波动较大,与 bps 的顺序并不严格一致(ETH 高于 BTC、DOGE 高于 BNB);但"远高于 i.i.d. 期望"这一点对五个资产无一例外。因此,最长 run 不作为单独接受判据,而是给 raw tick 流作为密码学随机源的失败模式提供直观解释:若 seed 或 password 的取样窗口落在这类长 run 内,输出会退化为长段全 0 或全 1。

**比特产出速率给出后续吞吐量上界。** Per-cell bits/s 区间从 0.68(DOGE,2026-03)到 15.52(BTC,2026-02);per-asset 中位数依次为 BTC 10.68、ETH 9.56、BNB 2.49、DOGE 2.02、SOL 1.74 bps(Table 4.2)。前两位与 Table 4.1 的 raw trades/s 顺序一致(BTC > ETH),但下三者反转:SOL 虽 raw trades/s 高于 BNB / DOGE,其 zero-delta ratio 是五者中最高(15 月 median 约 0.58),drop-zero 之后剩余 bit 事件比 BNB(zero-delta ratio ≈ 0.44)更少,使 SOL 在 bps 排序中位列最末。baseline 吞吐量因此不仅取决于 trades/s,也取决于 per-asset 的 zero-delta ratio,并构成任何聚合后吞吐量估计的上界。

#### Implications

Experiment 1 给出一个**负向但定量**的结论:直接把 raw tick 的符号序列当 RNG 不成立。虽然边际频率接近平衡,但 Runs 与条件可预测性 battery 在 75/75 个 (asset, month) cell 上一致拒绝;lag-1 自相关与最长 run 进一步说明失败来自相邻依赖与长结构,而不是单纯的 0/1 比例偏移。Monobit 的漏检则说明,后续实验不能只依赖边际频率检验。这一结论为 Experiment 2 提供三个直接锚点:

(i) **聚合的必要性。** ℓ = 1 的 raw tick 流在 Runs、ApEn 与 D 检验下全量被拒绝,因此 Experiment 2 必须通过聚合来降低条件依赖,而不是在原始符号流上寻找可接受窗口。

(ii) **1 阶残留结构作为对照指标。** lag-1 自相关在五个资产上均为正,但量级跨度较大:BTC / ETH / DOGE / BNB 中位数在 +0.37 至 +0.75 之间、Per-month 分布稳定在零线之上,raw tick 符号流上存在稳定的一阶依赖;SOL 中位 +0.095、紧贴零线,属边界情形。因此五资产间并非严格单调,只是粗粒度上与 bps 同向。Experiment 2 因此把 lag-1 自相关作为比较 transaction-time 与 1-second bar 两条聚合轴的对照指标(SOL 作为低信号边界 case 一并对照),后续实验不预设该结构会被完全消除,而是检验不同聚合轴能在多大程度上缓解这一短程依赖。

(iii) **吞吐量上界。** 75 个月度 cell 的 baseline bits/s 量级(1 至 16 bps)是 §3.7 throughput metric 与 Exp 3 entropy-rate 讨论的天花板;任何后续聚合都会在这个上界之下换取更强的随机性诊断表现。

### Experiment 2 — Aggregation

Experiment 2 直接回应 RQ1 的正向部分:Exp 1 已经证明 raw tick 不可用,所以聚合是必要的;Experiment 2 在 transaction-time 与 physical-time 两条轴上,系统地检验"聚合到多深"才使序列通过 α = 0.01 下的随机性检验。

本节按下面四步推进;每一步的"问题 / 不足"是下一步的引子。

1. **Transaction-time single offset**：固定起始 offset o = 0,作为 pilot step 先估计可通过的 ℓ\* 量级,但不作为最终接受判据(§4.3.2)。
2. **Transaction-time all-offset strict gate**：进入完整 all-offset 构造,检验多个 offset 上的稳健性(§4.3.3)。
3. **Transaction-time all-offset relaxed gate**：放松 offset 覆盖规则,检验 strict gate 是否排除了过多仍可用的 cell(§4.3.4)。
4. **Physical-time 1-second bars**：切换到 physical-time 轴,检验按秒采样时短程依赖是否改变(§4.3.5)。

§4.3.6 把两条轴的结论汇总,给出后续实验配置的依据。

#### Setup

下面的设置贯穿 §4.3.2 至 §4.3.5,各节内只额外说明 ℓ 网格的差异。

- **Asset universe.** 与 Exp 1 一致的 5 个 USDT 现货对(BTCUSDT、ETHUSDT、BNBUSDT、SOLUSDT、DOGEUSDT,详 §4.1)。
- **Window.** 与 Exp 1 一致的 15 月样本(2025-01 至 2026-03),诊断粒度为 (asset, month) cell,共 5 × 15 = 75 个 cell。
- **Encoding.** 算法 1(§3.1):在 transaction-time 轴上以"成交笔数"为 ℓ 的单位;在 physical-time 轴上先通过 §3.5 的 1-second bar pipeline 将价格序列转换为 per-second close-price,ℓ 的单位变为"秒数"。drop-zero 处理在两条轴上保持一致。
- **All-offset construction.** §3.2:对每个 ℓ,构造 ℓ 条 offset 比特流并独立检验。§4.3.2 先采用固定 offset 的 pilot 版本(o = 0,只一条流);§4.3.3 起进入完整 all-offset。
- **Acceptance gates.** 主接受规则使用 D(adaptive *k*) + Monobit:single offset 要求两项 *p* 值均 ≥ α;all-offset strict gate 要求两项通过率均 ≥ 0.80;relaxed gate 是 §3.4 中定义的 heuristic 版本。Runs、D(*k* = 2)、ApEn 与 Shannon bias 仍被记录为辅助诊断,其中 Runs 在 §4.3.5 中被显式加入 +Runs gate。
- **ℓ grid.** §4.3.2 / §4.3.3 取 50 至 2000、步长 25;§4.3.4 取 10 至 2000、步长 2;§4.3.5 取 10 至 600、步长 1。

#### Transaction-Time: Single Offset

Single offset 固定起始偏移 o = 0:每个 ℓ 只构造一条比特流,先观察聚合深度与通过性的基本关系;selected ℓ\* 是使 D(adaptive *k*) 与 Monobit 同时给出 *p* ≥ α(α = 0.01)的最小 ℓ。ℓ 网格取 50 至 2000、步长 25,跨 5 资产 × 15 月共 75 个 (asset, month) cell。

**Figure 4.2 — Single-offset −log₁₀(*p*) vs ℓ。** Figure 4.2(a) 展示 2025 Q1,Figure 4.2(b) 展示 2026 Q1(Q5);每张图按资产 × 月份排列,显示 D 与 Monobit 的 −log₁₀(*p*) 如何随 ℓ 增长而下降。水平红线为 α = 0.01 阈值,完整 15 月 selected ℓ\* 见 Appendix Table A.1。

**Table 4.3 — Single-offset gate · per-asset summary。** 5 行(每资产一行),跨 15 个月度 cell 汇总。

| Asset | n_pass | selected ℓ\* median (over n_pass) | selected ℓ\* range |
|-------|:-----:|----------------------------------:|---------------------:|
| BTC   | 13/15 |                              1300 |           [900, 1975] |
| ETH   | 15/15 |                               725 |           [525, 1575] |
| BNB   | 15/15 |                               275 |            [175, 850] |
| SOL   | 15/15 |                               225 |            [100, 750] |
| DOGE  | 15/15 |                               225 |             [75, 825] |

> *Note.* n_pass = 该资产在 15 月中 single-offset gate 返回 acceptable 的月份数;selected ℓ\* median 与 range 只在 acceptable 月份上计算。行按 selected ℓ\* median 降序排列。完整 per-(asset, month) 表见 Appendix Table A.1。

**Selected ℓ\* 呈现粗粒度的活跃度分层。** Table 4.3 显示,BTC 与 ETH 在 [50, 2000] 区间内需要明显更深的聚合,而较低活跃的三个资产在 ~200–300 即可触达阈值。这与 Onofri et al. (2025) Case 2 在 8 只美股 + 1 ETF 上报告的"trades/s 越高、所需 ℓ 越大"为同向关系;但这里的结论只应理解为粗粒度分层,不是五个资产之间严格单调的排序。

**Single offset 只给出初始估计,不是最终接受方案。** 在 2025-01 与 2025-08 两个月,BTC 在整个 [50, 2000] 网格上都不能让 D 与 Monobit 同时通过,完整结果见 Appendix Table A.1。这说明固定 o = 0 可以给出 ℓ\* 的大致量级,但不能说明其他起始 offset 是否也有同样表现;这些失败也不能仅用单月 trades/s 高低解释。Single offset 因此只作为 pilot diagnostic。

**下一步问题是结果是否在多个 offset 上稳定。** 对固定 ℓ 而言,all-offset 构造有 ℓ 个可能起始 offset。o = 0 通过,并不意味着另外 ℓ − 1 条 offset 流也通过。若结果高度依赖起点,就不能只因为一个 offset 成功而接受该 cell。§4.3.3 因此把 fixed-offset 诊断升级为完整规则:至少 80% 的 offset 必须同时通过。

#### Transaction-Time: All-Offset Strict Gate

§4.3.3 把判据从"o = 0 单条通过"升级为 all-offset 框架下的 strict gate(算法 2,§3.4):对每个 ℓ,构造 ℓ 条 offset 比特流,**要求其中 ≥ 80% 同时在 D(adaptive *k*)与 Monobit 上给出 *p* ≥ α(α = 0.01)**;selected ℓ\* 取使该判据为真的最小 ℓ。ℓ 网格沿用 50 至 2000、步长 25。

**Figure 4.3 — All-offset strict gate · pass-rate vs ℓ。** Figure 4.3(a) 展示 2025 Q1,Figure 4.3(b) 展示 2026 Q1(Q5);每个 panel 给出某资产某月份下 D 与 Monobit 的 offset 通过率。水平红线为 0.80 strict gate 阈值,完整 15 月 selected ℓ\* 见 Appendix Table A.2。

**Table 4.4 — All-offset strict gate · per-asset summary。** 5 行(每资产一行),跨 15 个月度 cell 汇总。

| Asset | n_pass | selected ℓ\* median (over n_pass) | selected ℓ\* range |
|-------|:-----:|----------------------------------:|---------------------:|
| BTC   |  7/15 |                            1500 |          [1225, 1825] |
| ETH   | 13/15 |                             975 |           [650, 1900] |
| DOGE  | 15/15 |                             375 |             [75, 1075] |
| SOL   | 13/15 |                             350 |             [150, 650] |
| BNB   | 15/15 |                             350 |             [200, 1025] |

> *Note.* n_pass = 该资产在 15 月中 strict gate 返回 acceptable 的月份数;selected ℓ\* median 与 range 只在 acceptable 月份上计算。行按 selected ℓ\* median 降序排列。完整 per-(asset, month) 表见 Appendix Table A.2。

**Strict gate 整体压紧 ℓ\*,粗粒度排序与 single offset 一致。** 与 §4.3.2 single offset 比较,strict gate 把每个资产的 per-asset selected ℓ\* median 整体推高:BTC 1300 → 1500、ETH 725 → 975、BNB 275 → 350、DOGE 225 → 375、SOL 225 → 350(两组 median 各自在其有 acceptable ℓ 的月份上计算,月份基数不同,故此对比反映的是量级趋势而非逐月差值)。这是要求 80% offset 同时通过(而非单条)所付出的代价——多 offset 的 joint confirmation 等价于一个更严的统计 bar,需要更深的聚合才能整体迁出拒绝区。资产之间的粗粒度关系仍是 BTC 与 ETH 明显高于 BNB / SOL / DOGE,但低三者之间不应解释为严格单调排序。

**BTC 在本数据集中扮演高活跃 outlier 的角色:8/15 月份在 ℓ ≤ 2000 网格内无解。** Single offset 下 BTC 只有 2 个月(2025-01、2025-08)失败,strict gate 下升至 8 个月——同一资产、同一聚合范围,80% offset 共同确认的代价主要由它承担。这一失败模式不能由单月 raw trades/s 干净解释:同为高活跃资产的 ETH 在 strict gate 下保持 13/15 通过,而 BTC 的失败月份跨低 / 高活跃月份均有。ETH 与 SOL 各有 2 个月 strict gate 失败,合计 12 个 cell 失效,strict gate 整体接受率为 63/75 = 84%。

**Strict gate 选中的流仍系统性地过不了 Runs。** 需要强调:strict gate 的主判据只含 D(adaptive *k*) + Monobit。被它选中的 63 个 acceptable cell 中,有 38 个的 Runs 通过率低于 0.05(统计口径见 Appendix Table A.2 说明)——即在这些 cell 的 selected ℓ\* 上,几乎每一条 offset 流都被 Runs 拒绝;D(*k* = 2) 通过率呈现同样的模式。换言之,"strict gate 通过" ≠ "一阶结构被消化",它只保证 adaptive-*k* 的 D 与 Monobit 两项达标。这一残留是 transaction-time 轴的稳定病征,也是后续比较 physical-time 轴的动机之一。

**Strict gate 留下两条实际问题。** 第一,BTC 在 8 个月里完全无 acceptable ℓ ≤ 2000,说明 80% offset 同时通过的要求对高活跃资产可能过严。第二,selected ℓ\* 的 month-to-month range 较宽,粗网格也限制了估计精度。§4.3.4 因此尝试 relaxed offset-coverage gate,并把 ℓ 网格细化到 step = 2。

#### Transaction-Time: All-Offset Relaxed Gate

§4.3.4 在 all-offset 框架下把判据从 strict gate 换成 §3.4 定义的 relaxed gate。主文使用 (F, f) = (3, 0.03),ℓ 网格细化为 10 至 2000、步长 2。

**Figure 4.4 — All-offset relaxed gate · n_pass(ℓ) + selected ℓ\*。** Figure 4.4 把 2025 Q1 与 2026 Q1(Q5)放在同一张图中,每个 panel 显示 5 个资产的 n_pass(ℓ),即同时通过 D 与 Monobit 的 offset 数。红线为 relaxed gate 阈值,标记点给出 selected ℓ\*;完整 15 月结果见 Appendix Table A.4,Bonferroni 对照见 Appendix Table A.5。

**Table 4.5 — All-offset relaxed gate · per-asset summary。** 5 行,跨 15 个月度 cell 汇总。

| Asset | n_pass | selected ℓ\* median | selected ℓ\* range |
|-------|:------:|--------------------:|---------------------:|
| BTC   | 15/15  |                1150 |          [870, 1750] |
| ETH   | 15/15  |                 556 |           [400, 1194] |
| BNB   | 15/15  |                 212 |             [128, 464] |
| SOL   | 15/15  |                 180 |              [66, 596] |
| DOGE  | 15/15  |                 156 |              [48, 594] |

> *Note.* n_pass = 该资产在 15 月中 relaxed gate 返回 acceptable 的月份数;selected ℓ\* median 与 range 在全部 15 月上计算。行按 selected ℓ\* median 降序排列。完整 per-(asset, month) 表见 Appendix Table A.4。

**Relaxed gate 把覆盖率从 strict 的 63/75 推到 75/75。** Strict gate 在 BTC 8 个月、ETH 2 个月、SOL 2 个月共 12 个 cell 上失败(§4.3.3 Table 4.4);relaxed gate 在全部 75 cell 上都找到 acceptable ℓ\*。BTC 此前 strict 下无 ℓ ≤ 2000 通过的 8 个月,relaxed 下均找到 ℓ\* ∈ [998, 1750]——仍在 [50, 2000] 网格内,只是 strict 的 80% bar 对它们过严。这一观察直接回应 §4.3.3 末尾给出的 practical coverage problem。

**Selected ℓ\* 整体压低,但粗粒度资产分层保持不变。** 逐资产对比 per-asset selected ℓ\* median(strict 在其有 acceptable ℓ 的月份、relaxed 在全部 15 月各自计算),relaxed gate 把每个资产的 median 都拉低:BTC 1500 → 1150、ETH 975 → 556、BNB 350 → 212、DOGE 375 → 156、SOL 350 → 180,降幅约 23%(BTC)至 58%(DOGE)。两组 median 月份基数不同(strict 有 12 个失败 cell、relaxed 全部 75 个 cell 成功),故降幅是量级口径而非逐月差值。Relaxed gate 等价于一条更松的 bar,因此每个资产都用更小的 ℓ 通过。资产层面仍呈现 BTC 最高、ETH 次之、BNB / SOL / DOGE 同量级的粗粒度结构。

**Relaxed gate 的 accepted-cell 描述性吞吐量高于 strict。** 在 accepted cell 上统计,selected / witness stream 的中位 bit rate 从 strict 的约 0.012 bps 提高到 relaxed 的约 0.021 bps,约 1.8×。这一差异主要来自 relaxed gate 选出的 ℓ\* 整体更低;但它只是两种 gate 在本实验 cell 集合上的描述性比较,不等同于多资产部署吞吐。Relaxed gate 的优势因此应理解为 coverage 更完整、per-cell bit rate 更高;代价是 robustness 论证从 "80% 的 offset 同时通过" 退到 "至少 3 条同时通过"(后者在论文中明确标为 heuristic 而非形式校正)。

**Bonferroni / Šidák 对照给出更小的 ℓ\*。** 作为方向性对照,Bonferroni / Šidák 版本在 2025 Q1 给出系统性更小的 selected ℓ\*。这与 §3.4 的判断一致,因此不作为主判据;完整结果见 Appendix Table A.5。

§4.3.4 至此把 transaction-time 轴上的方法链条收尾:single offset → strict gate → relaxed gate 三步,后两步在 offset stability、coverage 与 bit rate 之间做权衡。Relaxed gate 给出 75/75 cell 全部 acceptable,但它仍是一条 heuristic,不构成更强的统计保证。

与此同时,transaction-time 轴仍留下一个重要问题:*D*(*k* = 2) / Runs 在 selected ℓ\* 附近几乎普遍拒绝,短程依赖是否由采样轴放大仍需检验。§4.3.5 因此切换到 physical-time 轴(1-second bar)。

#### Physical-Time: 1-Second Bars

§4.3.5 在 physical-time 轴上重做 all-offset 接受循环。与 transaction-time 不同,这里先把价格序列转换成 per-second close-price,再以"秒数"为 ℓ 的单位做聚合(详 §3.5)。ℓ 网格取 10 至 600、步长 1;gate 仍采用 80% pass-rate 框架。Base gate 在 1-second bar 上已经给出 70/75 覆盖,因此不再引入 relaxed gate。

**Figure 4.5 — 1-second bar gate · pass-rate vs ℓ。** Figure 4.5(a) 展示 2025 Q1,Figure 4.5(b) 展示 2026 Q1(Q5);格式与 Figure 4.3 相同,但 ℓ 的单位从"成交笔数"变为"秒"。水平红线为 0.80 pass-rate 阈值,完整 15 月 selected ℓ\*(三档 gate)见 Appendix Table A.6。

**Table 4.6 — 1-second bar gate · per-asset summary。** 5 行(每资产一行),跨 15 个月度 cell 在 base(D + Monobit)与 +Runs 两档 gate 下汇总。

| Asset | base n_pass | base ℓ\* median (sec) | +Runs n_pass | +Runs ℓ\* median (sec) |
|-------|:----------:|----------------------:|:------------:|------------------------:|
| BNB   |   14/15    |                    84 |    14/15     |                     101 |
| BTC   |   15/15    |                    62 |    15/15     |                      92 |
| DOGE  |   14/15    |                    33 |    13/15     |                      53 |
| ETH   |   12/15    |                    65 |    8/15      |                      56 |
| SOL   |   15/15    |                    54 |    12/15     |                      59 |

> *Note.* 偶数样本量的 ℓ\* median 取两中间值平均后四舍五入(BNB base 83.5→84、ETH base 64.5→65、ETH +Runs 55.5→56、SOL +Runs 58.5→59)。完整 per-(asset, month) 表(含 +Runs + ApEn)见 Appendix Table A.6。

**1-second bar base gate 在 physical-time 轴上覆盖 70/75。** Base gate 在 1-second bar 上给出 70/75 acceptable cell,说明换轴后仍能在多数 cell 上找到秒级 ℓ\*。失败集中在 ETH、BNB 与 DOGE 的少数月份;seconds-with-trades coverage 能解释其中一部分失败,但不是唯一因素。

**+Runs gate 把覆盖从 70/75 拉到 62/75,是 1-second bar 轴上的关键独立性结果。** 为做同口径对照,Runs 也被加入 transaction-time strict gate 与 1-second bar gate。Transaction-time strict+Runs 只覆盖 48/75(Appendix Table A.3),而 1-second bar +Runs 覆盖 62/75;进一步加入 ApEn 后仍为 62/75。这个对比说明,transaction-time 下难处理的一阶残留,在 physical-time 轴上得到明显缓解。

**该独立性改善与聚合轴有关。** 同一份 aggTrades 数据在 transaction-time 轴上仍保留较强一阶残留,但在 physical-time 轴上多数 cell 得到缓解。这一对照不支持"一阶残留完全来自源数据且不可缓解"的解释;更合理的理解是,按成交笔数等距采样会把短时间内的同向 order-flow 浓缩到相邻 bit 中,而 1-second bar 把这种局部集中性稀释开。这与 Exp 1 中 lag-1 自相关为正、且量级与活跃度大体同向的诊断相一致。

**Physical-time 轴更容易解释为 wall-clock waiting time。** Transaction-time 轴上的吞吐量随当月 trades/s 浮动;physical-time 轴上,ℓ\* 以秒为单位,可直接解释为产出下一个 candidate bit 前大约需要等待多久。由于 drop-zero 仍会过滤零差分秒,实际 bit/s 会略低于 1 / ℓ\*,但量级基本一致。Table 4.6 的 ℓ\* median 对应的描述性速率大约落在 0.01–0.03 bps 区间。加入 Runs 后覆盖率下降,在部分资产或月份上也会带来更长等待时间。

#### Implications

Experiment 2 的主要作用是为后文 pipeline 选择聚合轴。两条轴都能产生 accepted cells,但实际含义不同:transaction-time 按成交笔数聚合,更适合作为统计对照;physical-time 的 ℓ 以秒为单位,更容易在后文解释为等待时间。§4.3.6 将结果收束为四点。

(i) **应采用 physical-time 作为主聚合轴。** Transaction-time 的 bit rate 随 trades/s 波动,更适合作为统计构造和补充对照。而 Physical-time 的 ℓ 以秒为单位,selected ℓ\* 可以直接解释为 wall-clock sampling schedule 与每个 candidate bit 的近似等待时间。

(ii) **Physical-time 更适合作为扩展检验的输入配置。** 在 +Runs 口径下,transaction-time strict gate 的覆盖率从 63/75 跌到 48/75(within-axis 损失 24%),physical-time base gate 从 70/75 跌到 62/75(within-axis 损失 11%);进一步加入 ApEn 后仍为 62/75。**Within-axis 的 coverage 损失幅度在 transaction-time 上显著更大**,这说明 transaction-time 下的 Runs / *D*(*k* = 2) 残留至少部分由采样轴放大。因此,后续 entropy-rate 分析、补充 NIST 子检验与 TestU01 sanity check 优先在 physical-time 选出的 bit streams 上进行。

(iii) **Transaction-time relaxed gate 保留为补充配置。** 它证明成交笔数轴上在放松 offset-coverage rule 后也能达到完整覆盖;但该规则是 heuristic,且吞吐随市场活跃度变化,因此不作为主配置。Experiment 3 也不把它作为 fallback:审计对象是 1-second bar +Runs gate 本身的覆盖边界。1-second bar +Runs gate 下失败的 13 个 cell 因此作为该 gate 边界的证据保留,不进 Experiment 3 样本。

(iv) **吞吐量只作为量级锚点。** Experiment 2 中 selected cell 的 per-cell bit rate 大致落在 10⁻² bps,说明更强的随机性诊断会带来更低的 bit emission rate。

---

### Experiment 3 — Extended Test Battery

Experiment 2 在 1-second bar 轴上用一个小型 gate——D(adaptive *k*)、Monobit、Runs 三项的 offset 通过率均 ≥ 0.80——为每个 (asset, month) cell 选出聚合层级 ℓ\*,在 15 月样本上共接受 62 个 cell。该 gate 足以*选出*一个聚合层级,却不保证"被选中的流在一个更完整的检验电池下也随机"。Experiment 3 因此不是证明这些流完美随机,而是审计 §4.3.5 的 gate 覆盖边界:它探到了哪些结构,又漏掉了哪些。

具体做法是:把这 62 个 cell 送进 §3.3 定义的 29-sub-test universe——它在 §4.3 已计算的 core tests 之外加入 NIST SP800-22 与 TestU01 Alphabit,因此提供 cross-battery 校验。Experiment 3 的主样本固定为 +Runs gate:base gate(D + Monobit)只是 §4.3 为展示选层流程报告的中间诊断配置,§4.3.5 已显示不把 Runs 纳入 gate 会让明显一阶结构继续进入候选流。

#### Setup

- **Sample.** 62 个 (asset, month) cell——即 Experiment 2(§4.3.5)1-second bar +Runs gate 在 15 月样本上接受的全部 cell。Experiment 2 下失败的 13 个 cell 不进入 Experiment 3:样本即为 62,不做救援。Experiment 3 不重新选 ℓ\*,而是在这些已接受 cell 的 selected ℓ\* 上做审计。
- **Battery.** 沿用 §3.3 定义的 29-sub-test universe。Exp 2 core 中只有 D adaptive-*k*、Monobit、Runs 三项构成 §4.3.5 的 +Runs gate;D(*k* = 2) 与 ApEn 只是诊断量,不参与选层。短长度上 TestU01 Alphabit 会 length-skip,相应 (cell, sub-test) 标 NOT_RUN,不进入 admissible 分母。
- **Acceptance.** 与 Experiment 2 一致:对每个 (cell, sub-test),若 ≥ 80% 的 valid offset 给出 *p* ≥ α = 0.01,则该 (cell, sub-test) 记为 pass;per-asset 汇报"通过月份数 / admissible 月份数"。
- **Sanity check.** 主跑之前,先在 `/dev/urandom` 随机数据上对每个 sub-test 做 *K* = 1000 次 IID null trial,覆盖 6 个长度档(5K / 10K / 25K / 50K / 100K / 200K bit,跨度对齐 cell 实际可达的 bit 长度范围)。Sanity check 用来标记每个 (sub-test, bracket) 是否进入主跑分母:通过者计入 admissible;若某个 (sub-test, bracket) 的观测 type-I 超过 sanity 阈值,则在主跑中标 INVALID;若因长度不足无法运行,则标 NOT_RUN。

#### Results

**Sanity check 显示扩展电池整体可用。** 29 × 6 = 174 个 (sub-test, bracket) 中,164 个通过 sanity(观测 type-I ≤ 0.02 = 2α)。该阈值作为宽松 sanity filter,用于剔除明显失配的短长度配置,而不是重新校准各检验的显著性水平。[^sanity-threshold] 另有 1 个标为 INVALID(LongestRun 在 5K 档 type-I = 0.122,序列过短,与 NIST 对 LongestRun 的 *N* ≥ 6272 bit 长度建议一致);9 个因不满足检测长度要求而标为 NOT_RUN。下文所有通过率的分母只统计 sanity-admissible 的 (sub-test, bracket)。

[^sanity-threshold]: 设 2α 而非 α 本身,是为容纳 *K* = 1000 null trials 下的二项采样波动。在 α = 0.01 下,即使 sub-test 实现正确,观测 type-I 的二项 99% CI 上端约为 0.018(Clopper & Pearson, 1934),因此取 0.02 作为 sanity 阈值,略宽于此。

**Figure 4.6 — Experiment 3 · per-asset sub-test pass rates.** 展示 29 个 sub-test 在五个资产上的通过率(每个单元格为该 (asset, sub-test) 通过的月份比例)。文件:`data/processed/experiment3/runs-gate/figures/pass_rate_per_asset.png`。

**绝大多数 sub-test 在扩展电池下依然通过。** D(adaptive *k*)、Monobit、Runs、DFT 在五个资产上 admissible 范围内均为 100% 通过。前三者本就是 Experiment 2 的 +Runs gate;DFT(spectral 类)在 100% 通过,是一个 gate 之外的新确认。其余 sub-test 大多在多数月份上通过(Figure 4.6)。换言之,Experiment 2 选出的聚合层级在更宽的电池下大体稳健。

**Table 4.7 — Experiment 3 · 三个跨资产失败的 sub-test。**

| Sub-test               | Battery          |  BTC  | ETH | BNB  | SOL  | DOGE |
| ---------------------- | ---------------- | :---: | :-: | :--: | :--: | :--: |
| Serial *m*             | NIST SP800-22    | 8/15  | 3/8 | 9/14 | 4/12 | 6/13 |
| MultinomialBitsOver L4 | TestU01 Alphabit | 8/15  | 3/8 | 8/14 | 3/12 | 6/13 |
| Approximate Entropy    | Exp 2            | 11/15 | 2/8 | 8/14 | 9/12 | 9/13 |

> *Note.* 单元格为"通过月份数 / admissible 月份数"。Admissible 月份数因资产而异(BTC 15、ETH 8、BNB 14、SOL 12、DOGE 13),即 Experiment 2 接受的 cell 数。行按来源 / battery 分组,不是按失败率排序。

**三个高阶 sub-test 暴露出剩余弱点。** Table 4.7 显示:Serial *m*(NIST)的 per-asset 通过率在 33%(SOL,4/12)至 64%(BNB,9/14)之间,总计 30/62,是 NIST SP800-22 扩展项里最弱的一项;若把口径放到全部 sub-test,TestU01 Alphabit 的 MultinomialBitsOver L4 还要更弱一档(25%–57%,总计 28/62);ApEn 也有清晰失败,尤其 ETH 低至 2/8。这三项都检验"高阶 / 多符号结构"——它们的失败说明,Experiment 2 的小型 gate 选出的流虽通过了短程依赖检验,却仍残留 gate 探不到的高阶结构。

**两套独立测试库给出一致的失败模式。** 这是 Experiment 3 最关键的观察:Serial *m* 来自 NIST SP800-22,MultinomialBitsOver L4 来自 TestU01 Alphabit——两个独立开发的测试库——它们呈现非常接近的跨资产失败模式(per-asset 通过率几乎逐一对应)。因此该残留结构不是某一个测试库的实现 quirk,而是被两套独立电池一致确认的真实信号。

**base vs +Runs 敏感性回溯印证了 Experiment 2 的 gate 选择。** 作为反事实敏感性分析,Experiment 2 早期 base gate(D + Monobit)选出的 70 个 cell 被取出,并在其对应 selected ℓ\* 上运行同一扩展电池。与 +Runs 主样本相比,base-selected streams 在 D(*k* = 2) 与 Runs 上明显恶化:二者跨资产平均通过率从 +Runs 下的近 100% 跌至约 29%(BTC / ETH / SOL / DOGE 低至 ~20%,仅 BNB 较高)。这说明 Runs 加入主 gate 不是任意收紧,而是为了阻止一阶结构继续进入候选流。

#### Implications

Experiment 3 给出一个细化的结论:单资产聚合(§4.3)**显著压低**了**短程**依赖——D(adaptive *k*)、Monobit、Runs、DFT 在扩展电池下一律通过,D(*k* = 2) 也只在 62 个 cell 中失败 1 个(BTC,14/15)——但留下了一层**高阶残留结构**,只有 Serial 与多符号类 sub-test 探得到,且这一残留被 NIST 与 TestU01 两套独立电池一致确认。

这直接动机化 Experiment 4:如果单个资产的聚合流仍带残留结构,那么把多个资产的比特流组合起来——按 piling-up 引理,多条带偏置的流 XOR 之后趋于均匀——应当能清掉单资产清不掉的残留。Experiment 4 检验 multi-asset XOR combination 能否做到这一点,以及它在吞吐量上的代价。

---

### Experiment 4 — Multi-Asset XOR Combination

Experiment 3 的结论是:单资产聚合已经显著压低短程依赖,但 Serial、ApEn 与 Alphabit 的多符号检验仍暴露出高阶残留。Experiment 4 因此把问题从"单个资产是否足够随机"推进到"多个资产组合后,这些残留能否被进一步削弱,以及削弱需要付出多少吞吐量代价"。

Experiment 4 回应 RQ3 的第二层条件:multi-asset combination 是否能在 out-of-sample validation 中同时给出更强的 statistical robustness、可接受的 throughput,以及足以支撑 entropy input 的 min-entropy estimate。**主要发现是 n ∈ {2, 3, 5} 可部署,而 n = 4 暴露出 calibration 选出的固定参数在 validation 上系统性失败——后者本身构成一项独立的方法学发现,因此 §4.5 把 n = 4 作为中心议题处理。**

直觉来自 piling-up 引理(Matsui, 1994;详见 §3.6):若若干输入比特近似独立,则它们的 XOR 会把边际偏差推向 0.5。这里的重点不是把该引理当成完整安全证明,而是把它转化成一个可验证的工程假设:multi-asset XOR combination 是否能在 out-of-sample 月份上改善 Experiment 3 暴露出的单资产残留。

#### Setup

- **Input.** 沿用 §3.6 定义的 multi-asset combination 与 ℓ-level XOR aggregation。Experiment 4 在 BTC、ETH、BNB、SOL、DOGE 五个资产的 1-second sign-bit 流上实例化该算子;文件名中仍保留 `fused_stream.bin`,但正文术语统一称 combined stream。
- **Calibration / validation split.** Calibration 使用 2025-01 至 2025-09 共 9 个月;validation 使用 2025-10 至 2026-03 共 6 个月。Calibration 只用于选择 subset、ℓ\*_n 与 witness offset;validation 固定这些选择,不再调参。
- **Subset universe.** 对每个 n ∈ {2,3,4,5},枚举 C(5,n) 个资产子集,因此总计 C(5,2)+C(5,3)+C(5,4)+C(5,5)=10+10+5+1=26 个 subsets。
- **Calibration search.** 每个 subset 在 9 个 calibration 月上扫描 ℓ = 1..400、步长 1;这里的 ℓ 是 §3.6 定义的 bit-domain XOR aggregation level,不同于 §4.3 中 price-domain / physical-time aggregation 的秒级 ℓ。接受规则仍是 +Runs gate:D(adaptive *k*)、Monobit、Runs 三项的 all-offset pass rate 均 ≥ 0.80。
- **Selection rule.** 对每个 n,选择 estimated bits/month 最高的 subset;ℓ\*_n 取该 subset 9 个月 ℓ\* 的 80th percentile。为固定后续输出流,witness offset 在 calibration 末月选择:在 valid offsets 中取 D(adaptive *k*)、Monobit 与 Runs 三个 *p*-value 几何平均最大的 offset,并在 validation 中固定不再重选。Validation battery 的 pass/fail 仍按 all-offset pass-rate 判定,不由 witness offset 单独决定。P80 是 median 与 max 之间的折中:比 median 多留月度波动余量,但避免被单月 outlier 过度抬高。
- **Validation battery.** Validation 在选定 subset 与固定 ℓ\*_n 上运行 §3.3 定义的 29-sub-test universe。Validation 只跑 calibration-selected 的 4 个 subset(每 n 一个),这是 9/6 split 的方法学约束,不是数据缺失:在 validation 上扫所有 26 个 subset 会泄漏 test data。单个 (month, sub-test) 的 verdict 仍按 ≥80% valid offset 通过来判定;length-skip 或 sanity 不适用的项不进 admissible 分母。

#### Mutual Information Diagnostic

**Figure 4.7 — Experiment 4 · calibration-window mutual information matrix.** 展示 2025-01 至 2025-09 calibration 窗口上五个资产 1-second sign-bit 流的 pairwise mutual information。文件:`data/processed/experiment4/mi/figures/exp4_mi_matrix.png`。

Figure 4.7 先检验 Experiment 4 的核心前提:多个资产是否足够接近独立。结果是否定但有用。若把 10⁻³ bits/symbol 作为实用的 near-independence 参照线,10 个资产对全部高于这一量级;pooled MI 从 0.062 bits(BTC-BNB)到 0.244 bits(SOL-DOGE),平均 0.131 bits;|ρ| 从 0.292 到 0.565,平均 0.409。

这说明 crypto 资产的 1-second signs 共享明显 common-factor co-movement,并不满足 piling-up 引理的独立输入假设。因此 MI matrix 在本文中不作为 subset 选择准则,而作为解释 combined stream bias 的诊断量:如果 combination 仍能改善 residual sub-tests,其含义是"部分独立带来部分漂白",而不是严格独立下的理论保证。

#### Calibration Results

Calibration 流程如下。对每个 subset 与每个 calibration month,先按 §3.6 构造 combined stream,再在 ℓ = 1..400 的网格上运行 all-offset +Runs gate,取最小 passing ℓ 作为该月的 ℓ\*。随后在每个 n 内比较所有 subset 的 estimated bits/month,选择 throughput 最高的 subset;最终 ℓ\*_n 由该 subset 9 个 calibration 月 ℓ\* 的 80th percentile 给出。

**Table 4.8 — Experiment 4 · calibration 选出的 throughput-best subset。**

| n | selected subset | ℓ\*_n | witness offset | calibration est. bits/month | Δ vs runner-up | calibration median p(combined=1) |
|---|-----------------|:----:|:--------------:|-----------------------------:|:--------------:|---------------------------------:|
| 2 | BTC + ETH | 10 | 1 | 97,163 | +5% | 0.340 |
| 3 | BTC + ETH + SOL | 3 | 0 | 201,950 | +15% | 0.500 |
| 4 | ETH + BNB + SOL + DOGE | 9 | 1 | 45,711 | +8% | 0.281 |
| 5 | BTC + ETH + BNB + SOL + DOGE | 3 | 0 | 102,858 | unique | 0.499 |

> *Note.* "Δ vs runner-up" 表示 selected subset 相对同 n 下 2nd-best subset 的 throughput 百分比差距;n = 5 仅有一个 subset,故记为 unique。完整 26 个 subset 的 calibration 总览见 Appendix Table A.7。

Calibration 给出三个直接观察。第一,throughput-best subset 不等于 MI-best subset。例如 n = 3 的 MI-best 是 BTC+BNB+SOL,但 throughput-best 是 BTC+ETH+SOL;主文采用后者,因为 deployment 目标是 fixed gate 下的可用输出速率,MI 只做诊断。

第二,奇数 n 与偶数 n 在本 calibration window 中呈现出明显差异。n = 3 与 n = 5 的 combined p(1) 几乎等于 0.5,因而 ℓ\*_n 都落到 3;偶数 n = 2 与 n = 4 的 p(1) 明显偏离 0.5,需要更大的 ℓ 才能过 Monobit。这个结果与 XOR 的对称性直觉一致:在这些资产组合上,奇数个输入的 XOR 更接近平衡,偶数个输入则保留了更强的 marginal bias。这里的奇偶解释只作为经验诊断。

第三,throughput-best 与 runner-up 的差距并不总是显著。n = 2 仅 +5%(BTC+ETH 对 ETH+BNB),n = 4 仅 +8%(ETH+BNB+SOL+DOGE 对 BTC+ETH+SOL+DOGE),只有 n = 3 的 +15% 较为明显。这说明 "throughput-best" 在 n = 2 / n = 4 上只是边际优势;deployment set 的 robustness 因此还依赖 validation 阶段的统计稳健性表现,而不是 calibration throughput 排序本身。Appendix Table A.7 列出 26 个 subset 的完整 calibration 总览。

#### Validation Results

Validation 固定 calibration 选出的 subset、ℓ\*_n 与 witness offset,在 2025-10 至 2026-03 六个月逐月重新构造 combined stream,不再重新选择参数。29-sub-test verdict 仍按 all-offset pass-rate 判定;witness offset 只固定最终输出 stream 与 throughput 口径,不决定 validation battery 的 pass/fail。

**Table 4.9 — Experiment 4 · validation throughput and failure count.**

| n | selected subset | ℓ\*_n | median output bits/month | hours per 256 bits | sub-tests with ≥1 fail / 29 |
|---|-----------------|:----:|-------------------------:|-------------------:|----------------------------:|
| 2 | BTC + ETH | 10 | 95,622 | 1.99 | 4 |
| 3 | BTC + ETH + SOL | 3 | 191,830 | 0.98 | 11 |
| 4 | ETH + BNB + SOL + DOGE | 9 | 35,583 | 5.28 | 18 |
| 5 | BTC + ETH + BNB + SOL + DOGE | 3 | 95,118 | 2.01 | 8 |

**Figure 4.8 — Experiment 4 · throughput and validation trade-off.** 展示 selected subset 的 validation throughput、combined p(1) 与失败分布。文件:`data/processed/experiment4/validation/figures/exp4_validation_tradeoff.png`。

Validation 的第一层结论是吞吐量可用。n = 3 的 median throughput 最高,约 191,830 bits/month,生成 256 bits 需要约 0.98 小时;n = 2 与 n = 5 都约 95k bits/month,约 2 小时生成 256 bits;n = 4 最慢,约 35,583 bits/month,约 5.28 小时生成 256 bits。就 deployment latency 而言,n = 2、3、5 都处在低频使用可接受的量级;吞吐瓶颈不是当前组合方法的主要限制。

Validation throughput 整体接近但低于 calibration estimate;n = 4 的落差最大(~22%),与下文关于该配置漂出 calibration regime 的诊断一致。

**Figure 4.9 — Experiment 4 · validation verdict matrix.** 展示四个 n 在 2025-10 至 2026-03 六个月上的 29-sub-test validation verdict。文件:`data/processed/experiment4/validation/figures/exp4_validation_verdict.png`。

**Table 4.10 — Experiment 4 · key validation sub-tests, PASS months / 6。**

| Sub-test | n=2 | n=3 | n=4 | n=5 |
|----------|:---:|:---:|:---:|:---:|
| D(adaptive *k*) | 6 | 6 | 6 | 6 |
| D(*k* = 2) | 6 | 4 | 6 | 6 |
| Monobit | 4 | 6 | 0 | 5 |
| Runs | 6 | 4 | 6 | 6 |
| ApEn | 6 | 6 | 2 | 6 |
| Block Frequency | 6 | 5 | 3 | 6 |
| CumSum forward | 4 | 6 | 2 | 5 |
| CumSum backward | 4 | 6 | 0 | 5 |
| DFT | 6 | 6 | 6 | 6 |
| Serial *m* | 6 | 5 | 2 | 6 |
| Serial *m* − 1 | 6 | 5 | 6 | 6 |
| MultinomialBitsOver L4 | 6 | 5 | 1 | 6 |

第二层结论是 statistical robustness:validation 明确区分了 deployable configurations 与 failure case。n = 2、3、5 都有失败项,但失败是局部的;n = 4 则是系统性失败。

n = 2 的问题集中在 marginal-bias sensitive tests:Monobit、CumSum forward/backward 与 Alphabit MultinomialBitsOver L2 各有 2/6 月失败。n = 3 的 Monobit 与 CumSum 全过,但 D(k=2) 与 Runs 各有 2/6 月失败,说明 ℓ = 3 在边际上足够,但对短程依赖的聚合深度偏浅。n = 5 在统计上最稳健:Serial *m* 与 Serial *m* − 1 均 6/6 通过,多数失败项只出现 1/6 月。

n = 4 则不同:Monobit 0/6,CumSum backward 0/6,CumSum forward 2/6,Serial *m* 2/6,MultinomialBitsOver L4 1/6;在整个 29-sub-test universe 中,n = 4 合计有 18 个 sub-test 至少失败一次。

Table 4.10 也闭合了 Experiment 3 留下的问题。为避免跨窗口比较,这里把 Experiment 3 的 per-cell verdicts 限制到同一个 validation window(2025-10 至 2026-03)。在该窗口内,单资产 +Runs streams 的 Serial *m* 与 MultinomialBitsOver L4 均只通过 10/22 个 admissible cell。相比之下,deployable combined streams 在 n = 2/3/5 上分别达到 Serial 6/6、5/6、6/6,以及 L4 6/6、5/6、6/6。

这个配对比较说明 multi-asset combination 确实改善了 Experiment 3 暴露出的高阶残留。n = 4 仍失败:Serial *m* 只通过 2/6,L4 只通过 1/6,因为它的边际 bias 已经漂出 calibration 覆盖范围。换言之,multi-asset combination 有效,但前提是固定 calibration 仍能描述 validation 分布。

#### Why n = 4 Fails

n = 4 在 calibration 阶段完全通过——5 个 subset × 9 个月 45 个 cell 全部能在 ℓ 网格内找到使 +Runs gate 通过的 ℓ\*,ETH+BNB+SOL+DOGE 因 estimated throughput 最高而被选中——却在 validation 阶段系统性失败:Monobit 6 个月全部不过,CumSum backward 6 个月也全部不过。这不是普通的"弱 subset",而是 fixed-window calibration 在非平稳 sign bias 下的泛化失败。

n = 4 的系统性失败可以由 combined stream 的 marginal bias 漂移解释。Calibration 9 个月里,n = 4 的 combined p(1)(combined stream 中 1 的占比)大致落在 0.27 附近(具体 0.237–0.303 之间);validation 6 个月里 p 漂到 0.15–0.24 之间,其中 5 个月比 calibration 见过的任何月份都更偏。Calibration 选出的固定 ℓ = 9 是按 p ≈ 0.27 这一带 bias 标定的:在该 bias 上,9 个 bit XOR aggregation 已经足以把残留偏置压到 Monobit 探测不到的水平。一旦 p 漂到 0.15 附近,XOR 输入的偏置变大,同样的 ℓ = 9 不够压制残留,Monobit 因此整段失败。Calibration 9 个月里**没有任何一个月**见过这么偏的 p,所以无论用 median、P80 还是 max,都无法从 calibration 数据本身预先选出更大的 ℓ。

这正是 9/6 split 的价值。它不只产出一个失败配置,而是暴露了方法边界:在 crypto sign bits 呈现月度尺度的非平稳性时,calibration 窗口选出的固定 ℓ 不能被默认推广到所有 n。n = 4 因此不进入 deployment set;它作为负结果保留在论文中,因为它解释了为什么最终管线必须把 market-derived bits 当作 entropy input for downstream conditioning,而不能直接把 combined bits 当最终随机输出。

#### Min-Entropy and Deployment Set

Validation 结果导向的是一个 deployment set,而不是单一 winner。n = 3 是 throughput-best configuration;n = 5 是更强的 robustness check,其 hours-per-256-bit 与 n = 2 接近;n = 2 保留为较低复杂度的 fallback。n = 4 因为 validation failure 具有系统性而被排除。

按 §3.7 定义的 min-entropy budget 口径(MCV 与 Markov estimator 取较小者),对每个 validation cell 估计 h∞。

**Table 4.11 — Experiment 4 · validation min-entropy summary.**

| n | selected subset | median h∞ | worst-month h∞ | binding estimator | IKM bytes for 256-bit target |
|---|-----------------|----------:|---------------:|-------------------|-----------------------------:|
| 2 | BTC + ETH | 0.979 | 0.975 | MCV | 33 |
| 3 | BTC + ETH + SOL | 0.988 | 0.982 | mostly MCV; worst Markov | 33 |
| 4 | ETH + BNB + SOL + DOGE | 0.943 | 0.903 | MCV | 36 |
| 5 | BTC + ETH + BNB + SOL + DOGE | 0.982 | 0.979 | MCV | 33 |

Table 4.11 给出的边界与 validation battery 一致。若包含所有 n,最差 cell 是 n = 4,h∞ = 0.903 bits/symbol,达到 256-bit target 需要 36 input bytes。若只看 deployable set n ∈ {2,3,5},最差月 h∞ = 0.975 bits/symbol,因此 33 input bytes 足以支撑 256-bit target。MCV 几乎总是给出更紧的下界——24 个 validation cell 中 23 个由 MCV 决定 min-entropy 的最终值,只有 1 个由 Markov 决定。

这说明主要残留通常是 0/1 比例不均(MCV 捕捉的),而不是相邻 bit 之间的依赖(Markov 捕捉的);market-derived bits 应作为 entropy input for downstream conditioning,而不是直接映射为最终随机输出。

因此,Experiment 4 给出了 RQ3 的核心实验证据。Multi-asset XOR combination 可以在 validation window 上产出吞吐可用、min-entropy 估计足以支撑 password generation 的 streams,条件是排除失败的 n = 4,并把下游 HKDF-based conditioning component 视为构造的必要组成部分。结论是正向但有条件的:combination 在奇数 n 上改善了 Experiment 3 看到的 high-order residual,n = 4 暴露出非平稳性边界,cryptographic conditioning 不是可选增强,而是设计要求。

---

## Appendix — Supplementary Tables

本附录给出两类补充结果。第一类是 Experiment 2 在主要判据与方向性对照下的完整 15 月 selected ℓ\* 表。主文 §4.3 Figures 4.2–4.5 只展示 2025 Q1 与 2026 Q1(Q5)两个代表季度的曲线,完整时间序列在此呈现。第二类是 Experiment 4 的完整 calibration ranking(Appendix Table A.7)。Experiment 2 表使用同一列序(BTC > ETH > BNB > SOL > DOGE,按 raw trades/s 中位数降序排列,与 Table 4.1 一致),空 cell ``-'' 表示该 (asset, month) 在对应判据下在 ℓ 网格内无 acceptable ℓ。Experiment 2 附录表的原始 CSV 存放于 `data/processed/experiment2/`;Experiment 4 calibration summary 存放于 `data/processed/experiment4/calibration_all_subsets/`。

**Table A.1 — Single-offset selected ℓ\* per (asset, month)。** ℓ 网格 50 至 2000、步长 25;判据 = 最小满足 D(adaptive *k*)与 Monobit 同时给出 *p* ≥ α(α = 0.01)的 ℓ。

| Month   |  BTC | ETH  | BNB | SOL | DOGE |
|---------|-----:|-----:|----:|----:|-----:|
| 2025.01 |   −  |  925 | 275 | 750 |  825 |
| 2025.02 | 1650 |  875 | 475 | 500 |  225 |
| 2025.03 | 1800 |  625 | 250 | 275 |  375 |
| 2025.04 | 1700 |  750 | 250 | 225 |  275 |
| 2025.05 | 1500 | 1250 | 250 | 400 |  225 |
| 2025.06 | 1100 |  525 | 200 | 225 |  125 |
| 2025.07 | 1975 |  600 | 375 | 400 |  250 |
| 2025.08 |   −  | 1575 | 275 | 475 |  250 |
| 2025.09 |  900 |  850 | 350 | 300 |  250 |
| 2025.10 | 1375 |  725 | 850 | 225 |  175 |
| 2025.11 | 1125 |  875 | 300 | 150 |  150 |
| 2025.12 | 1050 |  600 | 275 | 125 |   75 |
| 2026.01 | 1300 |  725 | 250 | 175 |  125 |
| 2026.02 | 1225 |  550 | 250 | 200 |  100 |
| 2026.03 | 1075 |  575 | 175 | 100 |  100 |


**Table A.2 — All-offset, strict gate · selected ℓ\* per (asset, month)。** ℓ 网格 50 至 2000、步长 25;判据 = strict 80% pass-rate(D 与 Monobit 通过率均 ≥ 0.80)。

| Month   |  BTC | ETH  |  BNB | SOL  | DOGE |
|---------|-----:|-----:|-----:|-----:|-----:|
| 2025.01 |   −  | 1900 |  325 |   −  | 1075 |
| 2025.02 |   −  | 1025 |  700 |   −  |  900 |
| 2025.03 |   −  | 1150 |  350 |  425 |  500 |
| 2025.04 |   −  |  975 |  275 |  600 |  375 |
| 2025.05 |   −  |   −  |  475 |  625 |  650 |
| 2025.06 | 1325 |  850 |  250 |  300 |  125 |
| 2025.07 |   −  | 1275 |  425 |  550 |  650 |
| 2025.08 |   −  |   −  |  300 |  650 |  375 |
| 2025.09 | 1500 |  975 |  375 |  425 |  450 |
| 2025.10 | 1625 | 1300 | 1025 |  350 |  225 |
| 2025.11 | 1600 | 1400 |  450 |  225 |  200 |
| 2025.12 | 1275 |  700 |  275 |  150 |   75 |
| 2026.01 | 1825 |  950 |  400 |  225 |  150 |
| 2026.02 |   −  |  650 |  325 |  225 |  125 |
| 2026.03 | 1225 |  750 |  200 |  150 |  125 |

跨 15 月接受率 63/75(BTC 8 月失败、ETH 与 SOL 各 2 月失败)。在这 63 个 selected cell 上,`runs_pass_rate < 0.05` 的 cell 为 38 个;`D(k=2)_pass_rate < 0.05` 的 cell 同样为 38 个。

**Table A.3 — Transaction-time strict + Runs gate · selected ℓ\* per (asset, month)。** ℓ 网格同 Table A.2;判据 = D、Monobit、Runs 三项通过率均 ≥ 0.80。该表仅作为 §4.3.5 的同口径对照,不改变主文 strict gate 的定义。

| Month   |  BTC | ETH  |  BNB | SOL  | DOGE |
|---------|-----:|-----:|-----:|-----:|-----:|
| 2025.01 |   −  |   −  |  675 |   −  |   −  |
| 2025.02 |   −  | 1800 |   −  |   −  | 1500 |
| 2025.03 |   −  | 1550 |  550 | 1300 |  950 |
| 2025.04 |   −  | 1575 |  425 |  950 | 1075 |
| 2025.05 |   −  |   −  | 1075 | 1200 | 1550 |
| 2025.06 |   −  | 1325 |  550 |  675 |  225 |
| 2025.07 |   −  |   −  |   −  | 1650 |   −  |
| 2025.08 |   −  |   −  |  500 | 1750 | 1075 |
| 2025.09 |   −  | 1725 |  650 |  750 | 1025 |
| 2025.10 |   −  |   −  |   −  |  550 |  300 |
| 2025.11 |   −  | 1850 |  525 |  325 | 1425 |
| 2025.12 | 1925 | 1050 |  400 |  250 |  100 |
| 2026.01 |   −  | 1850 |  650 |  350 |  275 |
| 2026.02 |   −  |   −  |  575 |  450 |  300 |
| 2026.03 |   −  | 1750 |  225 |  325 |  300 |

跨 15 月接受率 48/75(BTC 1 月通过、ETH 9 月、BNB 12 月、SOL 与 DOGE 各 13 月)。

**Table A.4 — All-offset, relaxed gate · selected ℓ\* per (asset, month)。** ℓ 网格 10 至 2000、步长 2;判据 = max(F, ⌈f·N_valid⌉) 联合通过(F = 3, f = 0.03)。

| Month   |  BTC | ETH  | BNB | SOL | DOGE |
|---------|-----:|-----:|----:|----:|-----:|
| 2025.01 | 1750 |  800 | 244 | 596 |  594 |
| 2025.02 | 1550 |  610 | 286 | 312 |  172 |
| 2025.03 | 1576 |  436 | 180 | 180 |  214 |
| 2025.04 | 1370 |  444 | 176 | 196 |  162 |
| 2025.05 | 1248 |  550 | 198 | 226 |  156 |
| 2025.06 |  924 |  400 | 146 | 104 |   72 |
| 2025.07 | 1376 |  576 | 268 | 298 |  220 |
| 2025.08 | 1314 | 1194 | 212 | 388 |  214 |
| 2025.09 |  900 |  698 | 256 | 270 |  238 |
| 2025.10 | 1150 |  714 | 464 | 164 |  124 |
| 2025.11 |  988 |  660 | 232 | 108 |   72 |
| 2025.12 |  870 |  470 | 206 |  98 |   48 |
| 2026.01 | 1030 |  556 | 218 | 110 |   66 |
| 2026.02 |  998 |  420 | 158 |  76 |   56 |
| 2026.03 |  880 |  442 | 128 |  66 |   48 |

跨 15 月接受率 75/75。

**Table A.5 — Bonferroni / Šidák 3 月方向性对照(参考 §4.3.4)。** 用 per-offset α / N_valid 收紧后做"至少一条 offset 通过"判据。所有 cell 的 ℓ\* 都小于 Table A.3 的对应值,印证 §3.4 的方向性论证:Bonferroni / Šidák 控制的是"至少一个假拒绝",不适合作为"至少一个假通过"问题的正式校正;在"至少一条通过"规则下收紧 α 反而给出更早、更宽松的 selected ℓ\*。因此该表只作为方向性对照,不作为主判据。

| Month   |  BTC | ETH | BNB | SOL | DOGE |
|---------|-----:|----:|----:|----:|-----:|
| 2025.01 | 1364 | 500 | 218 | 334 |  274 |
| 2025.02 | 1144 | 422 | 190 | 208 |  132 |
| 2025.03 | 1252 | 338 | 156 | 154 |  102 |


**Table A.6 — 1-second bar gate · selected ℓ\* per (asset, month)、三档 gate 对照。** ℓ 单位为秒,网格 10 至 600、步长 1。

*A.6(a) Base gate(D + Monobit)*

| Month   | BTC | ETH | BNB | SOL | DOGE |
|---------|----:|----:|----:|----:|-----:|
| 2025.01 |  53 |  58 | 148 |  32 |   31 |
| 2025.02 |  88 | 204 |  61 |  65 |   84 |
| 2025.03 |  65 | 413 |  70 |  41 |   35 |
| 2025.04 |  45 |  15 |  57 |  19 |   21 |
| 2025.05 |  75 | 537 | 327 | 200 |   92 |
| 2025.06 |  49 |  −  | 111 |  18 |   18 |
| 2025.07 | 114 |  91 |  −  | 319 |   43 |
| 2025.08 | 110 |  35 | 111 |  54 |   43 |
| 2025.09 |  80 |  71 | 254 |  67 |   61 |
| 2025.10 |  62 |  34 |  38 |  28 |   16 |
| 2025.11 |  26 |  29 |  25 |  10 |   22 |
| 2025.12 |  34 |  −  |  91 | 467 |   24 |
| 2026.01 |  47 |  36 |  76 |  20 |   15 |
| 2026.02 |  18 |  −  |  27 | 347 |   −  |
| 2026.03 | 250 | 327 | 197 | 356 |  196 |

接受率 70/75(失败:2025.06 ETH、2025.07 BNB、2025.12 ETH、2026.02 DOGE / ETH;其中 2025.12 ETH 与 2026.02 DOGE 的 seconds-with-trades coverage < 0.75,其余失败 cell 的 coverage 仍在 0.76–0.83 附近)。

*A.6(b) +Runs gate(base + Runs)*

| Month   | BTC | ETH | BNB | SOL | DOGE |
|---------|----:|----:|----:|----:|-----:|
| 2025.01 | 121 |  58 | 148 | 154 |   34 |
| 2025.02 |  94 | 227 |  77 | 479 |   84 |
| 2025.03 |  65 |  −  |  70 |  45 |   53 |
| 2025.04 |  64 |  20 | 112 |  26 |   27 |
| 2025.05 |  92 |  −  | 327 | 200 |   92 |
| 2025.06 |  49 |  −  | 111 |  18 |   19 |
| 2025.07 | 233 |  −  |  −  | 319 |   43 |
| 2025.08 | 141 |  53 | 111 |  79 |   58 |
| 2025.09 | 110 |  71 | 254 |  72 |   69 |
| 2025.10 |  72 |  36 |  39 |  35 |   23 |
| 2025.11 |  34 |  99 |  27 |  13 |  145 |
| 2025.12 | 500 |  −  |  91 |  −  |   −  |
| 2026.01 |  47 |  50 |  76 |  24 |   16 |
| 2026.02 |  22 |  −  |  27 |  −  |   −  |
| 2026.03 | 339 |  −  | 293 |  −  |  278 |

接受率 62/75;Runs 在大多数 cell 通过(transaction-time selected ℓ\* 上几乎所有 cell 仍被拒绝),这是 1-second bar 物理时间聚合的核心独立性结果(§4.3.5)。

*A.6(c) +Runs+ApEn gate(base + Runs + ApEn m = 5)*

| Month   | BTC | ETH | BNB | SOL | DOGE |
|---------|----:|----:|----:|----:|-----:|
| 2025.01 | 121 | 115 | 158 | 154 |   38 |
| 2025.02 |  94 | 227 |  78 | 479 |   89 |
| 2025.03 |  70 |  −  | 160 |  46 |   59 |
| 2025.04 |  64 |  20 | 112 |  26 |   27 |
| 2025.05 |  94 |  −  | 327 | 200 |   92 |
| 2025.06 |  51 |  −  | 111 |  18 |   19 |
| 2025.07 | 233 |  −  |  −  | 319 |   43 |
| 2025.08 | 141 |  58 | 111 |  79 |   58 |
| 2025.09 | 110 |  80 | 254 |  73 |   69 |
| 2025.10 |  72 |  41 |  47 |  35 |   23 |
| 2025.11 |  34 | 105 |  28 |  15 |  145 |
| 2025.12 | 500 |  −  |  91 |  −  |   −  |
| 2026.01 |  49 | 384 |  76 |  24 |   18 |
| 2026.02 |  22 |  −  | 323 |  −  |   −  |
| 2026.03 | 339 |  −  | 293 |  −  |  278 |

接受率 62/75;ApEn(m = 5)加在 +Runs 之上不再削减接受 cell 数,只让少数 cell 的 selected ℓ\* 略微上推。


**Table A.7 — Experiment 4 · per-subset calibration summary(26 个 subset 全表)。** Calibration window:2025-01 至 2025-09(共 9 月)。所有 234 个 (subset, month) cell 均通过 +Runs gate,即每个 cell 都能在 ℓ ∈ [1, 400] 网格内找到使 D(adaptive *k*)、Monobit、Runs 三项 all-offset pass rate 均 ≥ 0.80 的 ℓ\*。行按 n 升序、组内按 estimated bits/month 降序排列;† 标注每个 n 下被选作 deployment 的 throughput-best subset(也是主文 Table 4.8 中报告的 4 个)。原始 CSV:`data/processed/experiment4/calibration_all_subsets/all_subsets_summary.csv`。

| n | subset                              | ℓ\*_n | calibration median p(combined=1) | estimated bits/month | witness offset |
|---|-------------------------------------|:----:|---------------------------------:|---------------------:|:--------------:|
| 2 | BTC + ETH †                         |  10  | 0.340 |  97,163 | 1 |
| 2 | ETH + BNB                           |   9  | 0.333 |  92,532 | 0 |
| 2 | ETH + SOL                           |  12  | 0.254 |  80,889 | 4 |
| 2 | BTC + SOL                           |  10  | 0.328 |  80,888 | 5 |
| 2 | ETH + DOGE                          |  13  | 0.213 |  79,650 | 8 |
| 2 | BNB + SOL                           |   9  | 0.336 |  78,314 | 6 |
| 2 | BNB + DOGE                          |  10  | 0.326 |  75,467 | 9 |
| 2 | BTC + BNB                           |  10  | 0.362 |  70,219 | 6 |
| 2 | BTC + DOGE                          |  12  | 0.312 |  67,107 | 1 |
| 2 | SOL + DOGE                          |  15  | 0.207 |  57,429 | 2 |
| 3 | BTC + ETH + SOL †                   |   3  | 0.500 | 201,950 | 0 |
| 3 | ETH + BNB + SOL                     |   3  | 0.500 | 175,462 | 1 |
| 3 | BTC + ETH + BNB                     |   3  | 0.500 | 174,497 | 0 |
| 3 | BNB + SOL + DOGE                    |   3  | 0.500 | 166,881 | 0 |
| 3 | BTC + BNB + SOL                     |   3  | 0.499 | 156,022 | 1 |
| 3 | BTC + BNB + DOGE                    |   3  | 0.500 | 152,526 | 1 |
| 3 | ETH + SOL + DOGE                    |   5  | 0.499 | 139,510 | 0 |
| 3 | BTC + ETH + DOGE                    |   5  | 0.500 | 124,634 | 4 |
| 3 | ETH + BNB + DOGE                    |   5  | 0.502 | 115,206 | 2 |
| 3 | BTC + SOL + DOGE                    |   5  | 0.499 | 109,732 | 2 |
| 4 | ETH + BNB + SOL + DOGE †            |   9  | 0.281 |  45,711 | 1 |
| 4 | BTC + ETH + SOL + DOGE              |  11  | 0.273 |  42,430 | 5 |
| 4 | BTC + ETH + BNB + SOL               |   9  | 0.320 |  42,236 | 1 |
| 4 | BTC + ETH + BNB + DOGE              |  10  | 0.307 |  38,895 | 4 |
| 4 | BTC + BNB + SOL + DOGE              |   9  | 0.310 |  38,511 | 1 |
| 5 | BTC + ETH + BNB + SOL + DOGE †      |   3  | 0.499 | 102,858 | 0 |

> *Note.* n = 3 的前 6 行 ℓ\*_n 同为 3、p(combined=1) 均 ≈ 0.500,印证主文 §4.5 的奇偶 effect 观察(奇数 n 的 XOR 一阶矩抵消);n = 2 / n = 4 的偶数行 p(1) 普遍偏离 0.5,需要更大的 ℓ 才能过 Monobit。Throughput-best 与 runner-up 的差距详见主文 §4.5 Table 4.8。


---

## Chapter 5 — Password Generator Prototype

本章把 Experiment 4 选出的 deployable streams 接到一条 standard HKDF-SHA256 conditioning 与字符集映射的管线,产出 16-character passwords 并检查输出在统计层面是否与理想 baseline 对齐。

因此,Chapter 5 的评价对象不是"市场数据是否随机"本身,也不是重新运行 NIST / TestU01 battery。市场输入的统计随机性与 min-entropy 已在 Chapter 4 中评估。本章只回答应用层问题:在这些输入已经通过前述筛选的条件下,standard cryptographic conditioning 是否能把它们转化为可用密码,以及这些密码在输出分布与 entropy 口径下能达到的强度。

### Prototype Design and Scope

Prototype 固定使用 Experiment 4 已经选出的 deployable set,n ∈ {2,3,5};n = 4 因 validation 中系统性失败而不进入 prototype。目标是检查这些 streams 经 HKDF-SHA256 conditioning 与字符集映射后,能否产出日常使用意义上的强密码。

这里的"强密码"指随机生成、字符分布接近均匀、entropy 明显高于常见 human-chosen password 的密码字符串。其主强度口径是 password length 与字符集大小给出的 search-space entropy,不是 AES-128 / AES-256 这类 symmetric-key security level。

Pipeline 见 Figure 5.1。每个 password 使用从 Experiment 4 deployable stream(n ∈ {2,3,5},validation month)切出的一段 disjoint 33-byte IKM,经 HKDF-SHA256 派生后通过 rejection sampling 映射到 70-character charset(`[a-z] + [A-Z] + [0-9] + !@#$%^&*`)。33 bytes 的长度来自 §4.5 的 min-entropy 估计。[^ch5-ikm-bytes]

**Figure 5.1 — Prototype pipeline.** 展示从 Experiment 4 combined stream 到 16-character password 的 per-password 数据流,包含 salt 侧入与 re-Expand fallback。文件:`thesis/figures/prototype_pipeline.png`。

Rejection sampling 的接受窗口为 b < 210,以避免 modulo bias(Lemire, 2019)。HKDF 实现通过 RFC 5869 Appendix A Test Case 1 self-test;本次 2,400 个 HKDF-generated passwords 全部在一个 expand round 内完成,re-Expand fallback(info ‖ counter)未触发。

本章因此限于 **passive statistical 评估**:具体指标(字符均匀性的 chi-square 与 Shannon entropy)在 §5.2 给出。Password 输出不重新送进完整 randomness battery(市场输入的统计随机性已由 Chapter 4 负责);adversarial security 不在本章范围内。

[^ch5-ikm-bytes]: Deployable set worst-month h∞ = 0.975 bits/symbol(Table 4.11),因此 33 × 8 × 0.975 ≈ 257 ≥ 256 bits 的 estimated input entropy。

Prototype 使用一个 repository-persisted salt 以保证 demo 可复现。该 salt 适合复现实验输出:同一份 market streams、同一份代码与同一份 salt 会 bit-for-bit 生成相同的 passwords。但由于 market data 是公开数据,生产级密码生成器若要求 password secrecy,需要在 conditioning 阶段把 market-derived entropy 与某种 deployment-secret material 结合;本文保存在仓库里的公开 demo salt 不适合作为生产保密场景中的唯一 secret source。

### Evaluation and Results

Evaluation 使用 2025-10 至 2026-03 的 6 个 validation months,与 Experiment 4 validation window 完全一致。market 组采用 Experiment 4 的 deployable configurations:n = 2、n = 3、n = 5。每个 (n, month) cell 生成 100 个 16-character passwords,因此 market 组共有 3 × 6 × 100 = 1800 个 passwords。

为判断 market-derived output 是否与理想输出处在同一量级,prototype 同时生成两个 baseline:

- **B1 ideal-password baseline.** 直接从同一 70-character charset 均匀抽样,不经过 HKDF。它代表输出层面的理想 password 分布。
- **B2 ideal-IKM baseline.** 使用 salt-seeded random IKM 通过同一 HKDF-SHA256 pipeline。它保留 conditioning 与 charset mapping,只把 entropy source 换成理想输入。

两个 baseline 各覆盖 6 个 validation months,每月 100 个 passwords,因此 B1 与 B2 各有 600 个 passwords。总评估规模为 3000 个 passwords,分布在 30 个 cells 上。

每个 cell 的评价指标有两项。第一项是 pooled chi-square goodness-of-fit(Pearson, 1900):把 100 个 16-character passwords 展开成 1600 个字符,检验 70 个字符类别是否接近均匀分布,显著性水平 α = 0.01。第二项是同一 1600 个字符上的 Shannon entropy(bits/char)。这两个指标只评估输出字符分布。

**Table 5.1 — Prototype output evaluation.**

| group | cells | chi-square pass | chi-square p-value range | entropy median [min, max] |
|---|---:|---:|---:|---:|
| market n=2 | 6 | 6/6 | [0.248, 0.897] | 6.1000 [6.0946, 6.1045] |
| market n=3 | 6 | 6/6 | [0.111, 0.783] | 6.0986 [6.0902, 6.1032] |
| market n=5 | 6 | 6/6 | [0.0705, 0.982] | 6.0950 [6.0897, 6.1082] |
| B1 ideal-password | 6 | 5/6 | [0.000375, 0.787] | 6.0981 [6.0779, 6.1017] |
| B2 ideal-IKM | 6 | 6/6 | [0.595, 0.938] | 6.1007 [6.0996, 6.1058] |

**Figure 5.2 — Prototype evaluation · chi-square and Shannon entropy.** 展示 market n ∈ {2,3,5} 与 B1 / B2 baselines 的输出层面对比。文件:`data/processed/prototype/evaluation/figures/sidebyside_chi2_entropy.png`。

**市场衍生密码通过了输出均匀性检验。** 18 个 market-derived cells 全部通过字符均匀性检验;30 个总 cells 中只有 1 个失败,且失败发生在 B1 ideal-password baseline 的 2026-01 cell(p = 0.000375),不发生在 market output 上。考虑到 α = 0.01 且共检验 30 个 cells,期望 type-I failure 数为 30 × 0.01 = 0.30;至少出现 1 个 failure 的概率约为 26%。因此,这个单一 baseline failure 更合理地解释为有限样本下的正常随机波动,而不是 prototype pipeline 的缺陷。

**经验熵与两个 baseline 对齐。** 理论最大值为 log₂(70) = 6.1293 bits/char;本次所有 groups 的 median entropy 约为 6.095–6.101 bits/char。观测值比理论最大值低约 0.02–0.05 bits/char,但该偏差在 market 与两个 baseline 中同时出现,主要反映 1600-character plug-in entropy estimator 的有限样本偏差(即 Miller-Madow bias,(m−1)/(2N ln 2) ≈ 0.031 bits/char;Miller, 1955;现代分析见 Paninski, 2003),而不是 market-derived output 的独有问题。

**生成密码落在 strong-password 区间。** 按 overall median 6.0997 bits/char 计算,16-character password 的经验 entropy 约为 97.6 bits;理论上限为 98.07 bits(= 16 × log₂(70))。作为参照,常见 human-chosen password 估计在 ~30 bits 量级、strong-password 经验门槛 ≳ 80 bits(口径详见 §2.2 Password output strength),本 prototype 的 ~98 bits 落在 strong-password 区间。

**三档可部署 n 在输出层表现相近。** Market n = 2、3、5 在 prototype output 层面落在相近区间。结合 Experiment 4 的结果看,这并不表示 upstream residual 已经消失;它只说明在 §4.5 给出的 min-entropy 条件下,这些 residual 没有在本章采用的字符均匀性与 Shannon entropy 指标中表现为额外异常。

总体而言,Chapter 5 给出的结论是正向且有条件的:经过 Experiments 1–4 的筛选、聚合、扩展电池验证、多资产 combination 与 min-entropy sizing 后,deployable market-derived streams 可以作为 HKDF-based password generator 的 entropy input,产出字符分布与理想 baseline 对齐的日常强密码。该结论限于 §5.1 定义的 passive statistical setting;真实保密部署仍需要额外的 deployment secret。


---

## Chapter 6 — Discussion

### Thesis-Level Answer

本论文的核心结论是:在 deployable 配置 n ∈ {2, 3, 5} 下,加密货币市场数据经标准 HKDF-SHA256 conditioning 后,可以产出在本文输出层面指标上与理想 baseline 对齐的 ~98-bit 强密码。这一结论由 Experiments 1–4 的统计验证链与 Chapter 5 的端到端 prototype 共同支撑:

1. **Experiment 1** 否定原始 tick sign 直接作为 RNG 输入的可行性;
2. **Experiment 2** 在 1-second bar 物理时间轴上显著缓解短程依赖,并在多数 cell 上通过 +Runs gate;
3. **Experiment 3** 用至多 29 个 sub-test 的扩展电池审计 Experiment 2 gate 的覆盖边界;
4. **Experiment 4** 通过 multi-asset combination 选出三档 deployable streams,并暴露 n = 4 的非平稳性边界;
5. **Chapter 5 prototype** 把这条链端到端落到 password generation 上——3,000 个 password 的 chi-square 与 Shannon entropy 与理想 baseline 对齐(详见 §5.2 Table 5.1)。

该结论限于 **passive statistical setting**——即被动观察者能否在输出序列里发现 pattern,典型评估手段是 §4.3–§4.5 用到的 randomness battery 以及 Chapter 5 的输出层 chi-square 与 Shannon entropy。主动市场操纵、生产 secret 管理与轮换、以及 beacon-style unpredictability(即知道 public source 与 configuration 的对抗者能否预测下一 pulse——把"通过 randomness battery"等同于"beacon-unpredictable"是 Chapter 2 beacon 路线读者常见的混淆陷阱)均不在本文证明范围内;active manipulation 作为 §6.4 limitation #5 进一步说明。

### Answers to the Research Questions

§6.1 的 thesis-level 结论由对三个 research question 的逐个回应支撑。下文按 RQ 顺序给出每条结论的关键数字与边界。

**RQ1 — 聚合能否抽出统计独立的随机序列?** 答案是 *条件性 yes*。两条聚合轴都能在多数 (asset, month) 单元上找到通过 *D* + Monobit 的 ℓ\*:transaction-time 下 strict gate 给出 63/75、relaxed gate 75/75;1-second bar 下 strict gate 给出 70/75。但"独立性"在两条轴上的表现差异显著——transaction-time 下 *D*(*k* = 2) / Runs 在每个 witness 上都被拒;1-second bar 下两者在 62/75 个 cell 上达成 ≥ 80% offset 通过率。**对独立性的真正考验只在物理时间轴上才通过**——这也是 Experiment 3 与 Experiment 4 把 1-second bar +Runs gate 选为主样本的依据。

**RQ2 — 序列能否通过标准 randomness 检验?** 答案是 *主要 yes,但存在清晰边界*。1-second bar 轴上 +Runs gate 选出的 62 个 cell 经 §4.4 的 29-sub-test 扩展电池审计:D(adaptive *k*)、Monobit、Runs 与 DFT 在 admissible 范围内 100% 通过;D(*k* = 2) 只在 62 个 cell 中失败 1 个;但 Serial *m*、TestU01 Alphabit MultinomialBitsOver L4 与 ApEn 仍暴露出跨资产高阶残留。**§4.3.5 的小型 gate 对边际与短程结构有效,但不足以覆盖高阶 / 多符号结构**——这一边界直接动机化了 Experiment 4 的 multi-asset combination。

**RQ3 — 这些序列能否用于安全密码生成?** 答案是 *passive statistical setting 下的 yes*。Experiment 4 通过 9/6 calibration / validation split 选出 deployable set n ∈ {2, 3, 5}——n = 4 在 validation 阶段 Monobit / CumSum backward 全部失败(0/6),作为 calibration-validation 泛化失败的负结果保留,但不进 deployment。Chapter 5 prototype 在三档 deployable streams 上经 HKDF-SHA256 + 16-character mapping 生成 1,800 个 market-derived passwords;连同 B1 ideal-password 与 B2 ideal-IKM 两个 baseline,总评估规模为 3,000 个 password。结果显示:18 个 market cell 全部通过 chi-square(α = 0.01),Shannon entropy 与 baseline 在 ~0.03 bits/char 的 Miller-Madow bias 范围内一致。这是"standard cryptographic conditioning 是 deployable streams 转化为可用密码的必要组成"的 prototype 层面证据。

### Secondary Observations

在三个 RQ 之外,本工作记录两条与 Chapter 2 综述中 UHF 文献(美股、莫斯科交易所)在跨市场层面呼应的方法学观察。它们作为 secondary contributions(见 §7.2)出现,不进入 main contribution 列表;Chapter 4 正文不复述。

(1) **粗粒度活跃度分层 + 局部 non-monotonicity。** Selected ℓ\* 在 5 资产上呈现两层结构:粗粒度上与 trades/s 同向(高活跃 BTC 需要更大的 ℓ\*),与美股 UHF 文献"活跃度 → 所需聚合层级"的报告一致;细粒度上 SOL / DOGE / BNB 三者不严格单调,raw_tps 排序与 selected ℓ\* 排序错位(详见 §4.3 与 Table 4.1)。后一现象在另一市场上同样被观察到,通常归因于微观结构机制(例如 order splitting / 执行调度,见 Almgren & Chriss, 2001);加密货币市场上的具体识别留 §6.4 Future Work。

(2) **1 阶残留更像聚合轴属性,而非源数据固有属性。** *D*(*k* = 2) / Runs 在 transaction-time 下被拒、在 1-second bar 下大多窗口通过,提示 §4.2 观察到的正向 1 阶残留更可能由采样轴选择带来,而不是原始 tick 数据不可缓解的属性。把这一残留从"方法学失败"重新框为"采样轴选择代价",直接对应 §4.3.6 把 physical-time base gate 选为 Experiment 3 主配置的依据;跨市场可推广性留 §6.4 Future Work。

### Limitations and Future Work

**Methodological limitations.**

1. **Witness offset 的固定策略仍是简化设计。** 本文在 calibration 末月固定 witness offset 并在 validation 中保持不变,该选择影响最终对外输出的单条 stream 与吞吐量口径,但不决定 validation battery 的 pass/fail verdict——后者仍按 all-offset pass-rate 判定。更稳健的部署版本可在 future work 中比较单月 witness、多月稳定性 witness 与固定 offset 规则。
2. **判据设计的形式校正未做。** ℓ 网格的选择维度未做 Bonferroni / FDR 校正(strict 与 relaxed 共有);relaxed gate 的 (F, f) = (3, 0.03) 是 §3.4 论证下的 design choice,未做 (F, f) 网格的敏感性扫描(例如 (2, 0.02) 或 (5, 0.05) 下 selected ℓ\* 与覆盖率如何变化)。本工作的 relaxed-gate 结果应理解为这一组 design parameters 下的产出,而非该 family of heuristics 中的最优配置。
3. **扩展电池仍非完整 NIST / TestU01。** Experiment 3 已补入 NIST SP800-22 的 7 个扩展统计量与 TestU01 Alphabit,但 Non-overlapping Template、Universal Statistical、Random Excursions 系列与 TestU01 Rabbit 未纳入主分析。原因是 scope 与长度共同约束,不是这些检验在理论上不重要。
4. **边缘样本长度。** 本论文 valid offset 比特流的有效长度 n ∈ [2 × 10³, ~10⁴],处在 Shternshis & Marmi (2025) Appendix A Q-Q 仿真的边缘区间——该仿真显示 n ≥ 10⁴ 时 *D* 检验的 χ² 渐近近似可靠,n ~ 10³ 时可能偏离。因此本文接受判据带有"边缘样本"风险,临界附近的判定需谨慎;该限制独立于本工作的方法选择,只能通过更长样本期缓解。
5. **主动市场操纵不属于本 prototype 的威胁模型**(scope 与 threat model 见 §6.1 与 §5.1)。若研究目标转向公共随机灯塔或链上协议,需另行引入 Landis & Bonneau (2025) 式的 active-attacker / cost-of-manipulation 模型。

**Future work.**

- **补全完整 randomness batteries:** 在当前 29-sub-test universe 之外,继续加入 Non-overlapping Template、Universal Statistical、Random Excursions 系列与 TestU01 Rabbit,并对 length-skip / admissible 分母做统一报告。
- **更长样本期与更广资产集:** 把方法外推到衍生品、跨交易所、跨市场。
- **压缩-based 复杂度估计:** Benedetto et al. (2002) 的语言树方法,以及 Ziv & Lempel (1977) 系列 Lempel–Ziv 类方法,作为 alternative randomness 诊断;在本文的 ℓ 与 bitstream 长度区间下功效不佳故未纳入主分析,但在更长 bitstream 上可能提供与 *D* / NIST 互补的诊断价值。
- **低频密钥材料探索:** 同一 33-byte IKM → HKDF-Extract 管线也可作为后续探索的 key-material derivation 方向,但这已经不同于本文的 password-output setting。该方向需要重新定义 threat model、secret management 与认证要求;本文结果只能说明 passive statistical 指标下的 entropy input 质量,不能直接推出生产级 AES key 或 HSM seeding 的安全性。

---

## Chapter 7 — Conclusion

### Recap of the Motivation and Setting

本文出发于一个具体的工程问题:能否把公开、连续可获取的加密货币市场数据,通过适当的统计方法,转化为可用于密码生成的随机比特流?核心难点不在于"能不能产出比特",而在于"产出的比特能否在标准 randomness 检验下成立,以及 throughput 是否实用"。Experiment 1 在原始 tick 序列上明确显示边际熵高但条件可预测——必须聚合;这正是后续 Experiment 2–4 与 Chapter 5 prototype 的出发点。

方法基础有两条:Shternshis & Marmi (2025) 的熵驱动可预测性检验 *D*,与 Onofri et al. (2025) 的"全 offset"构造。本工作在此之上对加密货币 24/7 高频特性做了若干修订(relaxed gate、1-second bar physical-time pipeline、multi-asset XOR combination 等;见 Chapter 3 章首与下文 §7.2)。

本论文的回答是 **yes,但有条件**:在 deployable n ∈ {2, 3, 5} 配置下,加密货币市场数据经标准 HKDF-SHA256 conditioning 后,可产出在本文输出层面指标上与理想 baseline 对齐的 ~98-bit 强密码。该结论限于 passive statistical setting,不覆盖主动操纵或生产 secret 管理;具体回应与边界见 §6.1 与 §6.4。

### Summary of Contributions

本论文的贡献按"方法学 → 应用 → secondary 观察"三层组织。

**(1) 方法学贡献(method-level contributions)。** 本工作把 Shternshis & Marmi (2025) 的 *D* 检验、Onofri et al. (2025) 的全 offset 构造,以及 NIST SP800-22 与 TestU01 Alphabit 的经典 sub-tests,整合进一个统一的 all-offset acceptance + audit 框架,并在 24/7 连续的加密货币市场上评估这一组合电池的表现。在 reused 组件之上,本论文给出四个具体方法学增量:

- **Relaxed gate (§3.4):** 作为 heuristic robustness check,在不采用 Bonferroni / Šidák 的前提下提供 offset 冗余判据。
- **1-second bar physical-time pipeline (§3.5):** 引入第二条聚合轴,在物理时间上显著缓解短程依赖。
- **Multi-asset XOR combination (§3.6):** 定义 bit-domain XOR aggregation,并与 §3.1 的 price-domain aggregation 显式区分。
- **Output Metrics 口径 (§3.7):** 统一报告 throughput 与简化 SP800-90B min-entropy estimate。

HKDF-SHA256(§2.2)作为标准 cryptographic conditioning component 引入,术语介绍服务于 Chapter 5 的应用,本身不计入新贡献。

**(2) 应用贡献(application contribution)。** Chapter 5 给出一个 end-to-end password generator prototype,把 Experiment 4 deployable streams 接入标准 HKDF-SHA256 conditioning 与 70-character rejection sampling,在 3 档 deployable n × 6 validation 月上生成 1,800 个 market passwords,连同 B1 ideal-password 与 B2 ideal-IKM 各 600 个 baseline passwords 共 3,000 个,统一接受字符均匀性 chi-square 与 Shannon entropy 评估。**18 个 market cell 全部通过字符均匀性检验,Shannon entropy 与 baseline 在 ~0.03 bits/char 的 Miller-Madow bias 范围内一致**(详见 §5.2 Table 5.1)——这是"standard cryptographic conditioning 是 deployable streams 转化为可用密码的必要组成"的 prototype 层面证据。

**(3) Secondary 方法学观察(secondary methodological observations)。** 本工作记录两条与 Chapter 2 综述中 UHF 文献(美股、莫斯科交易所)在跨市场层面呼应的观察,作为 by-product 不进入 main contribution;详见 §6.3 Secondary Observations。

- **粗粒度活跃度分层 + 局部 non-monotonicity。** Selected ℓ\* 在 5 资产上呈现两层结构:粗粒度上与 trades/s 同向,细粒度上 SOL / DOGE / BNB 三者不严格单调。
- **1 阶残留更像聚合轴属性。** *D*(*k* = 2) / Runs 的 1 阶残留在 transaction-time 与 1-second bar 轴上差异显著,提示该残留更像采样轴选择带来的属性,而非源数据固有。

其他 design choice 与 scope cap 见 §6.4 limitations and future work。实现代码与处理后输出通过标题页上的 repository link 提供。

---

## References

> *本中文 draft 下方仅保留早期 13 条 anchor entries 的 prose-style 描述,以便快速对照原始 PDF 来源。**完整 bibliography(共 39 条,BibTeX 格式)见 `thesis/references.bib`**;正文 author-year cite 与该 bib 文件一一对应。提交版以 `thesis/main.tex` + `references.bib` 为准。*

1. **Clark, J., & Hengartner, U. (2010).** *On the Use of Financial Data as a Random Beacon.* EVT/WOTE 2010 (also Cryptology ePrint Archive 2010/361).(Reference #1)
2. **Chiba, A., & Ichikawa, S. (2024).** *Random Number Generation Based on Cryptocurrency Prices and Linear Feedback Shift Register.* In 2024 Twelfth International Symposium on Computing and Networking (CANDAR), pp. 142–148. IEEE.(Reference #2)
3. **Landis, D., & Bonneau, J. (2025).** *Randomness Beacons from Financial Data in the Presence of an Active Attacker.* Cryptology ePrint Archive, 2025.(Reference #3)
4. **Bouchaud, J.-P., Mézard, M., & Potters, M. (2002).** *Statistical properties of stock order books: empirical results and models.* Quantitative Finance 2(4), 251–256.(Reference #4)
5. **Cont, R. (2001).** *Empirical properties of asset returns: stylized facts and statistical issues.* Quantitative Finance 1(2), 223–236.(Reference #5)
6. **Shternshis, A., & Marmi, S. (2025).** *Price predictability at ultra-high frequency: Entropy-based randomness test.* Communications in Nonlinear Science and Numerical Simulation 141, 108469. DOI: 10.1016/j.cnsns.2024.108469.(Reference #6)
7. **Onofri, S., Shternshis, A., & Marmi, S. (2025).** *Emergence of Randomness in Temporally Aggregated Financial Tick Sequences.* arXiv:2511.17479 [q-fin.ST].(Reference #7)
8. **Benedetto, D., Caglioti, E., & Loreto, V. (2002).** *Language Trees and Zipping.* Physical Review Letters 88(4), 048702.(Reference #8)
9. **Shternshis, A., Mazzarisi, P., & Marmi, S. (2022).** *Efficiency of the Moscow Stock Exchange before 2022.* Entropy 24(9), 1184. DOI: 10.3390/e24091184.(Reference #9)
10. **Mathew, S. K., Srinivasan, S., Anders, M. A., Kaul, H., Hsu, S. K., Sheikh, F., Agarwal, A., Satpathy, S., & Krishnamurthy, R. K. (2012).** *2.4 Gbps, 7 mW All-Digital PVT-Variation Tolerant True Random Number Generator for 45 nm CMOS High-Performance Microprocessors.* IEEE Journal of Solid-State Circuits 47(11), 2807–2821. DOI: 10.1109/JSSC.2012.2217631.(Reference #10 — newly added for TRNG / electronic-noise example)
11. **Herrero-Collantes, M., & Garcia-Escartin, J. C. (2017).** *Quantum Random Number Generators.* Reviews of Modern Physics 89(1), 015004. DOI: 10.1103/RevModPhys.89.015004.(Reference #11 — newly added for TRNG / quantum-source survey)
12. **Bonneau, J., Clark, J., & Goldfeder, S. (2015).** *On Bitcoin as a Public Randomness Source.* Cryptology ePrint Archive, Report 2015/1015.(Reference #12 — newly added for blockchain randomness candidate)
13. **Pierrot, C., & Wesolowski, B. (2018).** *Malleability of the Blockchain's Entropy.* Cryptography and Communications 10(1), 211–233. DOI: 10.1007/s12095-017-0264-3.(Reference #13 — newly added for blockchain randomness adversarial analysis)

---

## AI Assistance Statement

本论文写作过程中使用了 AI 工具作为辅助。AI 的使用范围包括:帮助查找和整理相关文献线索,协助检查 references 与正文引用的一致性,对实验脚本和论文代码进行 code review,帮助发现潜在的叙述不一致、数据口径不清和 LaTeX 排版问题,并在中文草稿已经形成后辅助翻译和润色英文表达。

AI 没有独立完成本文的研究设计、实验决策或结论判断。所有实验设计、代码运行、数据解释、论文结构选择和最终表述均由作者审查、修改并确认。AI 输出只作为写作和工程检查的辅助材料使用。
