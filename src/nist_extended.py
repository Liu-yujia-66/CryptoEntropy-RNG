from __future__ import annotations

# nistrng (Pasqualini SP800-22 R1A Python reimpl) wrapper —— battery 中
# 来自 nistrng 的那部分（5 个测试，CumSum / Serial 各拆 2 → 7 行 schema）。
#
# 这个文件**只管 nistrng**：不调 stats、不调 TestU01。三 battery 的编排在
# `src/battery.py`，它从这里 import 下面三个 helper + 名字列表。
#
# 关键的 nistrng 1.2.3 内部行为（已被 smoke test 验证）：
#
# - **不用 `.passed`**：nistrng 内部硬编码 α=0.01，本项目要 α-agnostic 让
#   caller 拿原始 p 值自己跟阈值比。
#
# - **不用 `.score`**：`.score` 是 `@property`，返回的是
#   `float(numpy.nanmean(self._score_list))`。
#   单 p 测试（Monobit, BlockFreq, DFT, LongestRun）正确；但**双 p 测试**
#   （CumSum F/B 按 §2.13；Serial m / m-1 按 §2.16），`.score` 会**把两个
#   p 平均成一个**，无声偏离 NIST 标准（NIST 把两者当作独立 p 值分别报告）。
#   所以 wrapper 直接读 `result._score_list`（私有属性，未来 nistrng 升级
#   API 时本 wrapper 会爆，需要回头检查；公开 `.score` 完全弃用）。
#
# - **int64 cast**：nistrng 1.2.3 `CumulativeSumsTest._execute` 用 scalar
#   int8 累加；n >~ 10K 时无声溢出污染 CumSum p 值。本 wrapper 在 `ensure_int64`
#   里一次 cast，所有下游 nistrng 调用复用。代价可忽略
#   （100K bits int64 ≈ 800 KB）。
#
# 输入格式：bits 数组取值 ∈ {0, 1}，dtype int8 / uint8 / int64 / bool 都 OK。
# **不要**传 -1 / +1：nistrng 内部自动做 0 → -1 转换，传 -1/+1 会变成
# -3 / +1 垃圾结果。
#
# 命名约定（plan §1.6）：
#
# - CSV 输出列 `sub_test` 用人类友好名，定义在下面的
#   `SUB_TESTS_FROM_NISTRNG_BASE`
# - 查 nistrng dict-key 用 nistrng 自己的 key（如 `'frequency_within_block'`、
#   `'cumulative sums'` 注意有空格），映射表在 `NISTRNG_CALLS`
#
# 冒烟测试在 `src/battery.py` 里（端到端跑 full_battery，自动覆盖本 wrapper
# 的 int64 cast 回归 + CumSum / Serial 拆分行为）。

import numpy as np
import nistrng


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# CSV `sub_test` 列：nistrng 来源的 sub-test 名字。冒烟测试 (2026-05-18)
# 已通过 `_score_list.shape` 实测确认：
#   - BlockFreq / LongestRun / DFT: 0-d ndarray → 单行
#   - CumSum:    1-d (2,) → CumSum_forward / CumSum_backward
#   - Serial:    1-d (2,) → Serial_m / Serial_m_minus_1
SUB_TESTS_FROM_NISTRNG_BASE: list[str] = [
    "BlockFrequency",
    "CumSum_forward",
    "CumSum_backward",
    "LongestRun",
    "DFT",
    "Serial_m",
    "Serial_m_minus_1",
]

# CSV 友好名 → nistrng SP800_22R1A_BATTERY dict key。key 必须 verbatim ——
# 注意 `'cumulative sums'` 是字面空格，不是下划线。
NISTRNG_CALLS: list[tuple[str, str]] = [
    ("BlockFrequency", "frequency_within_block"),
    ("CumSum", "cumulative sums"),
    ("LongestRun", "longest_run_ones_in_a_block"),
    ("DFT", "dft"),
    ("Serial", "serial"),
]


# ---------------------------------------------------------------------------
# Helper 函数
# ---------------------------------------------------------------------------


def ensure_int64(bits: np.ndarray) -> np.ndarray:
    """调 nistrng 之前 cast 到 int64。

    单点防御 nistrng 1.2.3 `CumulativeSumsTest._execute` 的 scalar int8
    累加 bug —— 在 n >~ 10K 时会无声溢出污染 p 值。
    一律 cast（而不是只对 CumSum 特判）成本可忽略（100K bits int64 ≈ 800 KB），
    省去逐 sub-test 特殊处理。
    """
    return np.asarray(bits, dtype=np.int64)


def run_nistrng(test_name: str, bits_i64: np.ndarray) -> np.ndarray:
    """跑单个 nistrng sub-test，返回原始 `_score_list` ndarray。

    见文件顶部 docstring：不用 `.score`（双 p 测试会被 nanmean 平均），不用
    `.passed`（内置 α=0.01 硬编码）。直接读私有 `_score_list` 保留双 p 值。

    返回：
        单 p 测试 → 0-d ndarray（例如 `array(0.475)`），
        双 p 测试（CumSum, Serial）→ 1-d 长度 2 的 ndarray，
        其他形状 → 当前没用到的测试可能返回，留作 defensive。
    """
    test = nistrng.SP800_22R1A_BATTERY[test_name]
    result, _exec_time = test.run(bits_i64)
    return result._score_list


def normalize_result(
    name_in_csv: str,
    raw_scores: np.ndarray,
) -> list[tuple[str, float]]:
    """把 nistrng `_score_list` 转成 1 行或 2 行 (sub_test, p_value)。

    判别用 `numpy.ndim`（**不**用 `hasattr(__len__)`，因为 0-dim ndarray
    也有 `__len__` 但不能 `len()`，那是个隐藏坑）：

    - ndim 0  →  单行：[(name_in_csv, float(raw))]
    - 1-d 长度 2  →  两行，语义后缀：
        * CumSum  →  `_forward` / `_backward`     (NIST §2.13)
        * Serial  →  `_m` / `_m_minus_1`          (NIST §2.16)
    - 其他形状（防御）  →  按 `_0`, `_1`, ... 编号后缀

    CumSum / Serial 的命名跟 plan §1.6 schema 对齐。
    """
    if np.ndim(raw_scores) == 0:
        return [(name_in_csv, float(raw_scores))]

    score_list = [float(s) for s in np.asarray(raw_scores).ravel()]

    if name_in_csv == "CumSum" and len(score_list) == 2:
        return [
            ("CumSum_forward", score_list[0]),
            ("CumSum_backward", score_list[1]),
        ]
    if name_in_csv == "Serial" and len(score_list) == 2:
        return [
            ("Serial_m", score_list[0]),
            ("Serial_m_minus_1", score_list[1]),
        ]
    # 防御 fallback：未预期的多输出按 `_0`, `_1`, ... 编号
    return [(f"{name_in_csv}_{i}", s) for i, s in enumerate(score_list)]
