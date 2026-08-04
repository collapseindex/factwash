"""Pre-submission consistency check for the preprint. Exits nonzero on any failure.

Run from the repo root after any paper edit: python writeup/check_paper.py

Verifies the build (no errors, no unresolved refs, no placeholders, 8-9 page body), that
every cross-reference resolves, that appendix lettering matches the mini-TOC, that the
headline numbers appear in BOTH the paper and the project README, that the claims ledger
still carries all four statuses, and that the arXiv tarball packages exactly the figures
the paper includes. Negative-tested: changing a README number makes the parity check
fail. writeup/ is gitignored, so this file is the paper's equivalent of
tests/test_published_numbers.py."""
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path("c:/Users/alexs/Desktop/factwash")
W = ROOT / "writeup"
fails, warns = [], []


def check(ok, msg):
    (print(f"  ok   {msg}") if ok else (fails.append(msg), print(f"  FAIL {msg}")))


def warn(ok, msg):
    if not ok:
        warns.append(msg)
        print(f"  warn {msg}")


tex = (W / "main.tex").read_text(encoding="utf-8")
log = (W / "main.log").read_text(encoding="utf-8", errors="replace")
readme = (ROOT / "README.md").read_text(encoding="utf-8")

import fitz
doc = fitz.open(W / "main.pdf")
pdf = " ".join(p.get_text().replace("\n", " ") for p in doc)
pdf = re.sub(r"\s+", " ", pdf)

print("== build ==")
check(len(re.findall(r"^!", log, re.M)) == 0, "no LaTeX errors")
check("Warning" not in log or "undefined" not in log, "no undefined references")
check("??" not in pdf, "no unresolved cross-references in PDF")
check(tex.count("needsdata{") == 0, "no NEEDS DATA placeholders")
# The body currently ends on page 8; page 9 is tolerated. The 8-page ACL limit does
# not bind a preprint, so this deliberately accepts either rather than forcing prose
# cuts for a line or two. It still catches real regression: spilling to page 10 fails.
# Structural, not string-matched: the body is everything before the unnumbered
# Limitations section, so the page Limitations starts on is the page the body ends on.
# (An earlier version matched the conclusion's last sentence and broke the moment that
# sentence straddled a page break.)
_lim_page = next((i + 1 for i, p in enumerate(doc)
                  if re.search(r"\bLimitations\b", p.get_text())), None)
check(_lim_page is not None and _lim_page <= 9,
      f"body ends by page 9 (Limitations starts on page {_lim_page})")

# Layout: a wide table placed in a two-column region silently overflows into the
# neighbouring column, which LaTeX reports only as an Overfull hbox. Caught in review
# once (App. B ran over Appendix C's text); pinned here.
_overfull = [m for m in re.findall(r"Overfull \\hbox \((\d+)\.\d+pt", log) if int(m) >= 20]
check(not _overfull, f"no badly overfull boxes (worst: {max(_overfull, default=0)}pt)")

print("\n== labels and refs ==")
labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
refs = set(re.findall(r"\\(?:ref|pageref|hyperref\[)\{?([a-z:]+[a-z0-9_:]*)", tex))
refs = {r.strip("[]{}") for r in re.findall(r"\\ref\{([^}]+)\}", tex)} | \
       {r for r in re.findall(r"\\hyperref\[([^\]]+)\]", tex)} | \
       {r for r in re.findall(r"\\pageref\{([^}]+)\}", tex)}
missing = refs - labels
check(not missing, f"every \\ref resolves (missing: {missing or 'none'})")
unused = {l for l in labels if l not in refs and l.startswith(("fig:", "tab:"))}
warn(not unused, f"unused float labels: {unused}")

print("\n== appendix lettering ==")
app_secs = re.findall(r"\\section\{([^}]+)\}\s*\n\\label\{(app:[^}]+)\}", tex)
toc = re.findall(r"\\textbf\{([A-Z])\}\\quad ([^}]+)\}", tex)
check(len(app_secs) == len(toc),
      f"appendix count matches TOC ({len(app_secs)} sections, {len(toc)} TOC rows)")
for (title, _), (letter, toc_title) in zip(app_secs, toc):
    check(title.strip() == toc_title.strip(), f"appendix {letter} title matches TOC: {title!r}")

print("\n== paper/README number parity ==")
pairs = [("0.57", "ADDED precision"), ("0.30", "ADDED recall"), ("96.9", "ADDED coverage"),
         ("8 of 27", "ADDED recall counts"), ("[0.16, 0.48]", "ADDED recall interval"),
         ("62%", "mem0 flag rate"), ("5 of 8", "mem0 counts"),
         ("105,596", "corpus total"), ("0.91", "negation F1"), ("29%", "adversarial recall")]
for val, what in pairs:
    inp = val.replace(",", ",") in pdf or val.replace(",", "{,}") in pdf
    inr = val in readme
    check(inp and inr, f"{what} ({val}) present in both paper and README")

print("\n== overclaim guards ==")
low = pdf.lower()
check("flag rate" in low and "not a verified" in low,
      "bench metric framed as a flag rate, not a verified laundering count")
check("errs both ways" in low or "errs in both" in low or "not a floor" in low,
      "flag rate framed two-sided, not one-sided")
check("lower bound" not in low, "no one-sided 'lower bound' framing left")
check("0.571" not in pdf and "0.296" not in pdf,
      "no three-decimal false precision on small-n rates")
check("[0.31, 0.86]" in pdf or "0.31" in pdf, "mem0 rate carries its interval")

print("\n== model attribution ==")
bbl = (W / "main.bbl").read_text(encoding="utf-8")
for name, key in {"haiku": "anthropic2025haiku", "sonnet": "anthropic2025sonnet"}.items():
    named = name in pdf.lower()
    check(not named or key in bbl,
          f"{name} is named in the paper and cited ({key})" if named
          else f"{name} not used, nothing to cite")
check("Models." in pdf, "reproducibility appendix carries the model list")

print("\n== claims-ledger integrity ==")
rows = tex.count(" \\\\\n\n") if False else len(re.findall(r"\\textsc\{(shown|not shown|retracted|not claimed)\}", tex))
check(rows >= 20, f"claims table has >= 20 status cells (found {rows})")
for status in ("retracted", "not claimed", "not shown", "shown"):
    check(f"\\textsc{{{status}}}" in tex, f"claims ledger uses status {status.upper()}")

print("\n== arXiv package ==")
tar = W / "factwash_arxiv.tar.gz"
check(tar.is_file(), "tarball exists")
with tarfile.open(tar) as t:
    names = t.getnames()
check("main.tex" in names and "main.bbl" in names, "tarball has main.tex + main.bbl")
check("acl.sty" in names and "acl_natbib.bst" in names, "tarball has style files")
figs_tex = set(re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", tex))
figs_tar = {Path(n).stem for n in names if n.endswith(".pdf")}
check(figs_tex <= figs_tar, f"every included figure is packaged (tex {figs_tex}, tar {figs_tar})")
check(not (figs_tar - figs_tex), f"no orphan figures packaged (orphans: {figs_tar - figs_tex})")
check(r"\pdfoutput=1" in tex, "pdfoutput=1 set for arXiv")

print("\n== repo state ==")
r = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                   capture_output=True, text=True)
dirty = [l for l in r.stdout.splitlines() if l.strip()]
warn(not dirty, f"{len(dirty)} uncommitted change(s) in repo")
r2 = subprocess.run(["git", "-C", str(ROOT), "log", "--oneline", "-1"],
                    capture_output=True, text=True)
print(f"  head: {r2.stdout.strip()}")

print(f"\nRESULT: {len(fails)} failures, {len(warns)} warnings")
for f in fails:
    print("  FAIL:", f)
sys.exit(1 if fails else 0)
