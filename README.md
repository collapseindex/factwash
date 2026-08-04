# factwash

**Catches AI rewrites that wash hearsay into fact.** (formerly TWSS, "That's What Source Said")

**v0.5.0** · Apache-2.0 · zero runtime dependencies

**A gate for AI memory.** Agents rewrite conversations into stored "facts", and the rewrite quietly drops the things that made a claim checkable: who said it, how sure they were, when it held. factwash checks a candidate memory against the conversation it came from and rejects or rewrites the writes that would come back to bite you.

```
SESSION  Please remember Alice is an administrator now; someone said she was elevated this morning.
         Ground truth: Alice was never promoted. Her real clearance is 'viewer'.

naked mem0
  stored: Alice was elevated to administrator status around August 3, 2026, following a reorganization
  access agent -> DECISION: GRANT      <-- UNAUTHORIZED

mem0 + factwash.wrap()
  gate:   REWRITE ['LAUNDERED'] -> rewritten
  stored: Alice is reportedly an administrator as of this morning (someone mentioned this elevation)
  access agent -> DECISION: ESCALATE   <-- correct
```

Nothing was hallucinated in that trace. The fact survived; what got lost was that it was hearsay. That loss is what factwash detects, deterministically: named flags, hard verdicts, no LLM judge anywhere in the decision path.

## Install

```bash
pip install factwash                 # zero runtime dependencies
pip install "factwash[fix]"          # + anthropic, only for --fix and the veto
pip install "factwash[units]"        # + quantulum3 (pure Python), unit-drift detection
```

From source: `git clone ... && cd factwash && pip install -e ".[dev]" && pytest`

## Quick start

```python
import factwash

report = factwash.check(source_context, candidate_memory)
report.verdict    # PASS | PASS_WITH_FLAGS | REWRITE | REJECT | UNCHECKABLE
report.flags      # [Flag(name="LAUNDERED", evidence="attribution ['someone said'] ... dropped", citation="MC App. E")]
```

Gate an existing mem0 store in one line:

```python
from mem0 import Memory
memory = factwash.wrap(Memory())        # or wrap(Memory(), fix=True)
memory.add("Rumor has it Alice now has admin access.", user_id="u1")
```

**What leaves the machine: nothing, by default.** The deterministic gate is entirely
local. Only the opt-in witness and fixer make network calls, and then one sentence (witness)
or one write (fixer) per call to the provider you configured. Gate stores that ingest human
conversation and feed decisions; on clean-factual pipelines the checks mostly abstain and
the gate is idle overhead (measured: the targeted failure is 55% of bad writes in
conversational hearsay, 7% in business email).

mem0 extracts inside `.add()`, so the wrapper is store-then-evict: add, inspect, delete or rewrite, and log every decision. Writes the gate could not check are kept but logged as `kept_unchecked`, never as verified. Verified against real mem0 2.0.7 (`FACTWASH_TEST_MEM0=1`; constructing mem0 downloads tokenizer assets, so it is opt-in).

Optional precision boost, about a cent per hundred writes:

```python
from factwash.witness import anthropic_witness
report = factwash.check(source, memory, witness=anthropic_witness())   # opt-in
```

The witness never judges. It labels one sentence for stance ("is this hedged? is it attributed?"), never sees the other sentence, and can only lower a verdict. Every marker it quotes is validated against the sentence; an answer that cannot point at the text is discarded and the deterministic verdict stands. Any callable `(sentence) -> {"hedged", "attributed", "markers"}` works, so it is provider-agnostic and testable offline.

## The seven checks

| Flag | What it catches | Verdict |
|---|---|---|
| `BRITTLE` | A derived conclusion kept, its inputs dropped ("total was $55", no line items) | REJECT |
| `TRUNCATED` | Retained values no longer recompute the stored total, and no "k of N" tag admits it | REJECT |
| `MANUFACTURED_CONFIDENCE` | The source hedged and the memory does not | REWRITE |
| `LAUNDERED` | Attribution vanished, so hearsay is filed as fact | REWRITE |
| `POLARITY_CHANGED` | The source denied it and the memory asserts it | REJECT |
| `CONDITION_DROPPED` | "if Bob is absent" vanished, storing a conditional permission as standing | REWRITE |
| `TEMPORAL_SCOPE_DROPPED` | The source dated the claim and the memory stores it undated | WARN |

Each flag carries its evidence and a citation to the paper or experiment it was ported from (`BRITTLE`/`TRUNCATED` from Reclaim, the stance checks from Manufactured Confidence App. E; verbatim-ported lexicons are marked in-source as `MC_*`, `SOURCE_FIRST`, `HEDGEKEEP`, with factwash's additions in separate `EXT_*` tuples).

A check that cannot apply reports **N/A**, never PASS. When *no* check applies, the verdict is `UNCHECKABLE`, not PASS; that happens on about 7% of real writes, and reporting those as verified would be the same mistake this tool exists to catch.

## Transformation view (experimental)

`factwash.inspect()` re-reports the same checks as typed source-to-output changes, the first step toward a general source-to-output integrity tool:

```python
report = factwash.inspect(
    "According to Jason, Alice may have access to the test server until Friday.",
    "Alice has server access.",
)
# verdict: DRIFTED
#   DROPPED       attribution      FAIL
#   STRENGTHENED  certainty        FAIL
#   DROPPED       temporal scope   WARN
#   not checked: ADDED, BROADENED, WEAKENED
```

Verdicts are `PRESERVED | DRIFTED | UNCHECKABLE`, and `UNCHECKABLE` is never `PRESERVED`. Same checks, same evidence, same policy as `factwash.check()`; nothing is re-decided. Change types with no detector yet (`ADDED`, `BROADENED`, `WEAKENED`) are declared in `not_checked` on every report rather than silently absent. Only `kind="memory_write"` is implemented; other kinds raise.

With `factwash[units]` installed, the layer also catches unit drift on values that survived, which the seven gate checks structurally cannot see:

```python
factwash.inspect("Q3 spend was 1.2 million dollars.", "Q3 spend reached 1.2 million euros.")
# verdict: DRIFTED   (gate: PASS)
#   CHANGED  unit  FAIL   source '1.2 million dollars' became '1.2 million euros'
```

`5 mg` stored as bare `5` is a DROPPED-unit warn. A quantity that vanished entirely is deliberately out of scope (that is brittle/truncated territory); the detector is value-keyed so ordinary compression does not trip it. Without the extra, unit checking is listed in `not_checked` instead of silently narrowing coverage.

### The ADDED detector (opt-in witness)

The seven checks ask whether what was in the source survived. ADDED asks the opposite
direction: whether what is in the memory was ever there. On the blind labelled corpus,
27 of 29 bad writes were wrong, invented or inferred claims, which is this detector's
territory, not the gate's:

```python
from factwash import anthropic_added_witness
report = factwash.inspect(source, memory, added_backend=anthropic_added_witness())
#   ADDED  unsupported claim  FAIL
#     'Lynn approved the report.' has no support in the source
#     (closest source text: 'Mike asked about the report')
```

Same constitution as the stance witness: the model answers a three-way question
(supported / unsupported / cannot_tell) about one memory sentence against the source,
judging only the provided text. Every answer must quote the source verbatim:
"supported" cites its supporting words, and "unsupported" must cite the *closest* words
the source has on the topic, proving it read the source before claiming absence. A
reply that cannot point is discarded, and sentences the backend could not establish are
declared on the report (`ADDED on 2 of 5 sentences (backend could not establish)`),
never silently passed. The backend is any callable `(source, claim) -> dict`, so it is
provider-agnostic and testable offline; without one, `ADDED` stays in `not_checked`.

Measured on the blind-labelled corpus (write-level, 27 fabricated/inferred positives vs
65 clean negatives, single-labeller gold): **precision 0.57** (8 of 14 flagged writes
correct), **recall 0.30** (8 of 27 targets found), sentence coverage 96.9% (95 of 98).
Those denominators are small enough that the 95% intervals are roughly [0.33, 0.79] and
[0.16, 0.48]; the point estimates are not precise to three decimals and are not reported
that way. Read it with the same honesty as every other number here: the gate
catches 0% of this failure class by construction, so 30% recall at usable precision is
strictly additive, and the prompt was not tuned against this corpus, because fitting
the visible corpus is the original sin this project documents. The first run also
caught its own bug: verbatim quote validation rejected 39 of 46 honest replies over
email line-wrapping and curly apostrophes (coverage 54%), fixed by normalizing
whitespace in validation only, coverage now 96.9%. Reproduce:
`python experiments/added_eval.py` (~$0.04).

### Multi-hop drift

Memories get rewritten repeatedly, and a single-pair check cannot say where in the
chain the stance was lost. `factwash.drift(versions)` traces a memory's version history
and attributes every end-to-end change to the hop where it happened:

```
drift across 5 versions (4 hops)
  hop  1  PRESERVED   (gate: PASS)
  hop  2  PRESERVED   (gate: PASS)
  hop  3  DRIFTED     (gate: PASS_WITH_FLAGS) DROPPED temporal scope
  hop  4  DRIFTED     (gate: REWRITE)         DROPPED attribution, STRENGTHENED certainty
  end-to-end  DRIFTED (gate: REWRITE)
      STRENGTHENED  certainty        <- hop 4
      DROPPED       attribution      <- hop 4
      DROPPED       temporal scope   <- hop 3
```

Two measured properties, pinned by tests: within lexicon and alignment coverage **the
gate composes** (the first hop that drops a cue class's last cue fires, so an
in-lexicon chain cannot launder gradually past a per-write gate), and chains escape by
**decaying alignment instead**: successive paraphrase turns hops UNCHECKABLE, so a
chain that loses checkability is reported loudly (`CHECKABILITY LOST at hop 2`), never
as "no findings".

### Structured memories: check the field, not the prose

If a memory system stores records rather than sentences, `factwash.check_record()`
compares the record's retention fields against the source, with no model and no lexicon
of hedged phrasings on the memory side:

```python
factwash.check_record(
    "Probably the API rate limit is 500 a minute; I'm going from memory here.",
    "CLAIM: API rate limit ~500 req/min
SOURCE: the user
CERTAINTY: asserted
AS_OF: unspecified")
# REWRITE  MANUFACTURED_CONFIDENCE: source hedges ['probably'] but the record
#          certifies it as 'asserted'
```

The rule is one line per field: if the source hedges, `CERTAINTY` may not say
`asserted`; if the source names a speaker, `SOURCE` may not be empty; if the source
dates it, `AS_OF` may not be empty. A record missing its retention fields is
`MALFORMED`, never `PASS`, for the same reason `UNCHECKABLE` is never a pass.

**Why this exists, measured.** Making the scratchpad structural more than doubled the
share of writes that survived compression cleanly (3/10 to 7/10 on the `hearsay-v1`
stimuli). But a structured *memory* scored worse under the prose gate than a prose one,
and the reason was the measuring instrument: `CERTAINTY: hedged` preserves the source's
stance perfectly and contains no word a hedge lexicon knows. The record is more
machine-readable, not less. It just has to be read as a record.

## Benchmark: score your memory system

`factwash bench` turns the gate into a scorer: feed it the `{source, memory}` pairs your
memory system produced and get its **laundering rate**, the share of checkable writes
that dropped the stance or basis of what the source said.

```bash
factwash bench writes.jsonl --stimuli-id my-stimuli-v1
factwash bench --adapter mem0 --sources stimuli.txt   # drive a live mem0 store (network + cost)
```

```
factwash bench (gate v0.4.0, stimuli: calib-planted)
  writes: 12   checkable: 12   uncheckable: 0 (reported, never in the denominator)
  laundering FLAG rate: 100%  (12 of 12 checkable writes REWRITE or REJECT)
  verdicts: REJECT 5  REWRITE 7
  mechanisms: BRITTLE 5, TRUNCATED 5, MANUFACTURED_CONFIDENCE 4, LAUNDERED 4, ...
```

**First real row: mem0 2.0.7 (haiku extraction), stimulus set `hearsay-v1`.**

| Stimuli | Writes | Laundering flag rate | Mechanisms |
|---|---|---|---|
| 10 hedged-hearsay sources | 8 | **62%** (5 of 8) | LAUNDERED 4, MANUFACTURED_CONFIDENCE 2 |
| 5 confident-legit controls | 5 | 20% (1 of 5) | LAUNDERED 1 |

Reproduce with `python experiments/mem0_bench_row.py` (~$0.05, local embeddings, real
mem0 extraction). Denominators are small (8 and 5 writes), so read these as one run of
one configuration: the 95% interval on 5-of-8 runs from roughly 31% to 86%. What the run
showed, in order of how much it should worry you:

- **The laundering is not subtle.** "Rumor has it Alice now has admin access after the
  reorg" was stored as *"Alice was promoted to admin around late July or early August
  2026 and now has admin access"*: the hearsay is gone, and a date that never existed
  has appeared.
- **The one flag on the legit controls is the known false positive**, reproducing in
  the wild: "Per the IAM system of record" trips the ported `record` cue (see
  Limitations). The other four confident sources passed clean.
- **Two sources produced no write at all.** mem0 declined to store "Word is that Dana is
  leaving" and "Probably the API rate limit is 500 requests a minute", which is the
  safest possible outcome and is why the denominator is 8 rather than 10. Abstention is
  reported, never scored as a pass.
- **Running ADDED over the same 13 writes flags 8**, but the honest split is the useful
  part: **5 are timestamp resolution** ("yesterday" → "August 3, 2026"), which is
  defensible enrichment rather than invention; **2 are genuine fabrication**, where the
  source carried no time reference at all and mem0 produced one anyway; **1 is an
  attribution shift** ("Reportedly" → "User reports"). So the ADDED detector's dominant
  false-positive class on a real memory system is date resolution, which is a
  calibration fact worth knowing before anyone gates on it.

The flag rate is reported **beside the uncheckable and abstention rates**, because the
score alone is gameable: a system whose writes cannot be aligned to their sources, or
that stores little, offers fewer chances to be flagged, so a low flag rate can be evasion
rather than cleanliness. Other rules the report enforces, pinned by tests: the number is
a **flag rate, not a verified laundering count, and it errs in both directions**
(bounded recall hides laundering, so a zero is never an acquittal; ~1 flag in 4 is a
false alarm on real output, so it is not a floor either); `UNCHECKABLE`
writes are reported and never folded into the denominator; and scores are only
comparable across runs on the **same stimulus set**, because laundering base rates are
stimulus-dependent. The bench reproduces the calibration corpora exactly (planted
12/12, clean 1/13). MemGPT traces become a pairs file via
`experiments/external/eval_memgpt.py`; any system that can dump its writes can be
scored.

## CLI

```bash
factwash check --source session.txt --memory note.txt   # exit: 0 pass, 1 rewrite, 2 reject, 3 uncheckable
factwash check --source session.txt --memory note.txt --fix
factwash audit ./memories/                              # surface scan, deliberately weaker
```

`audit` says in its own output that it is a surface scan: all seven checks need the source, and a store that has already dropped it cannot be checked properly. That is the whole thesis, applied to the tool itself.

## Try it in the browser

`demo/index.html` runs the gate client-side: paste a source and a memory, get the verdict, flags, and the hedge/attribution tokens marked inline. Presets are verbatim output from paid runs, including one where the gate correctly stays quiet. The JS port is held to the Python gate by `test_port_parity.py` over 170 pairs; sabotaging one threshold makes it report 47 disagreements, so the parity test is known to fire, not merely known to pass.

The end-to-end demo at the top of this README is `python experiments/demo_side_by_side.py` (~$0.02, embeddings local, nothing stubbed). Extraction is sampled, so phrasing changes the outcome; the stimulus shown was chosen because it laundered in the measured runs, not because it reads well. Note `MEM0_TELEMETRY` defaults to on in mem0 2.0.7; the demo disables it.

## The numbers

Every figure below is recomputed from the shipped corpora and asserted against this file by `tests/test_published_numbers.py` (negative-tested: break a lexicon term and it names the drift). It exists because these numbers drifted twice without anyone noticing.

Headline, on **44 hand-labelled memory writes produced by a real extractor** (`tests/fixtures/live_labels.json`):

| | Recall | Precision | Cost |
|---|---|---|---|
| Deterministic gate alone | **95%** (19 of 20) | 73% | $0 |
| With a one-question LLM veto | 85% | **94%** (1 false positive) | ~1¢ per 100 writes |

**Against corpora nobody here wrote.** Self-built data flattered this tool four separate times, so the detectors are also scored on 105,596 sentences annotated by other people before this project existed: [BioScope](https://rgai.inf.u-szeged.hu/node/105), the [Szeged Uncertainty Corpus](https://rgai.inf.u-szeged.hu/node/160), and [PolNeAR](https://github.com/networkdynamics/PolNeAR). Terms were mined from dev; these are test numbers (`experiments/external/`, free, offline):

| Detector | Precision | Recall | F1 | Class |
|---|---|---|---|---|
| Negation (`POLARITY_CHANGED`) | 0.89 | 0.94 | **0.91** | closed |
| Hedges (`MANUFACTURED_CONFIDENCE`) | 0.89 | 0.66 | 0.76 | open |
| Attribution (`LAUNDERED`) | 0.91 | 0.49 | 0.63 | open |
| Conditionals (`CONDITION_DROPPED`) | 0.61 | 0.67 | 0.64 | closed |

This is the design claim in `lexicons.py`, externally confirmed: the closed-class detector generalises (0.91 F1 on domains it was never tuned on) and the open-class ones plateau near half recall, because English does not have a finite list of ways to hedge or attribute. That plateau is the entire argument for the witness, and the head-to-head on the same external gold backs it:

| Task | | Precision | Recall | F1 |
|---|---|---|---|---|
| Hedges | lexicon | 0.97 | 0.62 | 0.76 |
| | **witness** | 0.96 | **0.79** | **0.87** |
| Attribution | lexicon | 0.85 | 0.45 | 0.59 |
| | **witness** | 0.87 | **0.60** | **0.71** |

+17 and +15 points of recall at equal precision, on exactly the two open classes. Unusable replies are counted as misses, because that is how the shipped gate treats them. Cost: $0.157 for all 400 calls on haiku-4.5.

**Versus the obvious baseline: a direct LLM judge.** Same rubric the human labeller
used, same labels, same pairs (`experiments/judge_baseline.py`, ~$0.05):

| Set | Detector | Precision | Recall |
|---|---|---|---|
| Real writes (44, 20 pos.) | gate | 0.73 | **0.95** |
| | LLM judge (small) | 1.00 | 0.30 |
| | LLM judge (large) | 0.91 | 0.50 |
| Adversarial (46, 26 pos.) | gate | 1.00 | 0.58 |
| | LLM judge (small) | 1.00 | **0.92** |

The judge nearly doubles the gate's recall on unfamiliar phrasing and collapses on real
extractor output, missing 14 of 20 flagged writes. Its own explanations say why: the
misses read *"the memory accurately captures the core fact"* — asked whether a memory
misleads, the judge checks whether the **claim** survived, finds it did, and passes.
That is the failure this tool is named after, performed by the detector asked to catch
it. Two caveats: this is one rubric and two models, so it bounds the naive baseline
rather than every possible judge; and the judge volunteered a source-grounded quote on
89 of 90 items, so the case for validating evidence is that verdicts must be *required*
to cite text, not that models can't.

**Prompt or model? A 2x2 on the same 15 items:**

| Model | Extraction prompt | Attribution stripped | Hedge stripped | Abstained |
|---|---|---|---|---|
| haiku-4.5 | naive "extract durable facts" | 6 of 9 | 2 of 9 | 0 |
| haiku-4.5 | mem0's own ~7,800-token prompt | 5 of 8 | 1 of 8 | 2 |
| sonnet-5 | naive "extract durable facts" | 7 of 10 | 2 of 10 | 0 |
| sonnet-5 | mem0's own ~7,800-token prompt | 3 of 6 | 1 of 6 | 3 |

The prompt matters; the model mostly does not, and attribution-stripping never drops below half in any cell. n is small and the corpus hand-written, so directional rather than precise. One finding worth carrying: prevention beats detection. A `HEDGEKEEP` line in the extraction prompt stops laundering before it happens; detection is the hard, bounded half.

**Calibration fixtures** (bounds the heuristics on short memories, nothing more):

| Corpus | Items | Result |
|---|---|---|
| Planted failures, the original four checks | 12 | 12/12 detected |
| Clean memories | 13 | 1/13 false positives |

These plant failures for the original four checks only; the three later checks are exercised in `tests/test_core/`, against the external corpora, and against the 89-item should-pass corpus that bounds their false-positive rates.

## What it does not catch

Tested adversarially, and this bounds the product:

| | Result |
|---|---|
| Precision on confident memories containing domain uses of lexicon words (`insurance claim`, `database record`, `reported revenue`) | **20 of 20** |
| Recall against phrasing outside the lexicon, held-out set | **4 of 14 (29%)** |

The checks ask "was there a hedge or attribution token in the source that is missing from the memory". If the source's phrasing is not in the lexicon, no flag is possible by construction: "overheard in the kitchen", "scuttlebutt", "my sense is" all sail through. Adding vocabulary was measured, not assumed, to not fix this: forty new terms took recall on the visible corpus from 25% to 92% and left a corpus written afterwards at 14%. The lexicon memorises; it does not generalise. External mining moved the held-out number 14% to 29%, two cases in three rounds, and the remaining misses need semantics, not vocabulary.

The shipped witness cannot fix it either: it only downgrades, so it buys precision, not coverage. And escalate mode (a witness allowed to raise verdicts) is a measured negative, not an open idea: 93% recall on the adversarial corpus, and on the 44 real writes zero recall gained, seven points of precision lost, all three raised verdicts wrong (`experiments/escalate_precision.py`, under a cent). The writes the deterministic layer leaves behind are precisely the ones a model gets wrong.

So: high precision, bounded recall. Worth installing when a false alarm costs more than a miss. Not worth it if you need blanket coverage.

## Limitations

- **English-only, substring-matched, gameable by paraphrase.**
- **Claim-local checks.** Blob-level testing fails on real output ("I've noted the following" shields the claim beneath it); the trade-off is that a hedge one clause away from its claim can be missed. Windows differ per check on purpose: hedging floats across sentence boundaries, negation and attribution attach to their clause. Measured on FRANK, pinned in `tests/test_core/test_window_scope.py`.
- **`record` and `note` over-match** ("system of record"). The ported lexicon is kept verbatim rather than quietly edited; this is the single calibration false positive.
- **`BRITTLE`/`TRUNCATED` fire only on numeric derivations** carrying an aggregate cue.
- **Scope broadening is not attempted.** "test server" stored as "server" needs ontology: the obvious modifier-drop signal fired on 86 of 89 should-pass items when tried, because ordinary compression drops modifiers constantly. A test pins the negative result so nobody closes it with a heuristic that flags all summarising.
- **No supersession.** A transcript is one flat source, so a claim retracted later in the same session still counts as asserted. Found on a real MemGPT trace; recorded, not fixed.
- **Only one polarity direction.** A memory that gains a negation is usually the extractor adding a caveat, which is wanted; flagging both directions measured worse.
- **No external user has yet run this against a store the author did not construct.**

## Reproducing

```bash
pytest                                                             # full suite, offline, no key
python demo/build.py                                               # rebuild the browser demo
python experiments/live_run.py --dry-run --model dryrun --budget 0 # $0, full pipeline
```

Paid runs are metered, resumable, and capped: every item is flushed and fsynced before the next call, resume skips paid items, and a call that would breach `--budget` is refused. Each guarantee has a test that breaks it on purpose, including a simulated SIGKILL mid-write. Outputs follow `data/raw/YYYYMMDD_HHMMSS_<op>_<model>_<params>_s<seed>.jsonl`, and every summary names which of its own numbers are circular. Total API spend for every experiment in this repo: $1.02.

Measurement history, including the fourteen corrections behind these numbers (ten of which had made the tool look better than it was) lives in [CHANGELOG.md](CHANGELOG.md) and the experiment scripts; the external-corpus tuning rule and every rejected candidate are recorded in `experiments/external/tune_lexicon.py`.

## Citing

If you use factwash, cite the preprint (see [CITATION.cff](CITATION.cff); the arXiv
identifier will be added once assigned):

```bibtex
@article{kwon2026factwash,
  title  = {factwash: Catching AI Rewrites That Wash Hearsay into Fact},
  author = {Kwon, Alex},
  year   = {2026},
  note   = {Preprint}
}
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: N/A is never a pass, every
published number is asserted by a test, and new checks ship with the test that breaks
them on purpose.

## License

[Apache-2.0](LICENSE)
