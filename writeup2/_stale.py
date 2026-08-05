"""Scan for phrasings and numbers that belonged to superseded drafts.

Every entry here was, at some point, a true statement in this paper. Each was later
retracted or superseded. A consistency check has to look for the OLD claims, not just
verify the new ones, because the failure mode is a sentence surviving a rewrite.
"""
import re
from pathlib import Path

t = (Path(__file__).resolve().parent / "main.tex").read_text(encoding="utf-8")
body = t[t.index(r"\begin{document}"):]

STALE = [
    (r"(?<!, )\+18\.3(?!\])", "the pre-promoted assertion effect, now split"),
    (r"subordination does everything", "retracted figure caption"),
    (r"labels are not the mechanism(?![^&]*retracted)",
     "retracted, and labels are the one component that replicates"),
    (r"does as well as the labelled schema", "equivalence not established"),
    (r"helps where the compressor is weakest", "retracted v2 title claim"),
    (r"splits by model family(?![^&]*retracted)", "retracted"),
    (r"family split(?!.{0,80}retract)", "no family split; check context"),
    (r"ran on Haiku~4\.5 only", "the ablation now runs on both models"),
    (r"the ablation is one model", "no longer true"),
    (r"\$950\$", "old pair count"),
    (r"\$860\$", "old pair count"),
    (r"widens monotonically(?![^&]*retracted)", "retracted prediction"),
]

fails = 0
for pat, why in STALE:
    for m in re.finditer(pat, body, re.I):
        line = body[:m.start()].count("\n") + 1
        ctx = re.sub(r"\s+", " ", body[max(0, m.start() - 70):m.end() + 70])
        # a mention inside a retraction row is fine
        if "retracted" in ctx.lower() or "earlier draft" in ctx.lower() \
                or "previous draft" in ctx.lower() or "title history" in ctx.lower():
            continue
        fails += 1
        print(f"!! line ~{line}: {why}")
        print(f"   ...{ctx}...")
print(f"\n{fails} stale claims found")
