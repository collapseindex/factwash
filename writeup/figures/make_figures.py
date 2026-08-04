"""Regenerate the preprint's figures. Deterministic; every number here is stated in
main.tex and README.md, so a mismatch is a bug in one of the three places.

Style: validated default dataviz palette (slots 1-2, light mode), recessive chrome,
direct labels, no dual axes, bars from zero.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent

BLUE = "#2a78d6"      # categorical slot 1: closed class / lexicon
ORANGE = "#eb6834"    # categorical slot 2: open class / witness
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "font.size": 8,
    "axes.edgecolor": BASE,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "figure.dpi": 200,
})


def _spines(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


# --- Figure 1: mining closes a closed class and stalls on open ones ----------------
def fig_mining():
    fig, ax = plt.subplots(figsize=(3.2, 2.3))
    stages = [0, 1]
    series = [  # name, before, after, color, label y-nudge
        ("Negation", 0.88, 0.94, BLUE, 0.0),
        ("Conditionals", 0.67, 0.67, BLUE, 0.012),
        ("Hedges", 0.47, 0.66, ORANGE, -0.030),
        ("Attribution", 0.42, 0.49, ORANGE, 0.0),
    ]
    for name, a, b, color, dy in series:
        ax.plot(stages, [a, b], color=color, linewidth=2, marker="o", markersize=4,
                clip_on=False)
        ax.annotate(f"{name}  {b:.2f}", xy=(1, b), xytext=(1.05, b + dy),
                    color=INK, fontsize=7.5, va="center")
    ax.set_xlim(-0.08, 1.75)
    ax.set_ylim(0, 1.0)
    ax.set_xticks(stages)
    ax.set_xticklabels(["before mining", "after 3 rounds"])
    ax.set_ylabel("recall, held-out external gold")
    ax.grid(axis="x", visible=False)
    _spines(ax)
    ax.plot([], [], color=BLUE, linewidth=2, label="closed class")
    ax.plot([], [], color=ORANGE, linewidth=2, label="open class")
    ax.legend(frameon=False, fontsize=7, loc="lower left", handlelength=1.4)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "fig_mining.pdf")
    plt.close(fig)


# --- Figure 2: witness vs lexicon on the same expert gold --------------------------
def fig_witness():
    fig, ax = plt.subplots(figsize=(3.2, 2.1))
    tasks = ["Hedges", "Attribution"]
    lex = [0.62, 0.45]
    wit = [0.79, 0.60]
    x = [0, 1]
    w = 0.34
    gap = 0.012  # 2px-equivalent surface gap between adjacent fills
    for xi, v in zip(x, lex):
        ax.bar(xi - w / 2 - gap, v, width=w, color=BLUE, zorder=3)
        ax.annotate(f"{v:.2f}", xy=(xi - w / 2 - gap, v), xytext=(0, 2),
                    textcoords="offset points", ha="center", color=INK, fontsize=7.5)
    for xi, v in zip(x, wit):
        ax.bar(xi + w / 2 + gap, v, width=w, color=ORANGE, zorder=3)
        ax.annotate(f"{v:.2f}", xy=(xi + w / 2 + gap, v), xytext=(0, 2),
                    textcoords="offset points", ha="center", color=INK, fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(tasks, color=INK)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("recall at equal precision")
    ax.grid(axis="x", visible=False)
    _spines(ax)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="lexicon"),
                       Patch(color=ORANGE, label="witness")],
              frameon=False, fontsize=7, loc="upper right", handlelength=1.0)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "fig_witness.pdf")
    plt.close(fig)


# --- Figure 3: the lexicon memorises the corpus it can see ------------------------
def fig_memorise():
    fig, ax = plt.subplots(figsize=(3.2, 1.9))
    labels = ["corpus the 40 terms\nwere mined from",
              "corpus written\nafterwards"]
    vals = [0.92, 0.14]
    bars = ax.barh([1, 0], vals, height=0.55, color=BLUE, zorder=3)
    for y, v in zip([1, 0], vals):
        ax.annotate(f"{v:.0%}", xy=(v, y), xytext=(3, 0), textcoords="offset points",
                    va="center", color=INK, fontsize=8)
    ax.annotate("external mining later:\n14% to 29%", xy=(0.14, 0), xytext=(0.42, 0.42),
                color=MUTED, fontsize=7, va="center")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(labels, color=INK, fontsize=7.5)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("recall against adversarial phrasings")
    ax.grid(axis="y", visible=False)
    _spines(ax)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "fig_memorise.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_mining()
    fig_witness()
    fig_memorise()
    print("wrote", *(p.name for p in sorted(OUT.glob("fig_*.pdf"))))
