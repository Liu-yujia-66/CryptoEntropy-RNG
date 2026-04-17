from __future__ import annotations

"""
Shared utility functions used across experiment runners.
"""

import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Cross-cutting constants (used by both runners and plot scripts)
# ---------------------------------------------------------------------------

ASSET_ORDER = ["BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT"]

ASSET_COLORS = {
    "BTCUSDT": "#F7931A",
    "ETHUSDT": "#627EEA",
    "BNBUSDT": "#F3BA2F",
    "SOLUSDT": "#9945FF",
    "DOGEUSDT": "#C2A633",
}


def fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds into a human-readable string (e.g. '2h 3min 4.5s')."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}min {s:.1f}s"
    if m > 0:
        return f"{m}min {s:.1f}s"
    return f"{s:.1f}s"


def period_dir_name(months: list[str]) -> str:
    """
    Auto-generate a directory name from a list of 'YYYY-MM' strings.

    Examples:
        ["2025-01","2025-02","2025-03"]   → 3month-2025.01-03
        ["2025-07",..."2025-12"]          → 6month-2025.07-12
        ["2025-01",..."2025-12"]          → 12month-2025
        ["2025-04"]                       → 1month-2025.04
    """
    parsed = sorted((int(m[:4]), int(m[5:])) for m in months)
    first_year, first_month = parsed[0]
    _last_year, last_month = parsed[-1]
    n = len(parsed)

    if n == 12 and first_year == _last_year:
        return f"12month-{first_year}"
    if n == 1:
        return f"1month-{first_year}.{first_month:02d}"
    return f"{n}month-{first_year}.{first_month:02d}-{last_month:02d}"


def run_plot_subprocess(
    project_root: Path,
    plot_script_relpath: str,
    summary_dir: Path,
) -> None:
    """
    Invoke a plot script as a subprocess with --summary-dir <dir>.

    Uses the project's local .venv Python interpreter for environment isolation.
    Errors are reported but do not raise (plotting is downstream of analysis).
    """
    cmd = [
        str(project_root / ".venv" / "bin" / "python"),
        plot_script_relpath,
        "--summary-dir",
        str(summary_dir),
    ]
    print(f"[plot] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, check=False)
    if result.returncode != 0:
        print(f"[warn] plot script exited with code {result.returncode}")
