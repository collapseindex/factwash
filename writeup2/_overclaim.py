"""Flag sentences that assert more than a two-model, one-provider study can carry."""
import re
from pathlib import Path

STRONG = ["always", "never", "any model", "all models", "proves", "proved",
          "demonstrates that", "establishes that", "compressors", "in general",
          "universal", "guarantee", "must be", "shows that"]

HEDGES = ("one model", "haiku", "sonnet", "we did not", "not shown", "do not claim",
          "wary", "assumed", " only ", "rather than a law", "here", "this data")

t = (Path(__file__).resolve().parent / "main.tex").read_text(encoding="utf-8")
body = t[t.index(r"\begin{document}"):t.index(r"\appendix")]
body = re.sub(r"%.*", "", body)
# strip figure source; TikZ styles contain words like "never" and are not prose
body = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", body, flags=re.S)
plain = re.sub(r"[${}\\]", " ", " ".join(body.split()))
sents = re.split(r"(?<=[.!?])\s+", plain)

flagged = 0
for s in sents:
    low = s.lower()
    for w in STRONG:
        if w in low:
            hedged = any(h in low for h in HEDGES)
            if not hedged:
                flagged += 1
                print(f"!! [{w}] {s.strip()[:160]}")
            break
print(f"\n{flagged} unhedged strong claims in the body")
