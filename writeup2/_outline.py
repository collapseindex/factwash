import re
from pathlib import Path

lines = (Path(__file__).resolve().parent / "main.tex").read_text(
    encoding="utf-8").splitlines()
pat = re.compile(r"\\(section\*?|paragraph|subsection)\{(.+?)\}")
hits = [(i, m.group(1), m.group(2)) for i, l in enumerate(lines)
        if (m := pat.match(l))]
total = 0
for j, (i, kind, name) in enumerate(hits):
    end = hits[j + 1][0] if j + 1 < len(hits) else len(lines)
    body = " ".join(lines[i:end])
    words = len(re.sub(r"\\[a-zA-Z]+|[{}$\\]", " ", body).split())
    total += words
    pad = "" if kind.startswith("section") else "    "
    flag = "  <-- long" if words > 300 else ""
    print(f"{pad}{kind[:9]:<9} {name[:50]:<50} {words:>5}w{flag}")
print(f"\ntotal body words: {total}")
