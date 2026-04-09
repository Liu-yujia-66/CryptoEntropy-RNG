# Progress Report: Experiment 2 Temporal Aggregation

**Date:** April 9, 2026  
**Project:** Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation  
**Status:** Experiment 2 In Preparation

## 1. Objective

Experiment 2, titled *Effect of Temporal Aggregation on Randomness "Emergence"*, aims to investigate whether temporal aggregation can reduce short-range dependence in cryptocurrency price-direction sequences and produce bitstreams with stronger randomness-like properties.

Following the findings from Experiment 1, the central question of Experiment 2 is whether increasing the aggregation level in transaction time can suppress local dependence, shorten deterministic run structure, and improve the statistical quality of the extracted bitstreams.

To support this analysis, the asset universe for Experiment 2 was expanded beyond the initial baseline assets. The final selected assets are `BTC`, `ETH`, `BNB`, `SOL`, and `DOGE`.

## 2. Current Scope

The current scope of Experiment 2 is as follows:

- Use monthly Binance aggTrades data rather than short daily samples.
- Apply transaction-time temporal aggregation across multiple sampling intervals.
- Compare how aggregation affects Shannon entropy, autocorrelation, run structure, and related randomness indicators.
- Evaluate whether the observed effect is stable across multiple cryptocurrency market structures rather than being driven by a single asset.

## 3. Asset Selection Rationale

### 3.1 Bitcoin (BTC)

BTC 作为市值最高、流动性最强的加密资产，通常被视为整个加密市场的基准资产。其价格形成过程高度活跃，交易深度充足，因此可以作为高效市场假设下的代表性数据源。

在本研究中，BTC 用于提供一个高流动性、相对成熟市场结构下的基准随机性参考。如果时间聚合方法在 BTC 上仍然无法有效削弱依赖性，那么该方法的普适性将受到明显限制。

### 3.2 Ethereum (ETH)

ETH 作为第二大加密资产，具有与 BTC 不同的生态驱动因素，例如智能合约、DeFi 应用和链上活动等。其交易行为在一定程度上与 BTC 相关，但同时也表现出独立的市场特征。

引入 ETH 的目的是验证实验结果是否能够在多个主流资产上保持一致，从而避免基于单一资产样本得出过强结论。ETH 的加入有助于提升实验结论的稳健性与外推性。

### 3.3 BNB (BNB)

BNB 作为交易所生态代币，其价格行为不仅受到市场供需影响，也受到平台使用需求、手续费机制以及平台活动的驱动。因此，它与传统意义上的主流市场驱动资产存在一定差异。

选择 BNB 的目的是引入一种由“平台机制驱动”的资产类型，从而分析不同市场驱动机制是否会影响随机性提取效果。这有助于检验时间聚合方法是否适用于更广泛的加密资产类别。

### 3.4 Solana (SOL)

SOL 代表高性能区块链资产，交易活跃度较高且波动性显著。相较于 BTC 和 ETH，SOL 的市场结构更容易受到短期交易行为和流动性变化的影响。

引入 SOL 有助于研究在高波动、高频交易环境下，时间聚合是否仍然能够有效削弱序列中的依赖性，并改善统计随机性指标。如果在 SOL 上也能观察到一致改善，将进一步增强方法的鲁棒性。

### 3.5 Dogecoin (DOGE)

DOGE 作为典型的情绪驱动型资产，其价格波动往往受到社交媒体传播、市场情绪以及短期投机行为的强烈影响，因此通常呈现出较高的噪声特征。

选择 DOGE 的目的是构造一个“极端市场情形”，用于测试在高度非理性和噪声主导的市场条件下，时间聚合方法是否仍然能够提取出具有统计随机性的序列。DOGE 的纳入可以增强实验设计的辨别力与讨论深度。

## 4. Summary

最终选择 `BTC`、`ETH`、`BNB`、`SOL` 和 `DOGE` 这五个资产，是为了在资产流动性、市场成熟度、生态驱动机制和价格行为特征之间取得平衡。

其中，`BTC` 和 `ETH` 提供主流高流动性基准，`BNB` 和 `SOL` 提供不同类型的主流扩展样本，而 `DOGE` 则作为情绪驱动和噪声更强的对照资产。这样的组合有助于系统评估时间聚合方法在不同市场结构下的适用性与稳健性。

资产选择只是 Experiment 2 设计的一部分。后续进展将继续补充时间聚合方法设定、采样区间、统计检验结果，以及不同 `k` 值下的比较分析。
