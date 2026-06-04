from __future__ import annotations

# Experiment 3 / 4 共用的 test battery 编排层：把三个平级 battery（src.stats 5 个、
# nistrng 7 个、TestU01 Alphabit 最多 17 个）合并，加上 sanity 长度档 schema。
# 主入口 full_battery(bits, ...) 对单条流返回 {sub_test: (p_value, sanity_valid)}，
# 不做 offset 聚合或 pass-rate 判定（交给外层 runner）。
# 冒烟测试：python src/battery.py

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from src.stats import (
    _adaptive_k,
    approximate_entropy_test,
    entropy_predictability_test,
    monobit_test,
    runs_test,
)
from src.nist_extended import (
    NISTRNG_CALLS,
    SUB_TESTS_FROM_NISTRNG_BASE,
    ensure_int64,
    normalize_result,
    run_nistrng,
)
from src.testu01_alphabit import ALPHABIT_SUB_TESTS, run_alphabit

# Sanity 长度档（schema）
# (下界 bit 数, 标签)。bracket_for_length() 返回标签。
SANITY_BRACKETS: list[tuple[int, str]] = [
    (5_000, "5K"),
    (10_000, "10K"),
    (25_000, "25K"),
    (50_000, "50K"),
    (100_000, "100K"),
    # 200K 对应 Exp 4 n=3 BTC+ETH+SOL fused stream 的月长上沿
    # （per_month_throughput.csv 实测 168K–240K bits/月）。
    (200_000, "200K"),
    # 500K 档当前 Exp 3/4 单 cell 都到不了，bracket_for_length() 永不返回
    # "500K"，跑它只是浪费几十分钟。等真有 ≥500K 的多月 concat / 更大 fusion
    # 流时再取消注释（记得同步 _smoke_test 的 boundary_cases）。
    # (500_000, "500K"),
]

# 当 len(bits) < 5_000 时的兜底标签。实测没有 cell 落到 5,009 bits 以下，
# 所以这条不期望触发；保留作防御。
BELOW_MIN_BRACKET = "below_5K"


def bracket_for_length(n: int) -> str:
    """把单 offset 的 bit 数映射到 sanity 长度档标签。

    返回 SANITY_BRACKETS 中的标签之一；若 n < 第一档下界，返回
    `BELOW_MIN_BRACKET`（兜底，实测 cell 不会触发）。
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


# Sub-test 名清单（universe）
# CSV `sub_test` 列：5 个走 src/stats.py 的 sub-test 名字。
SUB_TESTS_FROM_STATS: list[str] = [
    "D_adaptive",
    "D_k2",
    "Monobit",
    "Runs",
    "ApEn",
]

# 三 battery 并集；`ALL_SUB_TESTS` 是 sub-test 的 universe。**长度恒**：
# 5 (stats.py) + 7 (nistrng 含 CumSum / Serial 拆分) + 17 (Alphabit) = 29。
# 注意：full_battery() 对某条流的实际输出可能少于 29——TestU01 Alphabit 在短
# 流上自己 skip 长-L 子项（length eligibility，详 src/testu01_alphabit.py）。
ALL_SUB_TESTS: list[str] = (
    SUB_TESTS_FROM_STATS + SUB_TESTS_FROM_NISTRNG_BASE + ALPHABIT_SUB_TESTS
)


# 公开 coordinator


def full_battery(
    bits: np.ndarray,
    sanity_matrix: dict[tuple[str, str], bool] | None = None,
    alphabit_pvals: dict[str, float] | None = None,
) -> dict[str, tuple[float, bool | None]]:
    """对单条 bit 流跑完整 battery，返回 p 值 + sanity 标签。

    battery 三个来源：
      - 5 个走 src/stats.py：D_adaptive, D_k2, Monobit, Runs, ApEn
      - 7 个走 nistrng：BlockFrequency, CumSum_forward/backward, LongestRun,
        DFT, Serial_m/m_minus_1
      - 最多 17 个走 TestU01 Alphabit（src/testu01_alphabit.py）

    参数：
        bits: 1D np.ndarray of bits ∈ {0, 1}。任何整数 dtype 都 OK。
        sanity_matrix: 可选 dict，key 是 (sub_test_csv_name, bracket_label)，
            value 是该 (sub-test, bracket) 是否通过 sanity 校准。缺失的 key
            默认 `False`（保守：未知 = 不可信）。传 `None` 跳过 sanity 查表。
        alphabit_pvals: 可选 dict[schema_name → p_value]，该流预先算好的
            Alphabit 结果。**批处理路径**：外层 runner 用
            `testu01_alphabit.run_alphabit_batch()` 对整个 cell 的所有 offset
            一次性算 Alphabit，再把每条流的结果传进来——driver 进程只起一次。
            传 `None` 时，full_battery 自己对这单条流调 `run_alphabit()`
            （per-stream，每次起一个 driver 进程；方便但慢）。传 `{}` 则
            完全跳过 Alphabit（只跑 12 个固定项，不需要 driver）。

    返回：
        dict[`sub_test_name` → (`p_value`, `sanity_valid`)]。
        **长度不再恒定**：12 个固定项（stats.py 5 + nistrng 7，永远都在）
        + 该流实际跑出的 Alphabit 子项（11–17 个，随流长变——TestU01 自己在
        短流上跳长-L 子项，详 testu01_alphabit）。故总长一般 23–29。
        某 Alphabit 子项缺席 = TestU01 没在该长度跑它，是正常 length
        eligibility，不是错误。

    抛出：
        FileNotFoundError —— alphabit_pvals 为 None 且 alphabit_driver 未编译。
        ValueError / RuntimeError —— 由底层测试 / driver 在输入异常时抛出。
    """
    n = bits.size

    # 5 个旧 sub-test 走 src/stats.py
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

    # 5 个新 sub-test 走 nistrng（CumSum + Serial 各拆 2，总 7 行）。
    # int64 cast 一次复用。
    bits_i64 = ensure_int64(bits)
    for csv_name, nistrng_key in NISTRNG_CALLS:
        score = run_nistrng(nistrng_key, bits_i64)
        rows.extend(normalize_result(csv_name, score))

    # TestU01 Alphabit（最多 17 个 sub-test）。结果数随流长变——TestU01 自己
    # 在短流上跳长-L 子项，11–17 个都算正常。若 caller 传了 alphabit_pvals
    # （外层 runner 对整个 cell 批量算好的，高效路径），直接用；传 None 则
    # 对这单条流调一次 driver；传 {} 则跳过 Alphabit。
    if alphabit_pvals is None:
        alphabit_pvals = run_alphabit(bits)
    for name, p in alphabit_pvals.items():
        rows.append((name, float(p)))

    # Sanity-valid join（可选，看外层 runner 是否传 sanity_matrix）
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


# 冒烟测试（跑法：`python src/battery.py`）


def _smoke_test() -> int:
    """本 coordinator 的自包含冒烟测试。

    验证 4 件事：
      [1] bracket_for_length 边界映射
      [2] full_battery 在 10K bits 上的 12 个固定 sub-test 结构 + p 值合理性
          （alphabit_pvals={} 跳过 driver，与 nistrng / stats 解耦）
      [2b] 注入的 alphabit_pvals 正确合并进结果
      [3] full_battery 在 100K bits 上不触发 nistrng int8 溢出 RuntimeWarning
          （int64 cast fix 的回归测试）
      [4] sanity_matrix join 行为

    全 PASS 返回 0，任何 FAIL 返回 1。整体 ~3-5 秒跑完。

    跑法：
        python src/battery.py
    """
    import time
    import warnings

    print("=" * 70)
    print("src/battery.py smoke test")
    print("=" * 70)
    failures = 0

    def _check(
        label: str, ok: bool, msg_on_pass: str = "", msg_on_fail: str = ""
    ) -> int:
        """打印 "[OK/FAIL] label  (msg)" 并返回 0/1 给 failure 累加。"""
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
        (199_999, "100K"),
        (200_000, "200K"),
        (499_999, "200K"),
        (500_000, "200K"),
        (1_000_000, "200K"),
    ]
    for n, expected in boundary_cases:
        got = bracket_for_length(n)
        failures += _check(
            f"bracket_for_length({n:>7}) = {got!r:<11}",
            got == expected,
            msg_on_pass=f"expected {expected!r}",
            msg_on_fail=f"expected {expected!r}",
        )

    # ---- [2] 12 个固定项（alphabit_pvals={} → 不需要 driver）---------------
    print("\n[2] full_battery() 12 fixed sub-tests (alphabit_pvals={})")
    _FIXED = SUB_TESTS_FROM_STATS + SUB_TESTS_FROM_NISTRNG_BASE
    bits = np.random.default_rng(42).integers(0, 2, 10_000).astype(np.uint8)
    result = full_battery(bits, alphabit_pvals={})

    failures += _check(
        "12 fixed sub-tests, in order",
        list(result.keys()) == _FIXED,
        msg_on_pass=f"got {len(result)}",
        msg_on_fail=f"got {list(result.keys())}",
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

    # ---- [2b] full_battery 把注入的 alphabit_pvals 合并进结果 --------------
    print("\n[2b] full_battery() merges injected alphabit_pvals")
    fake_alpha = {
        "Alphabit_HammingCorr_L32": 0.4242,
        "Alphabit_RandomWalk1_L64_H": 0.7000,
    }
    merged = full_battery(bits, alphabit_pvals=fake_alpha)
    failures += _check(
        "12 fixed + 2 injected Alphabit = 14 entries",
        len(merged) == 14,
        msg_on_pass=f"got {len(merged)}",
        msg_on_fail=f"got {len(merged)}",
    )
    failures += _check(
        "injected Alphabit p-values present and correct",
        merged.get("Alphabit_HammingCorr_L32", (None,))[0] == 0.4242
        and merged.get("Alphabit_RandomWalk1_L64_H", (None,))[0] == 0.7000,
        msg_on_fail="injected Alphabit rows missing or wrong",
    )

    # ---- [3] 100K bits 上 CumSum int8 溢出回归测试 -------------------------
    print("\n[3] full_battery() on 100K bits — CumSum int64 cast regression")
    bits_100k = np.random.default_rng(123).integers(0, 2, 100_000).astype(np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        try:
            t0 = time.perf_counter()
            result_100k = full_battery(bits_100k, alphabit_pvals={})
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
    result_joined = full_battery(bits, sanity_matrix=fake_matrix, alphabit_pvals={})
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
