# Pre-registration: held-out replication of the field-over-parenthetical effect

**Written and committed before any API call for this experiment.** The commit that adds
this file also adds `experiments/claims_corpus_v3.py`, the sixty claims it will run on.
The point of the exercise is that the claims and the analysis exist, in public, before
the numbers do.

## Why this is needed

The fifty claims in `claims_corpus_v3`'s predecessor (V2) were written **after** observing
that the original ten-claim corpus produced a null. That is a legitimate way to develop an
experiment and it is also exactly the condition under which stimulus tuning happens: the
author had just learned that the corpus decides the answer, and then wrote the corpus that
produced the answer. No re-analysis of that data can remove the concern, because the
concern is about how the data was generated.

A reviewer raised this directly. This is the response.

## Hypothesis

Under tight compression, a claim's epistemic standing is retained more often when written
as a labelled field than when written as a parenthetical clause.

## Prediction, stated now

On the sixty V3 claims, Haiku 4.5, budgets `brutal` and `severe`, 3 replicates:

- **Primary:** the per-claim sign test on field-minus-parenthetical differences will be
  significant at p < 0.01, with more claims favouring the field form than the
  parenthetical.
- **Effect size:** the claim-clustered mean difference will fall between **+8 and +25
  percentage points**. The V2 estimate was +15.9 with a 95% CI of [+10.8, +20.6]; this
  interval is deliberately wider than that to be a real prediction rather than a restatement.
- **Direction of the failure I consider most likely:** a smaller effect than V2, because
  V2 may be tuned. An effect below +8 points would still count as a partial replication in
  direction but a failure of the stated size prediction, and I will say so in those words.

## What counts as a failure

- Sign test p >= 0.05 → **the effect does not replicate.** The paper's headline claim
  becomes NOT SHOWN and the abstract is rewritten around a failed replication.
- Sign test p in [0.01, 0.05) → weaker than predicted; reported as a qualified
  replication with the prediction marked as missed.
- Claim-clustered mean outside [+0.08, +0.25] → the size prediction failed, reported as
  such even if the sign test passes.

## Frozen analysis plan

1. Model: `claude-haiku-4-5`. Arms: `field` and `paren` only. Levels: `brutal`, `severe`.
   Replicates: 3. Seed: 900. Corpus: V3, all sixty claims.
2. Outcome: a blind reader sees only the stored memory and the claim to look up, and
   answers `established_fact` / `qualified` / `absent`. Retention = `qualified`.
3. Unit of analysis: the **claim**. Per-claim difference in retention rate between arms;
   exact sign test across claims; claim-clustered bootstrap for the interval.
4. Pairs with a missing arm are dropped, as in every previous run. Unparsable judge
   replies are excluded and counted.
5. **One run.** No adding replicates after seeing the result, no adding or removing
   pressure levels, no switching models, no dropping claims, no adding arms.
6. The result is reported whatever it is, including a null, in the paper and in the
   claims ledger.

## What this does not fix

- The claims are still written by the same author, in English, to the same register
  spec. A genuinely independent corpus would be better and is not available here.
- The outcome is still judged by a model. No human annotation is collected in this
  experiment or any other in this paper.
- It replicates the two-cell effect only. The ablation decomposition (wording, labels,
  subordination, layout, length) is not re-run and remains exploratory.
