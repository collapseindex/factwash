"""Run the whole gate against FRANK's human factuality annotations.

The lexicon evaluation next door scores one component. This scores the VERDICT, on the
only external corpus shaped like Factwash's actual input: FRANK pairs a source article
with generated summary sentences and has three annotators label each sentence with a
typed factual error. Source plus derived text plus a human judgement of whether the
derivation broke -- that is the job, written down by someone else.

What a fair reading looks like
------------------------------
Factwash checks SEVEN specific failure modes, all of them about losing the source's basis
or its stance. FRANK's typology is dominated by hallucination -- wrong entity, wrong
predicate, invented content -- which Factwash has never claimed to detect and structurally
cannot: a fabricated name is perfectly well-hedged and perfectly well-attributed.

So the honest question is NOT "does Factwash catch FRANK's errors" (it will not, and a
high number there would mean the checks are firing for the wrong reasons). It is:

    1. Among the categories Factwash DOES target, does it fire more than base rate?
       CircE (circumstance: time, place, manner) is the one that maps onto
       TEMPORAL_SCOPE_DROPPED and CONDITION_DROPPED.
    2. On sentences all three annotators called clean (NoE), how often does it fire
       anyway? That is external false-positive rate, on text nobody here wrote.

Item 2 is the one that can hurt, and it is the reason to run this.

Run:  python experiments/external/eval_frank.py
"""
from __future__ import annotations

import collections
import json
from datetime import datetime
from pathlib import Path

import factwash

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "external" / "human_annotations_sentence.json"
RESULTS = ROOT / "data" / "results"

BLOCKING = ("REWRITE", "REJECT")

# FRANK's categories, with whether Factwash claims anything about them. Writing the claim
# down BEFORE reading the result is what stops this from becoming a search for whichever
# slice happens to look good.
TARGETED = {
    "CircE": "circumstance (time/place/manner) -- TEMPORAL_SCOPE_DROPPED, CONDITION_DROPPED",
}
NOT_TARGETED = {
    "EntE": "wrong entity -- hallucination, Factwash cannot see this",
    "PredE": "wrong predicate -- hallucination",
    "RelE": "wrong relation between entities",
    "CorefE": "coreference error",
    "LinkE": "discourse link error",
    "OutE": "content not in the article at all",
    "GramE": "ungrammatical",
    "OtherE": "outside the typology",
}
NO_ERROR = "NoE"


def majority(annotations: dict, min_votes: int = 2) -> set:
    """Error categories at least `min_votes` of the annotators agreed on."""
    counts = collections.Counter()
    for cats in annotations.values():
        for c in set(cats or []):
            counts[c] += 1
    return {c for c, n in counts.items() if n >= min_votes}


def main() -> int:
    if not SRC.is_file():
        print(f"missing {SRC}; see experiments/external/README.md")
        return 1
    records = json.loads(SRC.read_text(encoding="utf-8"))

    rows = []
    for rec in records:
        article = rec.get("article") or ""
        sents = rec.get("summary_sentences") or []
        annots = rec.get("summary_sentences_annotations") or []
        if not article:
            continue
        for sent, ann in zip(sents, annots):
            if not sent.strip() or not isinstance(ann, dict):
                continue
            report = factwash.check(article, sent)
            rows.append({
                "hash": rec.get("hash"), "model": rec.get("model_name"),
                "split": rec.get("split"), "sentence": sent,
                "gold": sorted(majority(ann)),
                "any_annotator": sorted(majority(ann, min_votes=1)),
                "verdict": report.verdict,
                "blocked": report.verdict in BLOCKING,
                "checks": sorted({f.name for f in report.flags if f.severity != "info"}),
            })

    n = len(rows)
    checkable = [r for r in rows if r["verdict"] != "UNCHECKABLE"]
    clean = [r for r in checkable if r["gold"] == [NO_ERROR] or not r["gold"]]
    base_rate = sum(r["blocked"] for r in checkable) / max(len(checkable), 1)

    per_cat = {}
    for cat in list(TARGETED) + list(NOT_TARGETED):
        sub = [r for r in checkable if cat in r["gold"]]
        if not sub:
            continue
        rate = sum(r["blocked"] for r in sub) / len(sub)
        per_cat[cat] = {"n": len(sub), "flag_rate": rate,
                        "lift_over_base": (rate / base_rate) if base_rate else 0.0,
                        "targeted": cat in TARGETED}

    fp_rate = sum(r["blocked"] for r in clean) / max(len(clean), 1)
    check_counts = collections.Counter(c for r in checkable for c in r["checks"])
    unusable = sum(1 for r in rows if r["verdict"] == "UNCHECKABLE")

    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "corpus": "FRANK (Pagnoni et al. 2021), human_annotations_sentence.json",
        "n_sentences": n, "n_checkable": len(checkable), "n_uncheckable": unusable,
        "base_flag_rate": base_rate,
        "clean_sentences": len(clean), "false_positive_rate_on_clean": fp_rate,
        "per_category": per_cat,
        "checks_fired": dict(check_counts),
        "caveat": ("FRANK is dominated by hallucination categories Factwash does not "
                   "target; the informative numbers are the CircE lift and the "
                   "false-positive rate on NoE sentences."),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = RESULTS / f"{stamp}_external_frank_gate_eval_s0.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"FRANK: {n} summary sentences, {len(checkable)} checkable "
          f"({unusable} UNCHECKABLE: no stored claim matched a source claim)")
    print(f"base flag rate            {base_rate:.3f}")
    print(f"flag rate on CLEAN (NoE)  {fp_rate:.3f}   <- external false positives, "
          f"n={len(clean)}")
    print()
    print(f"{'category':10s} {'n':>6s} {'flag rate':>10s} {'lift':>7s}  targeted?")
    for cat, d in sorted(per_cat.items(), key=lambda kv: -kv[1]["lift_over_base"]):
        print(f"{cat:10s} {d['n']:6d} {d['flag_rate']:10.3f} {d['lift_over_base']:7.2f}"
              f"  {'YES' if d['targeted'] else 'no'}")
    print(f"\nchecks fired: {dict(check_counts)}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
