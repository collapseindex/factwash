"""The ablation contrasts, scored a second time by an instrument with no model in it.

Section 6 gives the two-cell result a no-model readout and a hand-labelled slice. The
ablation never got either, so every number in the decomposition (labels, wording, layout,
length) rested on one Claude-family judge reading Claude-family output. That is the gap a
reviewer can drive a truck through, and it is the one place the paper's own warning about
single-instrument mechanism claims applies to the paper.

This reruns the identical contrasts from ablation_analyse.py with the deterministic gate
substituted for the blind reader, and prints the two side by side.

Read it the way mechanical_readout.py asks to be read. The gate is NOT ground truth and
NOT a human. It has a documented recall ceiling on open-class stance, so it undercounts
retention everywhere, and it is tilted AGAINST any arm that carries stance as a label,
because ``CERTAINTY: hedged`` contains no word its lexicon knows. Absolute rates will not
match and are not supposed to. The question is whether the DIRECTION and the RANK ORDER of
the contrasts survive an instrument that fails differently.

    python experiments/ablation_mechanical.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = ROOT / "data" / "results"

MODELS = ("claude-haiku-4-5", "claude-sonnet-4-5")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "experiments" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AB = _load("ablation_analyse")
MECH = _load("mechanical_readout")
A = AB.A  # two_cell_analyse, already loaded by ablation_analyse


def main() -> int:
    try:
        import factwash  # noqa: F401
    except Exception:
        print("factwash not importable; run `pip install -e .` first")
        return 1

    out = {}
    flips = []

    for model in MODELS:
        rows = AB.load_rows(model)
        if not rows:
            print(f"no rows for {model}, skipping")
            continue

        judge = defaultdict(lambda: defaultdict(list))
        gate = defaultdict(lambda: defaultdict(list))
        for r in rows:
            if A.outcome(r) == "unparsed":
                continue
            judge[r["arm"]][r["pair"]].append(A.outcome(r) == "kept_qualified")
            gate[r["arm"]][r["pair"]].append(MECH.gate_retains(r["note"], r["stored"]))

        print(f"\n=== {model}, {len(rows)} trials ===")
        print(f"{'contrast':<26} {'isolates':<15} "
              f"{'judge diff':>11} {'gate diff':>10}  {'agree?':>8}")
        print("-" * 76)

        out[model] = {}
        for hi, lo, isolates, _note in AB.CONTRASTS:
            if hi not in judge or lo not in judge:
                continue

            def diff(src):
                d = []
                for c in src[hi]:
                    if c in src[lo]:
                        d.append(sum(src[hi][c]) / len(src[hi][c])
                                 - sum(src[lo][c]) / len(src[lo][c]))
                pos = sum(1 for x in d if x > 0)
                neg = sum(1 for x in d if x < 0)
                return (100 * sum(d) / len(d), pos, neg, AB.sign_p(pos, neg))

            jd, jp, jn, jsig = diff(judge)
            gd, gp, gn, gsig = diff(gate)

            # "Agrees" means the two instruments point the same way on a difference big
            # enough to be worth a direction. Under a tenth of a point is noise in both.
            same = (jd > 0.1 and gd > 0.1) or (jd < -0.1 and gd < -0.1) \
                or (abs(jd) <= 0.1 and abs(gd) <= 0.1)
            mark = "yes" if same else "NO"
            if not same:
                flips.append((model, f"{hi}_vs_{lo}", isolates, jd, gd))

            print(f"{hi + ' vs ' + lo:<26} {isolates:<15} "
                  f"{jd:>+10.1f} {gd:>+9.1f}  {mark:>8}")

            out[model][f"{hi}_vs_{lo}"] = {
                "isolates": isolates,
                "judge": {"diff_points": round(jd, 2), "pos": jp, "neg": jn,
                          "sign_p": round(jsig, 5)},
                "gate": {"diff_points": round(gd, 2), "pos": gp, "neg": gn,
                         "sign_p": round(gsig, 5)},
                "direction_agrees": bool(same),
            }

    print()
    print("=" * 76)
    if flips:
        print(f"{len(flips)} contrast(s) where the instruments DISAGREE on direction:")
        for m, c, iso, jd, gd in flips:
            print(f"  {m:<22} {c:<26} {iso:<15} judge {jd:+.1f}  gate {gd:+.1f}")
        print()
        print("A contrast the no-model instrument does not reproduce is, by this paper's")
        print("own ledger vocabulary, not SHOWN on one instrument alone.")
    else:
        print("Every contrast keeps its direction under an instrument with no model in it.")
    print()
    print("Caveat that does not go away: the gate undercounts stance everywhere and is")
    print("tilted against label-carrying arms, so gate magnitudes are floors, not")
    print("estimates. Direction and rank are the readable part.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    dest = RESULTS / "ablation_mechanical.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
