"""Score Factwash's detectors against expert annotation on text nobody here wrote.

Every other quality number in this repo was measured on a corpus the author built, and
four separate times that arrangement flattered the fix. This is the correction: 64k
sentences annotated by linguists at HUN-REN-SZTE, years before Factwash existed, with no
stake in whether it looks good.

It scores the SHIPPED predicates (``lexicons.hedges_in`` and friends), not a
reimplementation beside them, which is why those helpers exist.

What is being measured, and what is not
---------------------------------------
This scores *cue detection*: given a sentence, does Factwash see the hedge/condition/
negation the annotators saw? That is the source-side half of every stance check --
the half that decides whether a failure is even VISIBLE. A cue Factwash cannot see is a
laundering it can never flag, so recall here is an upper bound on recall there.

It is NOT a score for the gate as a whole. These corpora have no memory writes in them,
so nothing here says how often the verdict is right. Do not quote it as if it did.

Scope note: sentences whose only cue is ``investigation`` ("we examined whether X") are
excluded from the hedge score. That is research framing, not a claim about certainty in
a stored memory, and Factwash never claimed to catch it -- but the count of them is
printed, and the alternative scoring is printed alongside, so the choice is auditable
rather than convenient.

Run:  python experiments/external/eval_lexicons.py
"""
from __future__ import annotations

import collections
import json
from datetime import datetime
from pathlib import Path

from factwash import lexicons as lex

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "data" / "external" / "normalized"
RESULTS = ROOT / "data" / "results"

# Factwash component -> (gold cue classes it should fire on, the shipped predicate).
# HEDGE is scored against the epistemic and doxastic classes plus BioScope's
# undifferentiated "speculation": all three are "this is not asserted as plain fact".
TASKS = {
    "hedge": (("speculation", "epistemic", "doxastic"), lex.hedges_in),
    "conditional": (("conditional",), lex.conditionals_in),
    "negation": (("negation",), lex.negations_in),
    # PolNeAR only. This is LAUNDERED's first external gold standard: until this corpus
    # went in, the attribution detector was the one component with no outside check at
    # all. PolNeAR's splits are the corpus authors' own, not ours.
    "attribution": (("attribution",), lex.attribs_in),
}
OUT_OF_SCOPE = "investigation"


def load(path: Path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def score(rows, gold_classes, detect, drop_out_of_scope: bool):
    """Sentence-level detection score, plus the cue surfaces we miss and over-fire on."""
    tp = fp = fn = 0
    missed = collections.Counter()
    caught = collections.Counter()
    fp_triggers = collections.Counter()
    skipped = 0

    for row in rows:
        gold = [c for c in row["cues"] if c["cls"] in gold_classes]
        if not gold and drop_out_of_scope and any(c["cls"] == OUT_OF_SCOPE for c in row["cues"]):
            skipped += 1
            continue
        found = detect(row["text"])
        if gold and found:
            tp += 1
        elif gold and not found:
            fn += 1
        elif found and not gold:
            fp += 1
            for t in found:
                fp_triggers[t.lower()] += 1
        # cue-level: did anything we matched actually cover this gold cue?
        low_found = [f.lower() for f in found]
        for c in gold:
            surface = c["text"].lower()
            hit = any(f in surface or surface in f for f in low_found)
            (caught if hit else missed)[surface] += 1

    out = prf(tp, fp, fn)
    out.update(n=len(rows), skipped_out_of_scope=skipped,
               cue_recall=len(list(caught.elements())) /
               max(len(list(caught.elements())) + len(list(missed.elements())), 1),
               top_missed_cues=missed.most_common(15),
               top_false_positive_terms=fp_triggers.most_common(15))
    return out


def main() -> int:
    corpora = sorted(NORMALIZED.glob("*.jsonl"))
    if not corpora:
        print("no normalized corpora; run experiments/external/build_corpora.py first")
        return 1

    report = {"generated": datetime.now().isoformat(timespec="seconds"),
              "note": "cue detection only; says nothing about verdict accuracy",
              "splits": {}}
    # dev exists to mine candidate cues from; test is the number that gets published.
    # Keeping both in one report makes an overfit visible as a dev/test gap instead of
    # letting it hide inside a single flattering figure.
    for split in ("dev", "test"):
        by_corpus = {}
        pooled = {t: collections.Counter() for t in TASKS}
        pooled_missed = {t: collections.Counter() for t in TASKS}
        pooled_fp = {t: collections.Counter() for t in TASKS}

        for path in corpora:
            rows = [r for r in load(path) if r.get("split") == split]
            if not rows:
                continue
            by_corpus[path.stem] = {}
            for task, (classes, detect) in TASKS.items():
                if not any(c["cls"] in classes for r in rows for c in r["cues"]):
                    continue  # this corpus does not annotate that class at all
                res = score(rows, classes, detect, drop_out_of_scope=(task == "hedge"))
                by_corpus[path.stem][task] = res
                for k in ("tp", "fp", "fn"):
                    pooled[task][k] += res[k]
                pooled_missed[task].update(dict(res["top_missed_cues"]))
                pooled_fp[task].update(dict(res["top_false_positive_terms"]))

        pooled_out = {t: prf(c["tp"], c["fp"], c["fn"]) for t, c in pooled.items() if c}
        for t in pooled_out:
            pooled_out[t]["top_missed_cues"] = pooled_missed[t].most_common(30)
            pooled_out[t]["top_false_positive_terms"] = pooled_fp[t].most_common(20)
        report["splits"][split] = {"corpora": by_corpus, "pooled": pooled_out}

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = RESULTS / f"{stamp}_external_lexicon_eval_szeged-bioscope_s0.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- console summary: the TEST split is the headline ---
    test = report["splits"]["test"]
    print(f"{'corpus':22s} {'task':12s} {'n':>7s} {'prec':>6s} {'rec':>6s} {'F1':>6s}   (test split)")
    print("-" * 74)
    for name, tasks in test["corpora"].items():
        for task, r in tasks.items():
            print(f"{name:22s} {task:12s} {r['n']:7d} "
                  f"{r['precision']:6.2f} {r['recall']:6.2f} {r['f1']:6.2f}")
    print("-" * 74)
    for split in ("dev", "test"):
        for task, r in report["splits"][split]["pooled"].items():
            print(f"{'POOLED ' + split:22s} {task:12s} {r['tp'] + r['fn']:7d} "
                  f"{r['precision']:6.2f} {r['recall']:6.2f} {r['f1']:6.2f}")

    print("\nTop gold cues Factwash never sees (mined from DEV only):")
    for task, r in report["splits"]["dev"]["pooled"].items():
        top = r["top_missed_cues"][:12]
        if top:
            # ascii(): these corpora carry typographic dashes and smart quotes, and a
            # Windows console is cp1252. Crashing the whole run on a print is a silly way
            # to lose a measurement, and the JSON report keeps the exact strings.
            print(f"  {task:12s} " + ", ".join(f"{ascii(c)}x{n}" for c, n in top))

    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
