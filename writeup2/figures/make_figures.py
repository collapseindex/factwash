"""Regenerate paper 2's figures.

Every number is read from ``data/results/twocell_pooled_summary.json``, written by
``experiments/two_cell_analyse.py`` from the raw JSONL. Nothing is typed in by hand, so a
figure cannot drift from the run that produced it. Missing summary is a hard failure
rather than a plausible-looking placeholder.

The figure is faceted by model rather than pooled, because the model is where the result
actually lives: the effect is present on the weakest compressor, absent on the middle one,
and has nothing to act on at the top, where no standing is lost in the first place. A
pooled line would average those three into a number that describes none of them.

Style matches paper 1: validated palette slots 1-2, recessive chrome, direct labels,
bars from zero, no dual axes.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
SUMMARY = OUT.parents[1] / "data" / "results" / "twocell_pooled_summary.json"

BLUE = "#2a78d6"      # slot 1: standing written as a labelled FIELD
ORANGE = "#eb6834"    # slot 2: standing written as PROSE (a parenthetical)
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"

LEVELS = ("none", "low", "high", "extreme")
SHORT = {"none": "none", "low": "low", "high": "high", "extreme": "extr."}
NICE = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-4-5": "Sonnet 4.5",
        "claude-opus-4-5": "Opus 4.5"}
ORDER = ("claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5")

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


def load():
    if not SUMMARY.is_file():
        sys.exit(f"missing {SUMMARY}\nrun: python experiments/two_cell_analyse.py")
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def fig_twocell(rep):
    blocks = rep["blocks"]
    models = [m for m in ORDER if any(k.startswith(f"{m} / ") for k in blocks)]
    x = list(range(len(LEVELS)))

    fig, axes = plt.subplots(2, len(models), figsize=(6.8, 3.9), sharex=True,
                             sharey="row")

    for col, model in enumerate(models):
        keys = [f"{model} / {lv}" for lv in LEVELS]
        n_pairs = sum(blocks[k]["paired"]["pairs"] for k in keys if k in blocks)

        # --- top row: standing recoverable from the stored memory --------------
        ax = axes[0][col]
        # small x-dodge: where the two arms coincide exactly (Opus, every cell at
        # 1.0) an un-dodged series is completely hidden behind the other
        for arm, color, dx in (("field", BLUE, -0.045), ("paren", ORANGE, 0.045)):
            rates = [blocks[k][arm]["rate"] for k in keys]
            lo = [blocks[k][arm]["ci95"][0] for k in keys]
            hi = [blocks[k][arm]["ci95"][1] for k in keys]
            ax.errorbar([v + dx for v in x], rates,
                        yerr=[[r - l for r, l in zip(rates, lo)],
                              [h - r for r, h in zip(rates, hi)]],
                        color=color, linewidth=1.8, marker="o", markersize=3.5,
                        capsize=2, elinewidth=0.8, clip_on=False,
                        label="labelled field" if arm == "field" else "parenthetical")
        ax.set_ylim(0, 1.04)
        ax.set_xlim(-0.3, len(LEVELS) - 0.7)
        ax.set_title(f"{NICE.get(model, model)}  ($n$={n_pairs} pairs)",
                     fontsize=8.5, color=INK, pad=4)
        _spines(ax)
        if col == 0:
            ax.set_ylabel("standing recovered")

        # --- bottom row: claim dropped from memory entirely --------------------
        ax = axes[1][col]
        w = 0.36
        for i, (arm, color) in enumerate((("field", BLUE), ("paren", ORANGE))):
            vals = [blocks[k][arm]["evicted"] / blocks[k][arm]["n"] for k in keys]
            ax.bar([v + (i - 0.5) * w for v in x], vals, width=w, color=color, zorder=3)
        ax.set_ylim(0, 0.32)
        ax.set_xticks(x)
        ax.set_xticklabels([SHORT[lv] for lv in LEVELS], fontsize=7)
        ax.set_xlabel("compression pressure", labelpad=2)
        _spines(ax)
        if col == 0:
            ax.set_ylabel("claim absent")

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, ncol=2,
               loc="lower center", bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_twocell.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_twocell.pdf / .png")


def main():
    rep = load()
    print(f"source: {SUMMARY.name}  analysed={rep['n_trials_analysed']} trials  "
          f"models={rep['models']}")
    fig_twocell(rep)


if __name__ == "__main__":
    main()
