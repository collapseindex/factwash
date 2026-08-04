"""Regenerate the plain-text abstract in ARXIV_SUBMIT.md from main.tex."""
import re
from pathlib import Path

W = Path("c:/Users/alexs/Desktop/factwash/writeup")
tex = (W / "main.tex").read_text(encoding="utf-8")
start = tex.index("\\begin{abstract}") + len("\\begin{abstract}")
abs_tex = tex[start:tex.index("\\end{abstract}")]

plain = re.sub(r"\\emph\{([^}]*)\}", r"\1", abs_tex)
plain = re.sub(r"\\texttt\{([^}]*)\}", r"\1", plain)
plain = plain.replace("\\sys", "factwash")
plain = re.sub(r"\\[a-zA-Z]+", "", plain)
plain = plain.replace("$", "").replace("{,}", ",").replace("{", "").replace("}", "")
plain = plain.replace("``", '"').replace("''", '"')
plain = re.sub(r"\s+", " ", plain).strip()

words, lines, cur = plain.split(), [], ""
for w in words:
    if len(cur) + len(w) + 1 > 88:
        lines.append(cur)
        cur = w
    else:
        cur = (cur + " " + w).strip()
lines.append(cur)
block = "\n".join(lines)

notes = W / "ARXIV_SUBMIT.md"
s = notes.read_text(encoding="utf-8")
key = "**Plain-text abstract (single paragraph, TeX stripped):**"
head, sep, tail = s.partition(key)
after = tail.split("**", 1)[1]
notes.write_text(head + sep + "\n\n" + block + "\n\n**" + after,
                 encoding="utf-8", newline="\n")
print("regenerated notes abstract:", len(block), "chars")
