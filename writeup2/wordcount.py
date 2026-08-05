"""Word count for the abstract, with LaTeX stripped.

Kept as a file rather than a shell one-liner because the backslashes get mangled
through the shell every single time.
"""
import re
import sys
from pathlib import Path

TEX = Path(__file__).resolve().parent / "main.tex"


def words(chunk: str) -> int:
    s = re.sub(r"%.*", "", chunk)
    s = re.sub(r"\\(?:cite[a-z]*|ref|label|S)\b\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", "x", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", s)
    s = re.sub(r"[${}~\\]", " ", s)
    return len(s.split())


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    if not m:
        print("no abstract found")
        return 1
    n = words(m.group(1))
    print(f"abstract: {n} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
