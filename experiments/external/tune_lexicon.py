"""Score candidate lexicon terms on the DEV split only, and never on test.

The failure mode this exists to prevent is the one that has already happened four times
in this repo: look at what the detector missed, add exactly those strings, and report the
improvement on the same data. That measures the leak, not the lexicon.

So: candidates are mined from dev, scored on dev, chosen by hand from that ranking, and
the consequence is read off test by eval_lexicons.py afterwards. If a term memorised dev
rather than generalising, the dev/test gap in that report is where it shows up.

Each candidate is scored by its MARGINAL effect -- what it adds over the lexicon as it
already stands -- because a term that only fires where "may" already fired buys nothing
and still costs precision.

Run:  python experiments/external/tune_lexicon.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from factwash import lexicons as lex

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "data" / "external" / "normalized"

# Candidates. Every one appears in the dev missed-cue list, but appearing there is not
# sufficient -- each also has to be plausible in a MEMORY WRITE, which is the job Factwash
# actually does. The ones rejected on that ground are recorded here rather than dropped
# silently, because "we tried it and it was bad" is the useful half of the record.
#
# REJECTED, with reasons:
#   "or"      x194  BioScope marks "either X or Y" as speculative. In a stored memory
#                   "or" is a conjunction; adding it would fire on a large share of all
#                   English and destroy precision for an annotation-convention artefact.
#   "can"     x109  Ability/permission, not epistemic doubt. Same objection.
#   "whether" x60   Almost always a complementiser ("checked whether it shipped").
#                   "unclear whether" is already in the lexicon and is the useful part.
#   "would"   x146  (conditional) marks the consequent, not the condition. A memory that
#                   drops "would" has not lost a condition to restore.
#   "will"/"should"/"could" (conditional)  modals, not conditions. "should" is already
#                   documented in lexicons.py as deliberately excluded.
HEDGE_CANDIDATES = [
    "suggest",        # bare stem; the lexicon has suggests/suggested but not this
    "likely",
    "possible",
    "indicate",       # lexicon has "indicates that" only
    "appear",         # lexicon has "appears" only
    "could",          # lexicon has "could be" only
    "considered to",
    "thought that",
    "believed that",
    "seems to",
    "estimate",
    "tend to",
    "assume",
]
NEGATION_CANDIDATES = [
    r"\babsence\b", r"\babsent\b", r"\bfail(?:s|ed|ure|ing)?\b",
    r"\bunable\b", r"\blacking\b", r"\bnegative for\b",
]
CONDITIONAL_CANDIDATES = [r"\buntil\b", r"\bonce\b", r"\bwhenever\b"]

# Attribution, from PolNeAR's dev split. Same stem logic as the hedge list: the lexicon
# has "said"/"says" and no "say", "reported" and no "reports".
#
# REJECTED before scoring, because they are reporting verbs in a newsroom and ordinary
# verbs in a conversation, which is where Factwash runs:
#   "called" x23  "called the meeting", "called off" -- polysemous
#   "found"  x22  "found the file"
#   "shows"  x15  "the dashboard shows"
#   ":"      x21  and the typographic dash x24: PolNeAR annotates punctuation that
#                 introduces a quotation. A memory write has no such convention, and
#                 flagging every colon would be absurd.
ATTRIB_CANDIDATES = [
    "say",          # bare stem: covers say/says/saying, of which only "says" was known
    "added", "adds",
    "wrote", "writes",
    "argued", "arguing",
    "agreed",
    "insisted", "denied that", "confirmed that", "explained",
    "announced", "warned", "acknowledged",
]

TASKS = {
    "hedge": (("speculation", "epistemic", "doxastic"), lex.hedges_in, HEDGE_CANDIDATES, False),
    "negation": (("negation",), lex.negations_in, NEGATION_CANDIDATES, True),
    "conditional": (("conditional",), lex.conditionals_in, CONDITIONAL_CANDIDATES, True),
    "attribution": (("attribution",), lex.attribs_in, ATTRIB_CANDIDATES, False),
}


def load_dev():
    """Dev rows, grouped by corpus.

    Grouped, not pooled, because of a bug this file shipped with for one run: pooling
    every corpus meant attribution candidates were scored against BioScope and Szeged
    sentences, which carry no attribution annotation at all, so every firing there counted
    as a false positive. Bare "say" came out at 282 false positives and 0.17 precision
    when its real cost on the corpus that actually annotates attribution is 14.

    The bug was DEFLATING rather than flattering, which is the rarer direction and the
    reason it nearly stuck: a tuner that rejects everything looks admirably strict.
    """
    by_corpus: dict[str, list] = {}
    for p in sorted(NORMALIZED.glob("*.jsonl")):
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        dev = [r for r in rows if r.get("split") == "dev"]
        if dev:
            by_corpus[p.stem] = dev
    return by_corpus


def rows_annotating(by_corpus, gold_classes):
    """Only corpora that actually annotate these classes can score a candidate."""
    out = []
    for rows in by_corpus.values():
        if any(c["cls"] in gold_classes for r in rows for c in r["cues"]):
            out += rows
    return out


def marginal(rows, gold_classes, detect, term, is_regex):
    """TP/FP a term adds on sentences the current lexicon does NOT already fire on."""
    hits = re.compile(term, re.IGNORECASE).search if is_regex else \
        (lambda t, s=term.lower(): s in t.lower())
    gained_tp = gained_fp = 0
    for row in rows:
        if detect(row["text"]):
            continue                       # already covered; marginal gain is zero
        if not hits(row["text"]):
            continue
        gold = any(c["cls"] in gold_classes for c in row["cues"])
        if gold:
            gained_tp += 1
        else:
            gained_fp += 1
    return gained_tp, gained_fp


def main() -> int:
    by_corpus = load_dev()
    if not by_corpus:
        print("no dev rows; run build_corpora.py first")
        return 1
    print(f"dev: {sum(len(v) for v in by_corpus.values())} sentences across "
          f"{len(by_corpus)} corpora\n")
    for task, (classes, detect, candidates, is_regex) in TASKS.items():
        sub = rows_annotating(by_corpus, classes)
        if not sub:
            print(f"=== {task}: no corpus annotates this class, skipping\n")
            continue
        print(f"=== {task} ({len(sub)} dev sentences from corpora that annotate it)")
        print(f"{'candidate':24s} {'+TP':>6s} {'+FP':>6s} {'precision of the addition':>26s}")
        scored = []
        for term in candidates:
            tp, fp = marginal(sub, classes, detect, term, is_regex)
            prec = tp / (tp + fp) if tp + fp else 0.0
            scored.append((tp, fp, prec, term))
        for tp, fp, prec, term in sorted(scored, key=lambda x: -x[0]):
            verdict = "keep" if prec >= 0.60 and tp >= 10 else "reject"
            print(f"{term:24s} {tp:6d} {fp:6d} {prec:25.2f}  {verdict}")
        print()
    print("Threshold: a candidate is kept only if its OWN additions are >=60% correct\n"
          "and it fires at least 10 times. Chosen terms go into lexicons.py by hand;\n"
          "the consequence is then read off the TEST split by eval_lexicons.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
