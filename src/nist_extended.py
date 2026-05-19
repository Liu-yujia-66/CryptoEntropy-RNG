from __future__ import annotations

# Experiment 3 的 NIST 扩展 sub-test wrapper（v3.1 fifth pass）。

# 提供 `full_battery(bits, sanity_matrix=None)` —— Exp 3 sanity check runner
# 和 Exp 3 主 per-cell runner 共用的单一 test battery 协调函数。契约见 plan §0.3：

# - 输入：单条 1D `bits` 数组（一个 offset 的流，或一条融合流）
# - 输出：dict[`sub_test_name` → (`p_value`, `sanity_valid`)]
# - **不做** offset 聚合 / ≥80% pass-rate 判定（这两件交给外层 runner）
# - **不用** nistrng 的 `.passed`（内置 α=0.01 硬编码）；wrapper 直接读
#   `_score_list` 私有属性返回原始 p 值，由调用方套自己的 α，保持 α-agnostic。
#   （为什么不用 `.score`：CumSum / Serial 的 `.score` 是 `_score_list` 的
#   nanmean，会把双 p 平均成单 p 偏离 NIST 标准——详见 `_run_nistrng` docstring。）

# 组成（plan §1.3 v3.1 fifth pass）：

# - 5 个"旧" sub-test 复用 `src/stats.py`，保 Exp 3 数字跟 Exp 1 / Exp 2 已发表
#   结果一致：D (adaptive k), D (k=2), Monobit, Runs, Approximate Entropy
# - 5 个"新" sub-test 来自 `nistrng.SP800_22R1A_BATTERY`：Block Frequency,
#   Cumulative Sums, Longest Run, DFT, Serial。CumSum 返回两个 p 值
#   (forward + backward，按 NIST SP 800-22 §2.13)，Serial 也返回两个
#   (ψ²_m + ψ²_{m-1}，按 §2.16)；wrapper 通过 `_normalize_result` 自动展开
#   成 7 行 ——> 总计 5 + 7 = 12 个 sub-test row。

# 输入格式（plan §1.3）：

# - bits 数组取值 ∈ {0, 1}，dtype int8 / uint8 / int64 / bool 都 OK
# - **不要**传 -1 / +1；nistrng 内部自动做 0 → -1 转换，传 -1/+1 会变成
#   -3 / +1 垃圾结果
# - wrapper 内部 cast 到 int64，绕开 nistrng 1.2.3 `CumulativeSumsTest`
#   的 int8 累加溢出 bug（10K bit 起就会污染 CumSum p 值）。
#   代价可忽略（100K bits int64 ≈ 800 KB）。

# 命名约定（plan §1.6）：

# - CSV 输出列 `sub_test` 用人类友好名，定义在下面的
#   `SUB_TESTS_FROM_STATS` 和 `SUB_TESTS_FROM_NISTRNG_BASE`
# - 查 `nistrng` dict-key 用 nistrng 自己的 key（如 `'frequency_within_block'`、
#   `'cumulative sums'` 注意有空格），映射表在 `_NISTRNG_CALLS`

# 冒烟测试（本文件底部内置 `_smoke_test`）：

#     python src/nist_extended.py

# 预期 ~3-5 秒跑完，验证 4 件事：(1) bracket_for_length 边界、(2) 10K bit
# full_battery 结构 + p 值合理性、(3) 100K bit CumSum int64 cast 回归
# （用 RuntimeWarning → error 升级强制断言）、(4) sanity_matrix join 行为。
# 全 PASS 退 0，任何 FAIL 退 1，可直接进 CI。


# 把项目根加进 sys.path，这样本文件作为 script 跑（`python src/nist_extended.py`
# 跑底部冒烟测试）时 `from src.xxx import` 才解析得到。被 import 时无副作用。
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
import nistrng

from src.stats import (
    _adaptive_k,
    approximate_entropy_test,
    entropy_predictability_test,
    monobit_test,
    runs_test,
)

# ---------------------------------------------------------------------------
# 常量（plan §1.4 sanity 长度档，§1.6 sub_test 名清单）
# ---------------------------------------------------------------------------

# Sanity 长度档：(下界, 标签)。bracket_for_length() 返回标签。
SANITY_BRACKETS: list[tuple[int, str]] = [
    (5_000, "5K"),
    (10_000, "10K"),
    (25_000, "25K"),
    (50_000, "50K"),
    (100_000, "100K"),
]

# 当 len(bits) < 5_000 时的兜底标签。按 plan §1.4.1 cell-length inspection 实测，
# 没有任何 Exp 2 cell 落到 5,009 bits 以下，所以这条不期望触发；保留作防御。
BELOW_MIN_BRACKET = "below_5K"

# CSV `sub_test` 列：5 个复用 sub-test 的名字（走 src/stats.py 算，
# 保 Exp 1 / Exp 2 已发表数字一致）。
SUB_TESTS_FROM_STATS: list[str] = [
    "D_adaptive",
    "D_k2",
    "Monobit",
    "Runs",
    "ApEn",
]

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

ALL_SUB_TESTS: list[str] = SUB_TESTS_FROM_STATS + SUB_TESTS_FROM_NISTRNG_BASE
# 合计 = 5 (stats.py) + 7 (nistrng 含 CumSum / Serial 拆分) = 12 行

# CSV 友好名 → nistrng SP800_22R1A_BATTERY dict key。key 必须 verbatim ——
# 注意 `'cumulative sums'` 是字面空格，不是下划线。
_NISTRNG_CALLS: list[tuple[str, str]] = [
    ("BlockFrequency", "frequency_within_block"),
    ("CumSum", "cumulative sums"),
    ("LongestRun", "longest_run_ones_in_a_block"),
    ("DFT", "dft"),
    ("Serial", "serial"),
]


# ---------------------------------------------------------------------------
# Helper 函数
# ---------------------------------------------------------------------------


def bracket_for_length(n: int) -> str:
    """把单 offset 的 bit 数映射到 sanity 长度档标签。

    返回 "5K" / "10K" / "25K" / "50K" / "100K" 之一；若 n < 5_000 返回
    "below_5K"（兜底，按 §1.4.1 Exp 2 cell 不会触发）。
    """
    if n < SANITY_BRACKETS[0][0]:
        return BELOW_MIN_BRACKET
    label = SANITY_BRACKETS[0][1]
    for threshold, current_label in SANITY_BRACKETS:
        if n >= threshold:
            label = current_label
        else:
            break
    return label


def _ensure_int64(bits: np.ndarray) -> np.ndarray:
    """调 nistrng 之前 cast 到 int64。

    单点防御 nistrng 1.2.3 `CumulativeSumsTest._execute` 的 scalar int8
    累加 bug —— 在 n >~ 10K 时会无声溢出污染 p 值。
    一律 cast（而不是只对 CumSum 特判）成本可忽略（100K bits int64 ≈ 800 KB），
    省去逐 sub-test 特殊处理。
    """
    return np.asarray(bits, dtype=np.int64)


def _run_nistrng(test_name: str, bits_i64: np.ndarray) -> np.ndarray:
    """跑单个 nistrng sub-test，返回原始 `_score_list` ndarray。

    关键细节（nistrng 1.2.3 内部行为，冒烟测试验证）：
    `Result.score` 是一个 `@property`，返回的是
    `float(numpy.nanmean(self._score_list))`。
    对单 p 测试（Monobit, BlockFreq, DFT, LongestRun）这跟原始值一致；
    但对双 p 测试（CumSum F/B 按 §2.13；Serial m / m-1 按 §2.16），
    `.score` 会**把两个 p 平均成一个**，无声偏离 NIST 标准（NIST 把两者
    当作独立 p 值分别报告）。

    所以本 wrapper 直接读 `result._score_list` 保留双 p 值。
    Caveat：`_score_list` 是私有属性（前缀 `_`），未来 nistrng 升级 API
    时本 wrapper 会爆，需要回头检查。公开的 `.score` 完全弃用。

    `.passed` 也不用：nistrng 内部硬编码 α=0.01，caller 用自己的 α=0.01
    跟这里返回的原始值比较。

    返回：
        单 p 测试 → 0-d ndarray（例如 `array(0.475)`），
        双 p 测试（CumSum, Serial）→ 1-d 长度 2 的 ndarray，
        其他形状 → 当前没用到的测试可能返回，留作 defensive。
    """
    test = nistrng.SP800_22R1A_BATTERY[test_name]
    result, _exec_time = test.run(bits_i64)
    return result._score_list


def _normalize_result(
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


# ---------------------------------------------------------------------------
# 公开 coordinator
# ---------------------------------------------------------------------------


def full_battery(
    bits: np.ndarray,
    sanity_matrix: dict[tuple[str, str], bool] | None = None,
) -> dict[str, tuple[float, bool | None]]:
    """对单条 bit 流跑所有 sub-test，返回 p 值 + sanity 标签。

    契约（plan §0.3 v3.1 fifth pass）：

    - 输入：单条 1D `bits` ∈ {0, 1}。流长由 caller 负责（如 plan §1.4
      MIN_BIT_COUNT = 2000，由外层 runner 强制）。
    - 输出：dict[`sub_test_name` → (`p_value`, `sanity_valid`)]
      * `sub_test_name`：CSV 友好名（见 plan §1.6 映射表）
      * `p_value`：`_score_list` 原始元素（**不是** `.score`，后者对 CumSum /
        Serial 会被 nanmean 平均），caller 套自己的 α=0.01
      * `sanity_valid`：从 sanity_matrix 查出的 bool；若 sanity_matrix 为 None
        则返回 None（sanity check runner 不传；Exp 3 主 runner 传）

    参数：
        bits: 1D np.ndarray of bits ∈ {0, 1}。任何整数 dtype 都 OK。
        sanity_matrix: 可选 dict，key 是 (sub_test_csv_name, bracket_label) 元组，
            value 是该 (sub-test, bracket) 是否通过 sanity 校准。
            缺失的 key 默认为 `False`（保守：未知 = 不可信）。
            传 `None` 完全跳过 sanity 查表（sanity check 自身跑表阶段用）。

    返回：
        dict，key 是 sub_test 名，**长度恒为 12**（冒烟测试 2026-05-18 实测
        确认 nistrng 1.2.3 Serial 也产双 p）：5 个 stats.py 旧 sub-test
        + 7 个 nistrng 新 sub-test（含 CumSum 拆 forward/backward 和 Serial
        拆 m / m_minus_1）。每个 value 是 `(p_value, sanity_valid)` tuple。

    抛出：
        ValueError / RuntimeError —— 由底层测试在输入异常时抛出。
    """
    n = bits.size

    # ------------------------------------------------------------------
    # 5 个旧 sub-test 走 src/stats.py（保 Exp 1 / Exp 2 数字一致）
    # ------------------------------------------------------------------
    k_adaptive = _adaptive_k(n)
    _, _, p_d_adaptive = entropy_predictability_test(
        bits, history_length=k_adaptive - 1
    )
    _, _, p_d_k2 = entropy_predictability_test(bits, history_length=1)
    _, p_mono = monobit_test(bits)
    _, p_runs = runs_test(bits)
    _, p_apen = approximate_entropy_test(bits)

    rows: list[tuple[str, float]] = [
        ("D_adaptive", float(p_d_adaptive)),
        ("D_k2", float(p_d_k2)),
        ("Monobit", float(p_mono)),
        ("Runs", float(p_runs)),
        ("ApEn", float(p_apen)),
    ]

    # ------------------------------------------------------------------
    # 5 个新 sub-test 走 nistrng。int64 cast 一次复用。
    # ------------------------------------------------------------------
    bits_i64 = _ensure_int64(bits)
    for csv_name, nistrng_key in _NISTRNG_CALLS:
        score = _run_nistrng(nistrng_key, bits_i64)
        rows.extend(_normalize_result(csv_name, score))

    # ------------------------------------------------------------------
    # Sanity-valid join（可选，看外层 runner 是否传 sanity_matrix）
    # ------------------------------------------------------------------
    bracket = bracket_for_length(n)
    result: dict[str, tuple[float, bool | None]] = {}
    for sub_test, p in rows:
        if sanity_matrix is None:
            valid: bool | None = None
        else:
            # 保守默认：未知 (sub-test, bracket) 组合视为 sanity-invalid。
            # 外层 runner 可以选择把这些标 N/A。"below_5K" bracket 会走这条分支。
            valid = sanity_matrix.get((sub_test, bracket), False)
        result[sub_test] = (p, valid)

    return result


# ---------------------------------------------------------------------------
# 冒烟测试（跑法：`python src/nist_extended.py`）
# ---------------------------------------------------------------------------


def _smoke_test() -> int:
    """本 wrapper 的自包含冒烟测试。

    验证 4 件事：
      [1] bracket_for_length 边界映射
      [2] full_battery 在 10K bits 上返回 12 行，结构 / p 值合理
      [3] full_battery 在 100K bits 上不触发 nistrng int8 溢出 RuntimeWarning
          （int64 cast fix 的回归测试）
      [4] sanity_matrix join 行为

    全 PASS 返回 0，任何 FAIL 返回 1。整体 ~3-5 秒跑完。

    跑法：
        python src/nist_extended.py
    """
    import time
    import warnings

    print("=" * 70)
    print("src/nist_extended.py smoke test")
    print("=" * 70)
    failures = 0

    def _check(
        label: str, ok: bool, msg_on_pass: str = "", msg_on_fail: str = ""
    ) -> int:
        """打印 "[OK/FAIL] label  (msg)" 并返回 0/1 给 failure 累加。

        msg_on_pass / msg_on_fail 可以为空（不显示括号注释）。
        两个方向都想显示同样信息（如实测值）时，两个参数传同一串。
        """
        mark = "OK " if ok else "FAIL"
        msg = msg_on_pass if ok else msg_on_fail
        suffix = f"  ({msg})" if msg else ""
        print(f"  [{mark}] {label}{suffix}")
        return 0 if ok else 1

    # ---- [1] bracket_for_length 边界 ---------------------------------------
    print("\n[1] bracket_for_length() boundary mapping")
    boundary_cases = [
        (4_999, "below_5K"),
        (5_000, "5K"),
        (9_999, "5K"),
        (10_000, "10K"),
        (24_999, "10K"),
        (25_000, "25K"),
        (50_000, "50K"),
        (99_999, "50K"),
        (100_000, "100K"),
        (200_000, "100K"),
    ]
    for n, expected in boundary_cases:
        got = bracket_for_length(n)
        failures += _check(
            f"bracket_for_length({n:>7}) = {got!r:<11}",
            got == expected,
            msg_on_pass=f"expected {expected!r}",
            msg_on_fail=f"expected {expected!r}",
        )

    # ---- [2] 10K bits full_battery 结构检查 --------------------------------
    print("\n[2] full_battery() on 10K bits — structure + p-value sanity")
    bits = np.random.default_rng(42).integers(0, 2, 10_000).astype(np.uint8)
    t0 = time.perf_counter()
    result = full_battery(bits)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    n_rows = len(result)
    failures += _check(
        "rows == 12",
        n_rows == 12,
        msg_on_pass=f"got {n_rows}",
        msg_on_fail=f"got {n_rows}",
    )

    keys = list(result.keys())
    failures += _check(
        "keys match ALL_SUB_TESTS",
        keys == ALL_SUB_TESTS,
        msg_on_fail="key order mismatch",
    )

    p_values = [p for p, _ in result.values()]
    failures += _check(
        "all p ∈ [0, 1]",
        all(0.0 <= p <= 1.0 for p in p_values),
        msg_on_pass=f"min={min(p_values):.4f}, max={max(p_values):.4f}",
        msg_on_fail=f"min={min(p_values):.4f}, max={max(p_values):.4f}",
    )

    failures += _check(
        "sanity_valid all None",
        all(v is None for _, v in result.values()),
        msg_on_fail="expected None when sanity_matrix=None",
    )
    print(f"  wall-clock: {elapsed_ms:.1f} ms")

    print("\n  Sub-test p-values:")
    for name, (p, _) in result.items():
        print(f"    {name:25s} p = {p:.6f}")

    # ---- [3] 100K bits 上 CumSum int8 溢出回归测试 -------------------------
    print("\n[3] full_battery() on 100K bits — CumSum int64 cast regression")
    bits_100k = np.random.default_rng(123).integers(0, 2, 100_000).astype(np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        try:
            t0 = time.perf_counter()
            result_100k = full_battery(bits_100k)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"  [OK ] no RuntimeWarning fired (int64 cast working)")
            print(f"  [OK ] {len(result_100k)} rows, wall-clock {elapsed_ms:.1f} ms")
            print(
                f"  [OK ] CumSum forward = {result_100k['CumSum_forward'][0]:.6f}, "
                f"backward = {result_100k['CumSum_backward'][0]:.6f}"
            )
        except RuntimeWarning as exc:
            failures += 1
            print(f"  [FAIL] RuntimeWarning fired (int64 cast broken): {exc}")

    # ---- [4] sanity_matrix join 行为 ---------------------------------------
    print("\n[4] sanity_matrix join (synthetic matrix on 10K bracket)")
    fake_matrix = {
        ("Monobit", "10K"): True,
        ("DFT", "10K"): False,
        # 其他 key 故意不填 → wrapper 应该默认走 False
    }
    bits = np.random.default_rng(7).integers(0, 2, 10_000).astype(np.uint8)
    result_joined = full_battery(bits, sanity_matrix=fake_matrix)
    join_cases = [
        ("Monobit  (matrix says True)", result_joined["Monobit"][1], True),
        ("DFT      (matrix says False)", result_joined["DFT"][1], False),
        ("Runs     (missing → default)", result_joined["Runs"][1], False),
    ]
    for label, got, expected in join_cases:
        ok = got == expected
        failures += 0 if ok else 1
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {label}: got {got}, expected {expected}")

    # ---- 总结 --------------------------------------------------------------
    print("\n" + "=" * 70)
    if failures == 0:
        print("Smoke test PASSED")
    else:
        print(f"Smoke test FAILED — {failures} check(s) failed")
    print("=" * 70)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(_smoke_test())
