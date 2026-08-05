"""Decompose the field-form advantage into labels, layout and length.

Pools the two ablation arms with the field and paren arms already collected. They share
a seed, corpus, levels and replicate count, and the filler draw does not depend on the
arm, so all four arms saw identical surroundings.

Each adjacent contrast moves one thing:

    field      vs unlabelled   LABELS   (both multi-line, 74 vs 60 chars)
    unlabelled vs paren        LAYOUT   (both unlabelled, 60 vs 62 chars)
    sentences  vs paren        LENGTH   (both unlabelled single-line, 79 vs 62)
    field      vs sentences    labels+layout at MATCHED length (74 vs 79)

Reported per claim, because the claim is the unit that generalises, with an exact sign
test over the sixty per-claim differences.
"""
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

spec = importlib.util.spec_from_file_location("a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

# mean characters over the sixty claims, not the first claim
CHARS = {"field": 115, "sentences": 120, "padded": 125, "unlabelled": 101,
         "promoted": 103, "paren": 103}
CONTRASTS = [
    ("promoted", "paren", "SUBORDINATION", "identical words, out of the parentheses"),
    ("sentences", "promoted", "WORDING", "both asserted; how explicitly stance is said"),
    ("field", "unlabelled", "LABELS", "both multi-line; does naming the parts matter?"),
    ("unlabelled", "paren", "LAYOUT", "both unlabelled, ~same length; own lines?"),
    ("padded", "paren", "LENGTH", "padding carries no stance; is it token count?"),
    ("field", "sentences", "schema vs asserted prose", "the equivalence question"),
]


def load_rows():
    rows = []
    # the ablation arms
    for p in sorted(RAW.glob("*_ablation_claude-*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["run"] = p.stem
                rows.append(r)
    # the field/paren arms already collected, same seed and design
    for p in sorted(RAW.glob("*twocellpress_claude-haiku-4-5_call_*_s700.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["run"] = p.stem
                rows.append(r)
    return [r for r in rows if r["pressure"] in ("brutal", "severe")]


def sign_p(pos, neg):
    n = pos + neg
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) / 2 ** n)


def main() -> int:
    rows = load_rows()
    by_arm = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if A.outcome(r) != "unparsed":
            by_arm[r["arm"]][r["pair"]].append(A.outcome(r) == "kept_qualified")

    arms = [a for a in ("sentences", "field", "unlabelled", "promoted", "padded",
                        "paren") if a in by_arm]
    print(f"{len(rows)} trials, arms present: {arms}")
    print()
    print(f"{'arm':<12} {'chars':>5} {'claims':>7} {'stance retained':>17}")
    print("-" * 46)
    rates = {}
    for a in arms:
        allv = [v for vs in by_arm[a].values() for v in vs]
        rates[a] = sum(allv) / len(allv)
        print(f"{a:<12} {CHARS.get(a, 0):>5} {len(by_arm[a]):>7} "
              f"{rates[a]:>16.3f}")

    print()
    print(f"{'contrast':<24} {'isolates':<14} {'diff':>7}  {'sign test':>18}")
    print("-" * 72)
    out = {"rates": {k: round(v, 4) for k, v in rates.items()}, "contrasts": {}}
    for hi, lo, isolates, _note in CONTRASTS:
        if hi not in by_arm or lo not in by_arm:
            continue
        deltas = {}
        for c in by_arm[hi]:
            if c in by_arm[lo]:
                deltas[c] = (sum(by_arm[hi][c]) / len(by_arm[hi][c])
                             - sum(by_arm[lo][c]) / len(by_arm[lo][c]))
        pos = sum(1 for d in deltas.values() if d > 0)
        neg = sum(1 for d in deltas.values() if d < 0)
        p = sign_p(pos, neg)
        mean = sum(deltas.values()) / len(deltas)
        out["contrasts"][f"{hi}_vs_{lo}"] = {
            "isolates": isolates, "mean_per_claim_delta": round(mean, 4),
            "positive": pos, "negative": neg, "tied": len(deltas) - pos - neg,
            "sign_p": round(p, 5), "claims": len(deltas)}
        star = " *" if p < 0.05 else "  "
        print(f"{hi + ' vs ' + lo:<24} {isolates:<14} {mean:+7.3f}  "
              f"{pos:>3}+/{neg:<3}- p={p:.4f}{star}")

    print()
    print("reading: a contrast that is significant is a thing that matters; one that is")
    print("not is a thing the effect does not depend on.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    dest = RESULTS / "ablation_summary.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
