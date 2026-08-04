# RefChecker: port, don't fork (Phase 1 verdict, 2026-08-03)

The broadening plan proposed forking Amazon Science's RefChecker (Apache-2.0, archived
2026-04-08) and living in the fork. Evaluated against a shallow clone before writing any
code. Verdict: **decline the fork, port three specific ideas.**

## Evidence

- **Portable core is small.** `base.py` + extractor + checker interfaces + prompts +
  `utils.py` + `aggregator.py` = 1,537 lines. The remaining ~4,900 lines are benchmark
  collection, the demo app, and AlignScore/NLI/repc checker implementations TWSS does not
  want.
- **The dependency tree fails TWSS's packaging rule.** RefChecker's pyproject makes
  torch, transformers, pytorch_lightning, boto3, spacy, plotly, nltk, scikit-learn,
  accelerate, litellm and diskcache all *mandatory*. TWSS ships `dependencies = []` and
  the design note requires deterministic checks to run without a deep-learning stack.
  A fork starts life violating its own constitution.
- **The plumbing marked "reuse" is the rotted part.** anthropic is pinned `^0.29`
  (pre-1.0; the SDK had a breaking rewrite), litellm `^1.49` (2024-era). Last substantive
  upstream development was mid-2024. Every provider call site needs rewriting under
  either strategy, so the fork buys maintenance burden without buying working code.

Kill criterion from the plan ("if the bidirectional example needs touching more than a
handful of their files, port instead") fired at inspection time, before the example.

## What to port (with attribution, when the ADDED detector lands)

1. **Claim-decomposition criteria** from `extractor_prompts.py`: fine-grained,
   self-contained, decontextualized claims (their "Donald Trump won the presidential
   election *in 2016*" completeness rule), and the explicit "this is an EXTRACTION task,
   do not judge factuality" separation of perception from policy.
2. **Sentence-ID evidence localization**: source sentences are indexed `[1] [2] ...` and
   every extracted claim cites the sentence ids it came from. Cheap, deterministic
   evidence spans that survive the LLM round-trip and can be validated the same way the
   witness's quoted markers already are.
3. **Checking discipline** from `checker_prompts.py`: Entailment / Neutral /
   Contradiction three-way labels with "do NOT use your own knowledge", which maps onto
   the gate's rule that UNCHECKABLE is never PASS (their Neutral is our UNCHECKABLE, not
   our pass).

Prompts are Apache-2.0 licensed material: when adapted, carry attribution and a NOTICE
entry. No RefChecker code or prompt text is included in this repo as of this note.

## Status of the broadening

`transform.py` implements the transformation view over the existing gate (see CHANGELOG
"Unreleased"). The ADDED detector (where the port targets above become relevant) is not
started; `TransitionReport.not_checked` says so on every report.
