# Preprint around the tool (repositioned 2026-08-03; was an ACL venue draft)

Untracked (`writeup/` is gitignored). Formatting copied from the
manufactured-confidence paper: same `acl.sty`, same preamble, same claims-table
style as report-gap.

```bash
cd writeup && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Repositioning note

No venue. This is a preprint around **factwash**: the tool leads, the closed/open-class
finding is its design evidence, and the failure mode is coined by name ("factwashing").
Applied: title + abstract lead with the tool, contributions tool-first, a "released
tool" section (gate + transformation view + units detector), nocite scaffold removed,
appendices B/C/D filled, claims table gained a units row. The venue-era warning below
("a reviewer who reads this as 'they built a linter' will reject it") no longer applies;
kept for history.

## The thesis, in one sentence

Whether a cheap deterministic check is enough is predicted by the **linguistic class**
of the property being checked. Closed classes (negation, conditionals) can be enumerated,
so a word list transfers across domains. Open classes (hedging, attribution) cannot, so a
word list plateaus and a model earns its cost exactly there.

That is the paper. The tool is the artifact, not the claim. A reviewer who reads this as
"they built a linter" will reject it, and would be right to: the linter is a word list
plus an optional API call. The finding is the mechanism.

## Order of the argument

The positives lead. The measured-negatives section (now §8, "What it does not catch",
distinct from the methodological "Limitations") comes after the reader has seen the
contribution.

| § | Content | Status |
|---|---|---|
| 1 | Intro: the harm, the finding, contributions | scaffolded |
| 2 | Related work, four short paragraphs | needs citations |
| 3 | What a write loses + the seven checks | table done |
| 4 | **External evaluation** — the closed/open split | numbers real |
| 5 | **Witness vs word list** head-to-head | numbers real |
| 6 | Memory writes: the labelled corpus + end-to-end | **needs the labels** |
| 8 | What it does not catch: the nulls, framed as scope | done |
| A | Claims and evidence table | seeded, needs rows |

## `\needsdata{}`

Every number that does not exist yet is wrapped in `\needsdata{}`, which renders in
**red bold** in the PDF. Before submission:

```bash
grep -c 'needsdata' main.tex     # must be 0
```

This exists because this project has published a wrong number twice through drift. A
placeholder that renders as ordinary text would be a third way to do it.

## What is blocking

Section 6 is the only section that cannot be written today. It needs the blind labelling
pass over `data/corpus/session_pool_enron_s0_s0.jsonl` (300 items, ~2 hours, resumable):

```bash
python experiments/corpus/label.py label --session data/corpus/session_pool_enron_s0_s0.jsonl
python experiments/corpus/label.py score --session data/corpus/session_pool_enron_s0_s0.jsonl
python experiments/corpus/label.py agree --session data/corpus/session_pool_enron_s0_s0.jsonl --n 40
```

`agree` gives the self-agreement number. Report it — a labeller who cannot reproduce
their own calls sets the ceiling on every figure the corpus supports, and a reviewer will
ask.

## Two calls made in the scaffold, both reversible

**Title.** Descriptive, with TWSS as the system name rather than the title. "That's What
Source Said" is a good name and it is in the title, but an ACL title that reads only as
the joke invites a reviewer to discount the paper before the abstract. The current title
keeps both.

**Framing of the nulls.** Escalate mode, the recall ceiling, and scope expansion are all
in §7 and in the claims table, stated plainly, including the one we retracted ourselves.
They are not in the abstract. That is the right call for acceptance and it is still
honest: nothing is hidden, and the claims table is more complete than most papers'.

## Page budget (8 pages, refs and appendix excluded)

| § | Pages |
|---|---|
| 1 Intro | 1.0 |
| 2 Related | 0.75 |
| 3 Problem + checks | 0.5 |
| 4 External | 2.0 |
| 5 Witness | 1.0 |
| 6 Writes | 1.25 |
| 8 What it does not catch | 0.75 |
| 8 Conclusion | 0.25 |
| | **7.5** |

Half a page of slack. Tables 1–4 are budgeted inside those numbers.

## Style

Plain sentences. One idea per sentence. No stacked subordinate clauses. If a sentence
needs a second read, split it. The MC paper's abstract is the register to match: it
explains a mechanism to someone who has not read the related work.
