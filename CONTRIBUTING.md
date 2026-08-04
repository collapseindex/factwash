# Contributing

Contributions are welcome. This file is short because the rules are few, but the few are
load-bearing: most of them exist because breaking them once already produced a wrong
published number.

## Setup

```bash
git clone https://github.com/collapseindex/factwash && cd factwash
pip install -e ".[dev]"
pytest                      # full suite, offline, no API key
```

Optional extras: `.[fix]` (anthropic, for the fixer and the live witness), `.[units]`
(quantulum3, for the unit-drift detector). The default install must keep
`dependencies = []`; anything heavier goes behind an extra, no exceptions.

## The rules that are the project

1. **N/A is never a pass, and UNCHECKABLE is never PASS.** A check that cannot apply
   says so. A write that cannot be aligned with its source is not verified. Any change
   that quietly converts either into a pass will be rejected regardless of what else it
   improves.
2. **Every published number is asserted by a test.** `tests/test_published_numbers.py`
   recomputes the README's figures from the shipped corpora and fails on drift. If your
   change moves a number, update the README in the same commit; the test will hold you
   to it. The same applies in reverse: do not edit a README figure without the
   measurement behind it.
3. **Negative-test your checks.** A detector ships with a test that breaks it on
   purpose and asserts the failure is caught. A checker that has only ever passed is
   decorating, not validating. See `tests/test_core/test_negative.py` for the pattern.
4. **Ported lexicons stay verbatim.** The `MC_*`, `SOURCE_FIRST` and `HEDGEKEEP`
   constants are ports from published papers and are kept auditable against their
   sources, over-matches included. New vocabulary goes in the separate `EXT_*` tuples
   with a comment saying where it was mined and under what rule.
5. **Models perceive; code decides.** A model component may extract evidence (spans,
   markers, qualifiers) that is validated against the text before use. It may not
   return a verdict, and an unusable reply leaves the deterministic result standing.
   Detector failures degrade to a declared `not_checked` entry, never to a crash and
   never to a silent pass.

## Adding a check or a transform detector

A new check needs: what it catches in one sentence, which verdict a failure maps to,
evidence carried on every flag, documented limitations (including known false positives
and false negatives), and positive + negative + adversarial test cases. If it is
evaluated against any corpus, say which one; this repo already juggles three distinct
extractor-output corpora and the paper had to disambiguate them once.

A new transform detector additionally declares itself in `transform.py`'s coverage
accounting, so that reports state what was not checked.

## Style

Match the code around you. Type hints on public APIs, docstrings that explain why
rather than what, named constants over magic numbers, and comments only where the code
cannot say it. Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).

## Security

No secrets in code, tests, or fixtures; configuration comes from the environment and
`.env` is gitignored. Mask any credential in logs to its last four characters. Corpus
data derived from the Enron archive must keep emails and phone numbers masked, as the
build scripts already do.
