# arXiv submission notes (prepared 2026-08-03)

**Package:** `factwash_arxiv.tar.gz` (main.tex + main.bbl + acl.sty + acl_natbib.bst +
figures/fig_{mining,memorise}.pdf). Verified: extracts to a clean directory and
compiles with pdflatex alone (no bibtex needed; .bbl included), 15 pages total
(9-page body + Limitations/Ethics/refs/appendices A-F), 0 errors,
0 undefined references. Layout: intro completes on page 1; Figure 1 (pipeline) tops
page 2; body ends with the Conclusion on page 8. References include the tooling used (quantulum3, Cohen 1960 for kappa, the
witness model card). `\pdfoutput=1` is set. The pipeline figure is TikZ, compiled
in-document, so no extra assets.

**Title:**
factwash: Catching AI Rewrites That Wash Hearsay into Fact

(arXiv title field takes no subtitle; the subtitle "Linguistic class predicts where
deterministic checking suffices" stays in the PDF. If you want it in the metadata,
append after a colon or em-free dash of your choosing.)

**Categories:** cs.CL (primary), cross-list cs.AI. cs.SE plausible third.

**License:** CC BY 4.0 recommended (matches the Apache-2.0 openness of the tool;
the arXiv non-exclusive license is the conservative alternative).

**Comments field suggestion:**
15 pages (9-page body), 3 figures. Code: https://github.com/collapseindex/factwash

**Plain-text abstract (single paragraph, TeX stripped):**

AI systems rewrite information constantly: conversations become stored memories,
documents become answers. The rewrite can keep a claim while washing away what made it
checkable, who said it, how sure they were, when it held. We call that failure
factwashing, and release factwash, an open-source write-time gate that catches it
deterministically, with named flags and evidence rather than an LLM judge. Building it
answers a practical question: when does a cheap check suffice, and when do you need a
model? What decides is whether the property has a bounded surface-cue inventory.
Explicit negation cues are close to enumerable, so a word list finishes and transfers,
reaching 0.91 F1 on untuned text. Hedging and attribution have open-ended realizations,
so vocabulary plateaus near half recall, and a one-question LLM witness recovers +17 and
+15 points of cue-detection recall at equal precision. Deployed, that witness may only
lower a verdict, so it buys precision rather than coverage. We measure cue detection on
105,596 independently annotated sentences. A blind-labelled corpus of memory writes then
locates the failure: 55% of bad writes in conversational hearsay, 7% in business email
(p < 0.001), so the first deployment question is not which detector to use but whether
the failure occurs at all. On unmodified mem0 2.0.7, the gate flags 5 of 8
hedged-hearsay writes.

**Abstract addition since first draft:** the abstract now ends with the production
result (the gate flagging 5 of 8 of mem0 2.0.7's hedged-hearsay writes), the strongest
adopter-facing number in the paper. If you retitle or trim, keep that sentence.

**Consistency gate:** `python writeup/check_paper.py` (from the repo root) must print
`0 failures`. It checks the build, cross-references, appendix lettering vs the TOC,
paper/README number parity, the claims-ledger statuses, and that the tarball packages
exactly the figures the paper includes. It is negative-tested: changing a README number
makes it fail.

**Pre-submission checklist:**
1. `python writeup/check_paper.py` and `python writeup/check_abstract_parity.py` both
   report zero failures.
2. The repo is pushed and the tag is public, since the paper links it on page 1.
3. The tarball extracts and compiles standalone with pdflatex alone.
4. Announcement-cycle cutoffs are 14:00 ET on weekdays, if timing matters.
