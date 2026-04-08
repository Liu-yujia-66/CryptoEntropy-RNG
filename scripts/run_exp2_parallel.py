from __future__ import annotations

"""
Parallel batch runner for Experiment 2.

Edit K_VALUES / MONTHS / ASSETS / MAX_ROWS / MAX_WORKERS below, then run:
    python scripts/run_exp2_parallel.py
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# 要批量测试的 transaction-time sampling 步长
K_VALUES = [50, 100, 200, 500, 1000, 2000, 5000]
# K_VALUES = [1000, 2000]

# 要处理的月度文件
MONTHS = ["2026-01", "2026-02", "2026-03"]

# 要处理的资产
ASSETS = ["BTCUSDT", "ETHUSDT"]

# 调试时可以限制每个文件读取的行数；正式全量运行时改成 None
MAX_ROWS: int | None = None
# MAX_ROWS = 100000

# 并发 worker 数；默认先用 2
MAX_WORKERS = 3

# 限制每个子进程内部的数值库线程数，避免 worker 各自再开很多线程
PER_PROCESS_NUM_THREADS = "1"


def build_command(project_root: Path, sampling_k: int) -> list[str]:
    command = [
        str(project_root / ".venv" / "bin" / "python"),
        "scripts/exp2_aggregation.py",
        "--sampling-k",
        str(sampling_k),
        "--months",
        *MONTHS,
        "--assets",
        *ASSETS,
    ]
    if MAX_ROWS is not None:
        command.extend(["--max-rows", str(MAX_ROWS)])
    return command


def run_single(project_root: Path, sampling_k: int) -> tuple[int, int]:
    command = build_command(project_root, sampling_k)
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = PER_PROCESS_NUM_THREADS
    env["OPENBLAS_NUM_THREADS"] = PER_PROCESS_NUM_THREADS
    env["MKL_NUM_THREADS"] = PER_PROCESS_NUM_THREADS
    env["NUMEXPR_NUM_THREADS"] = PER_PROCESS_NUM_THREADS
    env["VECLIB_MAXIMUM_THREADS"] = PER_PROCESS_NUM_THREADS
    print(f"[start] k={sampling_k}")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=project_root, env=env, check=False)
    return sampling_k, completed.returncode


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    failures: list[tuple[int, int]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(run_single, project_root, sampling_k): sampling_k
            for sampling_k in K_VALUES
        }
        for future in as_completed(future_map):
            sampling_k = future_map[future]
            try:
                k_value, return_code = future.result()
            except Exception:
                print(f"[error] k={sampling_k} raised an unexpected exception")
                failures.append((sampling_k, -1))
                continue

            if return_code == 0:
                print(f"[done] k={k_value}")
            else:
                print(f"[failed] k={k_value} exit_code={return_code}")
                failures.append((k_value, return_code))

    if failures:
        print("[summary] some runs failed:")
        for sampling_k, return_code in failures:
            print(f"  k={sampling_k} exit_code={return_code}")
        sys.exit(1)

    print("[done] completed all parallel experiment 2 runs")


if __name__ == "__main__":
    main()
