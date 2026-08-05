"""Regenerate paper 2's figures.

Every number is read from the summary JSONs written by the analysis scripts. Nothing is
typed by hand, so a figure cannot drift from the run that produced it. A missing summary
is a hard failure rather than a plausible-looking placeholder.

Two figures:

  fig_ablation   the five forms and the four contrasts. This is the result: length does
                 nothing, subordinating the stance is what kills it, labels add a real
                 but secondary increment.
  fig_perclaim   one bar per claim, because the claim is the unit that generalises, plus
                 the ten-claim measurement that said the opposite.

Style matches paper 1: validated palette slots, recessive chrome, bars from zero.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
RESULTS = OUT.parents[1] / "data" / "results"
SUMMARY = RESULTS / "twocell_pooled_summary.json"
ABLATION = RESULTS / "ablation_summary.json"

BLUE = "#2a78d6"      # stance asserted / labelled
ORANGE = "#eb6834"    # stance subordinated
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"

NICE = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-4-5": "Sonnet 4.5"}

ARM_LABEL = {
    "sentences": ("explicit sentences", "X. This came from Y. It is Z."),
    "field":     ("labelled fields", "X / SOURCE: Y / CERTAINTY: Z"),
    "unlabelled": ("own lines, no labels", "X / from Y / Z"),
    "promoted":  ("same words, unbracketed", "X. Per Y; Z."),
    "padded":    ("bracketed + padding", "X (per Y; Z). Filed with the rest."),
    "paren":     ("bracketed", "X (per Y; Z)"),
}
ARM_ORDER = ["sentences", "field", "promoted", "unlabelled", "padded", "paren"]
ASSERTED = {"sentences", "field", "unlabelled", "promoted"}

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


def _spines(ax, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def load(path):
    if not path.is_file():
        sys.exit(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fig_ablation(ab):
    rates, cons = ab["rates"], ab["contrasts"]
    arms = [a for a in ARM_ORDER if a in rates]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 3.1),
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    # --- left: retention by form -------------------------------------------
    y = list(range(len(arms)))[::-1]
    ax1.barh(y, [rates[a] for a in arms], height=0.62,
             color=[BLUE if a in ASSERTED else ORANGE for a in arms], zorder=3)
    for yy, a in zip(y, arms):
        ax1.text(rates[a] + 0.008, yy, f"{rates[a]:.3f}", va="center",
                 fontsize=7.5, color=INK)
    ax1.set_yticks(y)
    ax1.set_yticklabels([ARM_LABEL[a][0] for a in arms], fontsize=7.5)
    ax1.set_xlim(0, 0.44)
    ax1.set_xlabel("stance retained after compression", labelpad=3)
    ax1.set_title("what the note looked like", fontsize=8.5, color=INK, pad=4)
    _spines(ax1)

    # --- right: the contrasts ----------------------------------------------
    show = [("padded_vs_paren", "length alone"),
            ("unlabelled_vs_paren", "own lines"),
            ("promoted_vs_paren", "unbracketing"),
            ("field_vs_unlabelled", "labels"),
            ("sentences_vs_promoted", "wording it explicitly")]
    show = [(k, lab) for k, lab in show if k in cons]
    y2 = list(range(len(show)))[::-1]
    for yy, (k, lab) in zip(y2, show):
        c = cons[k]
        sig = c["sign_p"] < 0.05
        ax2.barh([yy], [c["mean_per_claim_delta"]], height=0.6,
                 color=BLUE if sig else BASE, zorder=3)
        ax2.text(c["mean_per_claim_delta"] + 0.006, yy,
                 f"{c['mean_per_claim_delta']:+.3f}"
                 + ("" if sig else "  n.s."),
                 va="center", fontsize=7.5, color=INK if sig else MUTED)
    ax2.axvline(0, color=MUTED, linewidth=0.8, zorder=4)
    ax2.set_yticks(y2)
    ax2.set_yticklabels([lab for _, lab in show], fontsize=7.5)
    ax2.set_xlim(-0.02, 0.28)
    ax2.set_xlabel("effect of changing one thing", labelpad=3)
    ax2.set_title("what actually matters", fontsize=8.5, color=INK, pad=4)
    _spines(ax2)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_ablation.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_ablation.pdf / .png")


def fig_perclaim(rep):
    cc = rep["claim_clustered"]
    models = [m for m in ("claude-haiku-4-5", "claude-sonnet-4-5")
              if f"c60/{m}" in cc]

    fig, axes = plt.subplots(1, len(models) + 1, figsize=(7.0, 2.7),
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
            ax.set_ylabel("asserted $-$ subordinated")
        _spines(ax)

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
    ax.set_xlabel("claim-clustered", labelpad=3)
    ax.set_title("corpus size decides", fontsize=8.5, color=INK, pad=4)
    _spines(ax)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_perclaim.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote fig_perclaim.pdf / .png")


def main():
    ab = load(ABLATION)
    rep = load(SUMMARY)
    print(f"ablation arms: {sorted(ab['rates'])}")
    fig_ablation(ab)
    fig_perclaim(rep)


if __name__ == "__main__":
    main()
