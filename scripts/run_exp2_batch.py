from __future__ import annotations

"""
Batch runner for Experiment 2.

Edit K_VALUES / MONTHS below, then run:
    python scripts/run_exp2_batch.py
"""

import subprocess
import sys
from pathlib import Path


# 要批量测试的 transaction-time sampling 步长
K_VALUES = [1, 10, 20, 50, 100, 200, 500, 1000]
# K_VALUES = [1, 10]  # 调试时用较少的 K 值，正式全量运行时改回上面这一行

# 要处理的月度文件
MONTHS = ["2026-01", "2026-02", "2026-03"]

# 要处理的资产
ASSETS = ["BTCUSDT", "ETHUSDT"]

# 调试时可以限制每个文件读取的行数；正式全量运行时改成 None
# MAX_ROWS: int | None = None
MAX_ROWS = 100000


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


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent

    for sampling_k in K_VALUES:
        command = build_command(project_root, sampling_k)
        print(f"[run] k={sampling_k}")
        print(" ".join(command))
        subprocess.run(command, cwd=project_root, check=True)

    print("[done] completed all experiment 2 runs")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"[error] batch run failed with exit code {error.returncode}")
        sys.exit(error.returncode)
