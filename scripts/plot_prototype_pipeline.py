"""
Prototype pipeline diagram for the thesis Password Generator chapter.

Draws the vertical per-password flowchart (combined stream -> 33-byte IKM ->
HKDF-Extract -> PRK -> HKDF-Expand -> OKM -> rejection sampling -> 16-char
password), with salt as a side input and the re-Expand fallback annotated.

Run from the project root:
    python scripts/plot_prototype_pipeline.py

Output: thesis/figures/prototype_pipeline.png
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path("data/interim/.mplconfig").resolve()),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

OUTPUT_PATH = Path("thesis/figures/prototype_pipeline.png")

# Layout
FIG_W, FIG_H = 6.5, 8.5
CX = 0.50
BOX_W = 0.62
BOX_H = 0.07

# Y positions for the main vertical chain (top to bottom)
Y_NODES = {
    "stream":   0.94,
    "ikm":      0.78,
    "prk":      0.61,
    "okm":      0.44,
    "chars":    0.27,
    "password": 0.09,
}

# Salt node sits on the right, between IKM and PRK (feeds HKDF-Extract)
SALT_X = 0.88
SALT_Y = 0.70

# Styling (match other thesis figures: plain, near-black).
EDGE = "0.20"            # near-black for borders and arrows
TEXT = "0.10"
LABEL_TEXT = "0.30"      # slightly lighter for arrow side-labels
FILL = "white"
EMPHASIS_LW = 1.8        # output node uses a slightly thicker border
DEFAULT_LW = 1.0


def draw_box(
    ax,
    x: float,
    y: float,
    text: str,
    width: float = BOX_W,
    height: float = BOX_H,
    fontsize: int = 10,
    linewidth: float = DEFAULT_LW,
    linestyle: str = "-",
) -> None:
    """Draw a plain rectangle centred at (x, y) with the given text."""
    box = Rectangle(
        (x - width / 2, y - height / 2),
        width,
        height,
        linewidth=linewidth,
        edgecolor=EDGE,
        facecolor=FILL,
        linestyle=linestyle,
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=TEXT)


def draw_arrow(
    ax,
    xy_from: tuple[float, float],
    xy_to: tuple[float, float],
    label: str | None = None,
    label_dx: float = 0.018,
    label_dy: float = 0.0,
    label_ha: str = "left",
    curve: float = 0.0,
    linestyle: str = "-",
) -> None:
    """Draw a straight/curved arrow from xy_from to xy_to with optional side label."""
    arrow = FancyArrowPatch(
        xy_from,
        xy_to,
        arrowstyle="-|>",
        mutation_scale=12,
        color=EDGE,
        linewidth=DEFAULT_LW,
        linestyle=linestyle,
        connectionstyle=f"arc3,rad={curve}",
    )
    ax.add_patch(arrow)
    if label is not None:
        mx = (xy_from[0] + xy_to[0]) / 2 + label_dx
        my = (xy_from[1] + xy_to[1]) / 2 + label_dy
        ax.text(
            mx,
            my,
            label,
            fontsize=9,
            ha=label_ha,
            va="center",
            color=LABEL_TEXT,
        )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---- main vertical chain ----
    draw_box(
        ax, CX, Y_NODES["stream"],
        "Experiment 4 combined stream\n(n in {2, 3, 5}, validation month)",
    )
    draw_box(
        ax, CX, Y_NODES["ikm"],
        "33-byte IKM block\n(disjoint per password)",
    )
    draw_box(ax, CX, Y_NODES["prk"], "32-byte PRK")
    draw_box(ax, CX, Y_NODES["okm"], "32 OKM bytes\nper Expand round")
    draw_box(
        ax, CX, Y_NODES["chars"],
        "16 accepted characters\n(from 70-char alphabet)",
    )
    draw_box(
        ax, CX, Y_NODES["password"],
        "16-character password",
        linewidth=EMPHASIS_LW,
    )

    # ---- salt side input (dashed border marks a side input) ----
    draw_box(
        ax, SALT_X, SALT_Y,
        "salt\n(32 bytes)",
        width=0.20, height=0.07, fontsize=9,
        linestyle="--",
    )

    # ---- main vertical arrows ----
    draw_arrow(
        ax,
        (CX, Y_NODES["stream"] - BOX_H / 2),
        (CX, Y_NODES["ikm"] + BOX_H / 2),
        label="slice",
    )
    draw_arrow(
        ax,
        (CX, Y_NODES["ikm"] - BOX_H / 2),
        (CX, Y_NODES["prk"] + BOX_H / 2),
        label="HKDF-Extract",
        label_dx=-0.018,
        label_ha="right",
    )
    draw_arrow(
        ax,
        (CX, Y_NODES["prk"] - BOX_H / 2),
        (CX, Y_NODES["okm"] + BOX_H / 2),
        label="HKDF-Expand(info)",
    )
    draw_arrow(
        ax,
        (CX, Y_NODES["okm"] - BOX_H / 2),
        (CX, Y_NODES["chars"] + BOX_H / 2),
        label="rejection sampling:\naccept byte b < 210,\nmap b mod 70",
        label_dx=-0.018,
        label_ha="right",
    )
    draw_arrow(
        ax,
        (CX, Y_NODES["chars"] - BOX_H / 2),
        (CX, Y_NODES["password"] + BOX_H / 2),
        label="concatenate",
    )

    # ---- salt arrow (dashed, feeds HKDF-Extract) ----
    salt_arrow = FancyArrowPatch(
        (SALT_X - 0.10, SALT_Y - 0.005),
        (CX, (Y_NODES["ikm"] + Y_NODES["prk"]) / 2),
        arrowstyle="-|>",
        mutation_scale=10,
        color=EDGE,
        linewidth=DEFAULT_LW,
        linestyle="--",
        connectionstyle="arc3,rad=-0.2",
    )
    ax.add_patch(salt_arrow)

    # ---- fallback annotation (plain text, no box) ----
    ax.text(
        0.98, (Y_NODES["okm"] + Y_NODES["chars"]) / 2,
        "re-Expand fallback:\nif < 16 accepted chars,\nExpand with info || counter\n(0 / 2400 in demo)",
        fontsize=8.5,
        color=LABEL_TEXT,
        ha="right",
        va="center",
    )

    plt.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
