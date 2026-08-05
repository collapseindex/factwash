"""Regenerate paper 2's figures.

Every number is read from ``data/results/twocell_pooled_summary.json``, written by
``experiments/two_cell_analyse.py`` from the raw JSONL. Nothing is typed by hand, so a
figure cannot drift from the run that produced it. A missing summary is a hard failure
rather than a plausible-looking placeholder.

The figure is the per-claim view, because the per-claim view IS the result. An earlier
version of this paper plotted pooled rates by pressure across four models and concluded
both that the effect vanished under clustering and that it split by model family. Both
were artefacts of a ten-claim corpus. Plotting one bar per claim makes the thing that
matters visible directly: how many claims move, how far, and in which direction.

Style matches paper 1: validated palette slots 1-2, recessive chrome, bars from zero.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
SUMMARY = OUT.parents[1] / "data" / "results" / "twocell_pooled_summary.json"

BLUE = "#2a78d6"      # slot 1: the labelled FIELD wins this claim
ORANGE = "#eb6834"    # slot 2: the PROSE parenthetical wins this claim
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"

NICE = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-4-5": "Sonnet 4.5"}

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


def _spines(ax, keep_left=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if not keep_left:
        ax.spines["left"].set_visible(False)


def load():
    if not SUMMARY.is_file():
        sys.exit(f"missing {SUMMARY}\nrun: python experiments/two_cell_analyse.py")
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def fig_perclaim(rep):
    """One bar per claim, both models, plus the ten-claim corpus for contrast."""
    cc = rep["claim_clustered"]
    models = [m for m in ("claude-haiku-4-5", "claude-sonnet-4-5")
              if f"c60/{m}" in cc]

    fig, axes = plt.subplots(1, len(models) + 1, figsize=(7.0, 2.9),
                             gridspec_kw={"width_ratios": [3] * len(models) + [1.5]})

    for col, model in enumerate(models):
        blk = cc[f"c60/{model}"]
        st = blk["sign_test"]
        deltas = sorted(st["deltas"].values())
        ax = axes[col]
        ax.bar(range(len(deltas)), deltas, width=0.85,
               color=[BLUE if d > 0 else (ORANGE if d < 0 else BASE) for d in deltas],
               zorder=3)
        ax.axhline(0, color=MUTED, linewidth=0.8, zorder=4)
        ax.axhline(blk["point"], color=INK, linewidth=1.0, linestyle=(0, (4, 3)),
                   zorder=5)
        ax.annotate(f"mean {blk['point']:+.3f}", xy=(0, blk["point"]),
                    xytext=(1.5, blk["point"] + 0.06), fontsize=7, color=INK)
        ax.set_ylim(-0.62, 0.78)
        ax.set_xlim(-1, len(deltas))
        ax.set_xticks([])
        ax.set_title(f"{NICE.get(model, model)}   "
                     f"{st['positive']}$+$ / {st['negative']}$-$ / {st['tied']} tied",
                     fontsize=8.5, color=INK, pad=4)
        ax.set_xlabel("60 claims, sorted by effect", labelpad=3)
        if col == 0:
            ax.set_ylabel("field $-$ prose\n(stance retained)")
        _spines(ax)

    # --- right panel: what ten claims said, on the same models and levels -----
    ax = axes[-1]
    labels, points, los, his = [], [], [], []
    for corpus, tag in (("c60", "60"), ("c10", "10")):
        for model in models:
            k = f"{corpus}/{model}"
            if k not in cc:
                continue
            labels.append(f"{NICE.get(model, model).split()[0]}\n{tag} claims")
            points.append(cc[k]["point"])
            los.append(cc[k]["ci95_claim_clustered"][0])
            his.append(cc[k]["ci95_claim_clustered"][1])
    y = list(range(len(labels)))[::-1]
    ax.errorbar(points, y,
                xerr=[[p - l for p, l in zip(points, los)],
                      [h - p for p, h in zip(points, his)]],
                fmt="o", markersize=4, color=INK, ecolor=MUTED,
                elinewidth=1.2, capsize=2.5, zorder=4)
    ax.axvline(0, color=ORANGE, linewidth=1.0, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlim(-0.16, 0.30)
    ax.set_xlabel("effect, claim-clustered", labelpad=3)
    ax.set_title("corpus size decides", fontsize=8.5, color=INK, pad=4)
    _spines(ax)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_perclaim.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_perclaim.pdf / .png")


def main():
    rep = load()
    print(f"source: {SUMMARY.name}  analysed={rep['n_trials_analysed']} trials")
    fig_perclaim(rep)


if __name__ == "__main__":
    main()
