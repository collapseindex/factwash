"""Draw a blinded sample for human annotation, then score agreement against the judge.

Why this exists. Every outcome in the paper is a model's judgement of another model's
output. A second model judge agreed at 98% and a deterministic gate agrees on direction,
but those are three instruments and no ground truth. A human reading the same text is a
different kind of evidence.

What this is NOT, and the paper must say so:

  - It is ONE rater, so there is no inter-annotator agreement to report.
  - The rater is the paper's author, so this is annotation blind to CONDITION, not blind
    to HYPOTHESIS. An author who knows what the paper argues is not a neutral instrument.
  - It therefore measures whether the model judge tracks a careful human reading of the
    same text. It does not establish that either is correct.

The blinding this DOES enforce:

  - The annotator sees exactly what the judge saw: the stored memory and the claim to
    look up. No arm, no model, no budget, no claim id.
  - Items are shuffled under a recorded seed, so field and prose are interleaved.
  - The judge's verdicts are written to a SEPARATE key file that the annotation file does
    not contain and the annotator does not open. Agreement cannot be computed until the
    labels are saved, and the scorer refuses to run on an unfinished sheet.

Usage:
    python experiments/human_annotate.py sample --n 50     # writes the blank sheet
    ... fill in the ANSWER: lines by hand ...
    python experiments/human_annotate.py score             # agreement + kappa
"""
import argparse
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"
SHEET = ROOT / "data" / "annotation" / "human_sheet.md"
KEY = ROOT / "data" / "annotation" / "human_key.json"
LABELS = ("qualified", "established_fact", "absent")

spec = importlib.util.spec_from_file_location(
    "a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

INSTRUCTIONS = """# Blind annotation sheet

You are looking at stored long-term memories written by an AI memory system. For each
one you are given the memory and a claim to look up in it.

**Question, for each item:** as stored, is that claim presented as established fact, or
does the memory preserve some indication that it is uncertain, second-hand, or
unverified? If the claim is not in the memory at all, answer `absent`.

Write one of these three words after `ANSWER:` on each item:

  qualified          the memory still signals uncertainty, hearsay or lack of verification
  established_fact   the claim is stored as plain fact, with no such signal
  absent             the claim is not in the memory at all

Rules that make this worth doing:

1. Judge ONLY the text in front of you. Do not reason about which experimental arm it
   came from; the sheet is shuffled and does not tell you.
2. Do not open `human_key.json` until you have filled in every answer and saved.
3. If you are torn, pick the one a downstream agent acting on this memory would be
   entitled to assume. Do not leave blanks; the scorer refuses an unfinished sheet.

---
"""


def sample(n: int, seed: int) -> int:
    rows, _ = A.balance(A.load())
    rows = [r for r in rows if r.get("stored") and r["corpus"] in ("c60", "v3")]
    if not rows:
        print("no sixty-claim rows found")
        return 1

    # stratify so the sample covers the space rather than whatever sorts first
    strata = defaultdict(list)
    for r in rows:
        strata[(r["model"], r["arm"], r["pressure"])].append(r)
    rng = random.Random(seed)
    picked, keys = [], sorted(strata)
    while len(picked) < n and keys:
        for k in list(keys):
            if not strata[k]:
                keys.remove(k)
                continue
            picked.append(strata[k].pop(rng.randrange(len(strata[k]))))
            if len(picked) >= n:
                break
    rng.shuffle(picked)

    sys.path.insert(0, str(ROOT / "experiments"))
    from claims_corpus import CORPORA
    from claims_corpus_v3 import V3
    claim_text = {c[0]: c[1] for c in CORPORA["all"] + V3}

    SHEET.parent.mkdir(parents=True, exist_ok=True)
    lines = [INSTRUCTIONS]
    key = []
    for i, r in enumerate(picked, 1):
        lines.append(f"\n## {i}\n")
        lines.append("**Stored memory**\n")
        lines.append("```\n" + r["stored"].strip() + "\n```\n")
        lines.append(f"**Claim to look up:** {claim_text.get(r['pair'], r['pair'])}\n")
        lines.append("\nANSWER: \n")
        key.append({"item": i, "uid": f"{r['run']}|{r['key']}",
                    "judge": r.get("blind_presented_as"),
                    "arm": r["arm"], "model": r["model"], "pressure": r["pressure"],
                    "pair": r["pair"]})
    SHEET.write_text("".join(lines), encoding="utf-8")
    KEY.write_text(json.dumps({"seed": seed, "n": len(picked), "items": key}, indent=2),
                   encoding="utf-8")

    cov = Counter((k["model"].replace("claude-", ""), k["arm"]) for k in key)
    print(f"wrote {SHEET}  ({len(picked)} items, seed {seed})")
    print(f"wrote {KEY}  <- do not open until the sheet is filled in")
    print("\ncoverage:")
    for k in sorted(cov):
        print(f"  {k[0]:<14} {k[1]:<11} {cov[k]}")
    return 0


def kappa(a, b, labels):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0, po


def score() -> int:
    if not SHEET.is_file() or not KEY.is_file():
        print("no sheet; run `sample` first")
        return 1
    text = SHEET.read_text(encoding="utf-8")
    answers = {}
    item = None
    for line in text.splitlines():
        if line.startswith("## "):
            item = int(line[3:].strip())
        elif line.startswith("ANSWER:") and item is not None:
            v = line.split(":", 1)[1].strip().lower()
            if v:
                answers[item] = v

    key = json.loads(KEY.read_text(encoding="utf-8"))
    missing = [k["item"] for k in key["items"] if k["item"] not in answers]
    if missing:
        print(f"UNFINISHED: {len(missing)} of {key['n']} items have no answer "
              f"(first few: {missing[:8]}). Not scoring a partial sheet.")
        return 1
    bad = {i: v for i, v in answers.items() if v not in LABELS}
    if bad:
        print(f"unrecognised labels: {bad}\nuse one of {LABELS}")
        return 1

    human = [answers[k["item"]] for k in key["items"]]
    judge = [k["judge"] for k in key["items"]]
    kap, po = kappa(human, judge, LABELS)

    print(f"n = {len(human)}   (seed {key['seed']})")
    print(f"raw agreement      {po:.3f}")
    print(f"Cohen's kappa      {kap:.3f}")
    print("\nconfusion (rows = human, cols = judge)")
    print(f"{'':<18}" + "".join(f"{l[:12]:>14}" for l in LABELS))
    for hl in LABELS:
        row = [sum(1 for h, j in zip(human, judge) if h == hl and j == jl)
               for jl in LABELS]
        print(f"{hl:<18}" + "".join(f"{v:>14}" for v in row))

    # does disagreement fall differently on the two arms? that is the thing that would
    # actually threaten the result, rather than overall noise
    print("\ndisagreement by arm (a judge that errs evenly cannot manufacture an effect)")
    for arm in ("field", "paren", "sentences", "promoted", "unlabelled", "padded"):
        idx = [i for i, k in enumerate(key["items"]) if k["arm"] == arm]
        if not idx:
            continue
        dis = sum(1 for i in idx if human[i] != judge[i])
        print(f"  {arm:<12} {dis:>3} / {len(idx):<3} disagree")

    out = {"n": len(human), "seed": key["seed"], "raw_agreement": round(po, 4),
           "cohens_kappa": round(kap, 4),
           "human": human, "judge": judge,
           "note": "ONE rater, who is the paper's author. Blind to condition, not to "
                   "hypothesis. No inter-annotator agreement is available."}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "human_agreement.json").write_text(json.dumps(out, indent=2),
                                                  encoding="utf-8")
    print(f"\nwrote {RESULTS / 'human_agreement.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "score"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()
    return sample(args.n, args.seed) if args.mode == "sample" else score()


if __name__ == "__main__":
    sys.exit(main())
