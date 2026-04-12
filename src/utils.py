from __future__ import annotations

"""
Shared utility functions used across experiment runners.
"""


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
