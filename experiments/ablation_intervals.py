"""Claim-clustered intervals for every ablation contrast, and an equivalence test.

Two things the sign test cannot do, both raised in review.

1. A sign test gives a p-value and no effect size, so "labels are not the mechanism"
   was being asserted while the same experiment measured labels at $+9.7$ points with
   $p=0.0003$. An interval makes the relative sizes visible instead of letting a
   significance verdict stand in for them.

2. field vs sentences returned $p=1.0$, which the paper turned into "does as well as".
   Failure to reject is not evidence of equivalence. The honest version needs either an
   interval narrow enough to exclude a difference worth caring about, or an explicit
   statement that the study cannot tell. This runs the two one-sided tests (TOST)
   against a stated margin so the answer is one of those two rather than a rhetorical
   slide.

The equivalence margin is declared here, in code, before looking at the answer: five
percentage points. It is chosen as roughly a third of the headline effect, i.e. the
smallest difference between two write formats that would change which one you would
tell someone to use.
"""
import importlib.util
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"


EQUIV_MARGIN = 0.05  # declared before the numbers are read


def build(model="claude-haiku-4-5"):
    spec2 = importlib.util.spec_from_file_location(
        "a", ROOT / "experiments" / "two_cell_analyse.py")
    A = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(A)

    rows = []
    for p in sorted((ROOT / "data" / "raw").glob(f"*_ablation_{model}_*.jsonl")):
        rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    for p in sorted((ROOT / "data" / "raw").glob(
            f"*twocellpress_{model}_call_*_s700.jsonl")):
        rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    rows = [r for r in rows if r["pressure"] in ("brutal", "severe")]

    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if A.outcome(r) != "unparsed":
            by[r["arm"]][r["pair"]].append(A.outcome(r) == "kept_qualified")
    return by


def contrast_ci(by, hi, lo, n_boot=8000, seed=99):
    claims = [c for c in by[hi] if c in by[lo]]
    if len(claims) < 5:
        return None

    def mean_of(sample):
        tot = 0.0
        for c in sample:
            tot += (sum(by[hi][c]) / len(by[hi][c])
                    - sum(by[lo][c]) / len(by[lo][c]))
        return tot / len(sample)

    point = mean_of(claims)
    rng = random.Random(seed)
    draws = sorted(mean_of([claims[rng.randrange(len(claims))]
                            for _ in claims]) for _ in range(n_boot))
    lo95 = draws[int(0.025 * n_boot)]
    hi95 = draws[int(0.975 * n_boot) - 1]
    # TOST: equivalence at +-margin needs the 90% interval inside the margin
    lo90 = draws[int(0.05 * n_boot)]
    hi90 = draws[int(0.95 * n_boot) - 1]
    equivalent = (lo90 > -EQUIV_MARGIN) and (hi90 < EQUIV_MARGIN)
    return {"claims": len(claims), "point": round(point, 4),
            "ci95": [round(lo95, 4), round(hi95, 4)],
            "ci90": [round(lo90, 4), round(hi90, 4)],
            "equivalence_margin": EQUIV_MARGIN,
            "equivalent_within_margin": bool(equivalent)}


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5"
    by = build(model)
    print(f"model: {model}")
    pairs = [("field", "unlabelled", "labels"),
             ("unlabelled", "paren", "own lines alone"),
             ("padded", "paren", "length alone"),
             ("sentences", "padded", "asserting the stance"),
             ("field", "sentences", "labelled schema vs plain asserted prose"),
             ("field", "paren", "the headline two-cell contrast"),
             ("promoted", "paren", "SUBORDINATION ONLY (identical words)"),
             ("sentences", "promoted", "richer wording, both asserted")]
    out = {"model": model, "equivalence_margin": EQUIV_MARGIN, "contrasts": {}}
    print(f"{'contrast':<34} {'point':>7}  {'95% CI (claim-clustered)':<24} "
          f"{'90% CI':<22}")
    print("-" * 96)
    for hi, lo, label in pairs:
        if hi not in by or lo not in by:
            continue
        r = contrast_ci(by, hi, lo)
        if not r:
            continue
        out["contrasts"][f"{hi}_vs_{lo}"] = {**r, "label": label}
        print(f"{label:<34} {r['point']:+7.3f}  "
              f"[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]{'':<8} "
              f"[{r['ci90'][0]:+.3f}, {r['ci90'][1]:+.3f}]")

    key = "field_vs_sentences"
    if key in out["contrasts"]:
        r = out["contrasts"][key]
        print()
        print(f"EQUIVALENCE TEST, margin +-{EQUIV_MARGIN:.2f} declared before reading "
              f"the data")
        print(f"  field vs sentences: 90% CI [{r['ci90'][0]:+.3f}, {r['ci90'][1]:+.3f}]")
        if r["equivalent_within_margin"]:
            print("  -> EQUIVALENT within the margin: the paper may say the two forms "
                  "perform comparably")
        else:
            print("  -> NOT EQUIVALENT: the interval is wider than the margin, so the "
                  "study cannot")
            print("     distinguish 'the same' from 'differs by up to "
                  f"{max(abs(r['ci90'][0]), abs(r['ci90'][1])) * 100:.1f} points'. The "
                  "paper must say")
            print("     it did not detect a difference, NOT that the forms do as well "
                  "as each other.")

    tag = "" if model == "claude-haiku-4-5" else f"_{model.replace('claude-', '')}"
    dest = RESULTS / f"ablation_intervals{tag}.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
