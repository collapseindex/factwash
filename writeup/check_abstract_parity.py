import re
from pathlib import Path

W = Path("c:/Users/alexs/Desktop/factwash/writeup")
tex = (W / "main.tex").read_text(encoding="utf-8")
start = tex.index("\\begin{abstract}") + len("\\begin{abstract}")
end = tex.index("\\end{abstract}")
abs_tex = tex[start:end]

plain = re.sub(r"\\emph\{([^}]*)\}", r"\1", abs_tex)
plain = re.sub(r"\\texttt\{([^}]*)\}", r"\1", plain)
plain = re.sub(r"\\sys", "factwash", plain)
plain = re.sub(r"\\[a-zA-Z]+", "", plain)
plain = plain.replace("$", "").replace("{,}", ",").replace("{", "").replace("}", "")
plain = plain.replace("``", '"').replace("''", '"')
plain = re.sub(r"\s+", " ", plain).strip()

notes = (W / "ARXIV_SUBMIT.md").read_text(encoding="utf-8")
key = "**Plain-text abstract (single paragraph, TeX stripped):**"
block = notes.split(key)[1]
block = block.split("**")[0]
block = re.sub(r"\s+", " ", block).strip()


def norm(t):
    return re.sub(r"[^a-z0-9%.,() ]", "", t.lower())


a, b = norm(plain), norm(block)
print("paper abstract chars:", len(a), "| notes abstract chars:", len(b))
print("PARITY:", "MATCH" if a == b else "DIFFER")
if a != b:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            print("first diff at", i)
            print("  paper:", repr(a[max(0, i - 60):i + 60]))
            print("  notes:", repr(b[max(0, i - 60):i + 60]))
            break
    else:
        print("  one is a prefix of the other; tail:", repr((a if len(a) > len(b) else b)[min(len(a), len(b)):][:160]))
