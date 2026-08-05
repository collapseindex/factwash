# Changelog

### Unreleased (2026-08-05)

Research for a second paper (`writeup2/`), not a library change. No public API moved and
no shipped behaviour changed; everything here is harness, corpora and analysis.

- **Two-cell format experiment.** `experiments/two_cell_pressure.py` compares matched
  notes that carry the identical claim and identical stance and differ only in how the
  stance is written, under six budget levels, scored by a blind reader that never sees the
  condition. Selectable claim corpora (`experiments/claims_corpus.py`): the original ten,
  fifty more across seven registers, and a held-out sixty written for a pre-registered
  replication (`claims_corpus_v3.py`).
- **Format ablation.** `experiments/ablation_form.py` separates labels, bracketing,
  wording and length across six forms. Run on two models, which is how we learned the
  decomposition does not transfer: the same net effect is assembled from different
  components on Haiku and Sonnet, and only labels and length behave the same way on both.
- **Pre-registration.** `writeup2/PREREGISTRATION.md` was committed, with the prediction
  and the decision rule, before any API call touched the held-out corpus.
  `experiments/prereg_score.py` applies that rule mechanically rather than letting the
  verdict be chosen after seeing the number. It replicated.
- **A readout with no model in it.** `experiments/mechanical_readout.py` re-scores the
  same stored memories with this repository's deterministic gate, as a check on outcomes
  that otherwise come entirely from model judges. It agrees on direction on both models
  while being biased *against* the arm it agrees about.
- **Harness hardening.** `--max-usd` enforced against measured tokens, with unknown model
  rates priced at an expensive fallback so the cap fails safe; a capped run now writes its
  summary instead of dying with its cost record (the runs that spent the most were the
  ones recording nothing); a temperature fallback for models that reject the parameter,
  recorded in the summary rather than smoothed over.
- **Corrections, all found by controls rather than by reading the code.** A judge parser
  that discarded ~6% of verdicts non-randomly, on the clearest positives, inflating an
  effect twofold. Pair-level inference where the unit that generalises is the claim. A
  ten-claim corpus that manufactured both a false null and a false model-family split. A
  corpus tagger that filed the held-out replication under the wrong corpus, which the
  paper gate caught in both of its wrong states.
- `experiments/total_spend.py` sums metered spend across every run. Currently $16.82
  nominal for the repository, of which $1.02 belongs to the experiments behind the
  published paper.


### v0.5.0 (2026-08-04)

Stance as a field. The morning's three probes found the leak is at recording, that
repairing prose does not survive compression, and that a schema does.

- **Stance as a field: `factwash.check_record()`.** Three probes this morning converged
  on one design. (1) The leak is at RECORDING, not compression: the gate flags 9/10
  source-to-note pairs and 1/10 note-to-compressed. (2) Gating the note and repairing it
  is a clean null end to end (0 recovered, 0 broken), because the repair writes the hedge
  as a parenthetical and the compressor strips it; stance written as a labelled field
  survived 3/4, as a parenthetical 0/4. (3) So make it a field: a four-field stance
  schema at the note step took clean writes from 3/10 to 7/10 on the same stimuli.
  The new checker compares a record's retention fields to the source with no model and
  no hedge lexicon on the memory side, and reports MALFORMED (never PASS) when the
  retention fields are absent. It exists because the prose gate scored a schema memory
  WORSE than a prose one: "CERTAINTY: hedged" carries the stance perfectly and contains
  no word a hedge lexicon knows, which is a fact about the instrument, not the record.
  Also fixes a parser bug found by its own test: `- **CERTAINTY**: rumor` silently lost
  the field because markdown was stripped from one end of the key only.

- **The LLM-judge baseline, run and reported: the judge commits the failure it is asked
  to detect.** Every reader asks why not just hand the pair to a model, and the paper
  only answered architecturally. Now measured (`experiments/judge_baseline.py`, ~$0.05,
  same rubric the human labeller used, same labels): on adversarial phrasing the judge
  nearly doubles the gate's recall (0.92 vs 0.58), which is the open-class result by
  another route; on 44 real extractor writes it inverts, 0.30 recall (small model) and
  0.50 (large) against the gate's 0.95, at higher precision. The reason is in its own
  explanations, which say "the memory accurately captures the core fact": asked whether
  a memory misleads, it checks whether the CLAIM survived, finds it did, and passes.
  Pre-registered before spending: any outcome went in, including the one where the judge
  wins. Two caveats stated with the result: one rubric and two models, so it bounds the
  naive baseline; and the judge volunteered a source-grounded quote on 89 of 90 items,
  so the evidence argument is that verdicts must be REQUIRED to cite text, not that
  models cannot. Claims ledger gained a NOT CLAIMED row for the latter.

- **The bench was gameable, and now reports the vector that shows it.** Excluding
  UNCHECKABLE from the denominator meant a heavily abstractive system could evade
  alignment, contribute fewer flaggable writes, and score *cleaner* for being harder to
  check. (The drift work proved the mechanism: paraphrase chains escape by going
  UNCHECKABLE, not by passing.) `BenchResult` now reports `uncheckable_rate` and
  `abstention_rate` beside the flag rate, `run_adapter` counts sources the system stored
  nothing for, and a caveat names the incentive. Tests pin the vector and the caveat.
  Credit: third-party review.
- **The class rule is stated as a cue-inventory claim, not a claim about English.**
  "Negation is a closed class" overreaches: semantic negation also surfaces through
  *lack*, *fail to*, *without*, antonyms and pragmatic denial, none of which an
  explicit-cue list catches. What the corpora annotate is cues, so the demonstrated claim
  is that explicit negation cues are substantially more enumerable than hedge and
  attribution realizations. Abstract and Limitations rewritten accordingly.
- **One table for every evaluation set** (new Appendix B), because the paper reports a
  0.73 precision and a 0.34 precision from different corpora and never said so at point
  of use. Each set now appears once with its size, what it measures, and what it cannot.

- **Overclaim audit: four corrections, one of them in the tool's own output.** (1) The
  bench called its number a LOWER BOUND, which is one-sided and flattering to anyone
  using it to indict a system: bounded recall pushes the rate down, but imperfect
  precision (~1 flag in 4 is a false alarm on real output) pushes it up. It is now
  reported as a FLAG RATE that errs both ways, in the render, the caveats, the JSON key
  (`laundering_flag_rate`), the README and the paper; a test asserts the two-sided
  framing. (2) ADDED was reported as precision 0.571 / recall 0.296, three decimals from
  denominators of 14 and 27; now 0.57 (8/14) and 0.30 (8/27) with the 95% intervals
  ([0.33, 0.79], [0.16, 0.48]). (3) The paper's abstract stated a bare "62% laundering";
  it now says the gate flags 5 of 8, and the body carries the interval [0.31, 0.86].
  (4) Multi-hop composition was stated as a property of the gate; it is now scoped to
  the three chains it was probed on, with the generalisation explicitly marked as not a
  proof. The claims ledger gained a NOT CLAIMED row for "that is mem0's laundering rate".

- **First real leaderboard row: mem0 2.0.7 launders 62% of hedged-hearsay writes.**
  `experiments/mem0_bench_row.py` drives a real mem0.Memory (its own extraction LLM,
  local embeddings, local store) over the shipped 15-source `hearsay-v1` stimuli and
  scores hearsay and legit controls as SEPARATE runs, because averaging them would bury
  the base-rate lesson. Hearsay: 62% (5 of 8 writes; two sources produced no write at
  all, which is the safest outcome and why the denominator is 8). Legit controls: one
  flag out of five, and it is the documented `record` over-match ("Per the IAM system
  of record") reproducing in the wild rather than a new defect. The stored text is the
  demo: "Rumor has it Alice now has admin access" became "Alice was promoted to admin
  around late July or early August 2026 and now has admin access".
- **ADDED over the same real writes: 8 of 13 flagged, and the split is the finding.**
  5 are timestamp resolution ("yesterday" -> "August 3, 2026"), 2 are genuine
  fabrication (no time reference in the source at all), 1 is an attribution shift
  ("Reportedly" -> "User reports"). The dominant ADDED false-positive class on a real
  memory system is date resolution: a calibration fact anyone gating on ADDED needs,
  and it is stated rather than absorbed into a headline number.

- **The ADDED witness, measured live: precision 0.571, recall 0.296, coverage 96.9%**
  (write-level, blind corpus, 27 fabricated/inferred positives vs 65 clean negatives,
  ~$0.04 on haiku, `experiments/added_eval.py`: streamed, fsynced, resumable,
  call-capped). Strictly additive: the gate catches 0% of this class by construction.
  Not tuned against this corpus, deliberately. The first run measured coverage 54%
  and an instrumented rerun attributed 39 of 46 dead replies to one mechanical bug:
  verbatim quote validation rejected honest quotes over email line-wrapping and curly
  apostrophes. Fixed by normalizing whitespace/apostrophes in validation only (words
  in order still required; fabricated quotes still die, regression-tested); coverage
  went to 96.9% and the numbers above are the post-fix run. Both run summaries are
  committed under data/results/.

- **The ADDED detector: the opposite direction, completing the quadrant.** The gate
  asks whether what was in the source survived; `added_backend` on
  `factwash.inspect()` asks whether what is in the memory was ever there, which is
  where 27 of 29 bad writes on the blind corpus lived. Same constitution as the stance
  witness, adapted for the comparative question: three-way verdict per memory sentence
  (supported / unsupported / cannot_tell, the RefChecker entailment discipline: judge
  the provided text, never world knowledge); "supported" must quote its supporting
  source words and "unsupported" must quote the CLOSEST source words on the topic,
  proving the model read the source before claiming absence; quotes are validated
  verbatim and a reply that cannot point produces nothing. Sentences the backend could
  not establish are counted and declared on the report. `anthropic_added_witness()`
  ships as the default backend (opt-in, one call per sentence); any callable with the
  contract works, so the wiring is fully tested offline. The prompt contains no example
  claims, for the same fake-100% reason the stance prompt contains no example idioms.

- **Multi-hop drift: hop-attributed laundering across rewrite chains.**
  `factwash.drift(versions)` runs the transformation view over every adjacent pair and
  the ends, then attributes each end-to-end change to the first hop that shows it. Two
  properties were measured by probe before the module was written and are pinned as
  tests: (1) the gate COMPOSES within lexicon+alignment coverage: the hop that drops a
  class's last cue fires, so in-lexicon chains cannot launder gradually past per-write
  gating (the `gradual` flag is computed, not assumed, and its logic is tested both
  ways); (2) paraphrase chains escape by losing CHECKABILITY, not by passing: hops go
  UNCHECKABLE and the report says so loudly. A prediction made during design was also
  corrected by measurement: class-straddling cues ('reportedly' = hedge + attribution)
  DELAY a loss to the hop that drops them rather than hiding it end-to-end; the
  unattributed-change path exists for alignment-divergence cases and is unit-tested.

- **factwash bench: the gate as a scorer.** `factwash bench pairs.jsonl` scores the
  (source, memory) pairs a memory system produced and reports its laundering rate:
  REWRITE+REJECT over checkable writes, with the mechanism profile alongside. Three
  honesty rules are pinned by tests: the rate is a LOWER BOUND (bounded adversarial
  recall means a zero is not an acquittal), UNCHECKABLE is reported and never in the
  denominator (0/0 reports n/a, not 0.0), and reports carry a stimulus-set id because
  base rates are stimulus-dependent and cross-set comparison is a category error. A
  mem0 adapter drives a live store (add, capture, delete; the bench itself stays
  deterministic and offline), adapter failures are counted and declared, and the bench
  reproduces the shipped calibration corpora exactly (planted 12/12, clean 1/13) as its
  own regression test. Also fixed `__version__` still reading 0.3.0 after the v0.4.0
  cut; the release shipped with a stale package version and nothing caught it, so
  `test_version_matches_pyproject` now does.

- **Embedding-based alignment: measured, and declined.** The proposal (swap content-word
  overlap for embedding sentence alignment, "probably buys more real-world recall than
  anything") was tested before being built: `experiments/align_diagnostic.py` attributes
  every known miss to either the aligner (no source sentence matched, so no detector
  ever ran) or the detectors (right sentence compared, lexicon lacks the phrasing).
  Result: of 11 adversarial evasion misses plus 1 bad-labelled UNCHECKABLE, **10 are
  detector losses the aligner delivered correctly** ('overheard', 'scuttlebutt', 'my
  sense is'...), 1 is the paraphrase item constructed specifically to defeat substring
  matching, and 1 is an out-of-scope inferred claim no aligner can reach. An embedding
  aligner would recover at most 1 of 12 known losses. The recall ceiling is an
  open-class lexicon fact, not an alignment fact; the paper's "the remaining misses
  need semantics, not vocabulary" survives an attack on its own infrastructure. The
  diagnostic self-checks (a planted paraphrase must classify ALIGNMENT, a planted
  covered case must still flag) and refuses to report otherwise. n is small (12),
  stated plainly.

### v0.4.0 (2026-08-03)

The broadening release: the memory gate grows a transformation view, gets renamed
after the failure mode it detects, and goes Apache-2.0.

- **Renamed TWSS -> factwash.** The old name was an in-joke that needed explaining; the
  new one is the failure mode, so the name answers "what does this do" by itself. Package,
  CLI, env var (`FACTWASH_TEST_MEM0`), paper `\sys` macro and repo all renamed together;
  "That's What Source Said" stays in the README as the expansion of record. PyPI `twss`
  was squatted anyway; `factwash` is free.
- **Transformation view, the first step out of memory-only.** `factwash.inspect(source,
  output)` re-reports the same seven checks as typed changes (DROPPED attribution,
  STRENGTHENED certainty, REVERSED polarity, ...) with verdicts PRESERVED | DRIFTED |
  UNCHECKABLE. Nothing is re-decided: one mapping table over the gate's flags, and a
  parity test pins the mapping to the exact set of checks `core.check` runs so a renamed
  check cannot silently drop out. Change types with no detector yet (ADDED, BROADENED,
  WEAKENED) are declared `not_checked` on every report, because a report that only lists
  what it found reads as "nothing else happened". Only `kind="memory_write"` is
  implemented; other kinds raise.
- **RefChecker fork evaluated and declined, with evidence.** The portable core is 1,537
  lines; its pyproject makes torch, transformers, pytorch_lightning and boto3 mandatory
  (violates this package's zero-dependency default), and the provider SDKs are pinned at
  pre-1.0 anthropic / 2024 litellm, so every call site needs rewriting under either
  strategy. Port targets recorded in `refchecker_port_verdict.md`: the claim-decomposition
  prompt criteria, the sentence-ID evidence-localization mechanism, and the
  Entailment/Neutral/Contradiction discipline, all for the future ADDED detector.
- **Units detector, the first check the gate cannot express.** `factwash[units]` (quantulum3,
  two pure-Python deps) adds value-keyed unit drift to the transformation view: same value
  with a different unit is CHANGED/fail ('1.2 million dollars' -> '1.2 million euros',
  which the gate PASSES), a real unit stored as a bare number is DROPPED/warn. A quantity
  that vanished entirely is deliberately out of scope (brittle/truncated territory;
  firing on ordinary compression is the modifier-loss mistake, measured at 86/89 false
  fires in the paper). Lives in the transform layer only, so the gate stays the paper's
  seven checks. Without the extra, unit checking appears in `not_checked`.
- **Torch-backed ADDED detectors cut from the roadmap** (keep-it-light call): the future
  ADDED path is the existing witness pattern first; MiniCheck/LettuceDetect remain
  documented options in `backend_survey.md` if local models are ever wanted.
- **Stress pass on the transform layer: two real defects, both fixed and pinned.**
  (1) quantulum3 crashed on ambiguous units in any environment where sklearn is present
  but `stemming` is not, taking `inspect()` down with it; the detector now forces the
  heuristic path (`classifier.USE_CLF = False`, which also keeps ML out of the decision
  path) and any parser failure degrades to a declared `not_checked` entry instead of an
  exception. (2) '5 minutes' -> '5 min' false-fired CHANGED because the heuristic
  disambiguator resolves 'minutes' to minute-of-arc (angle) and 'min' to time; CHANGED
  now requires the same entity on both sides, trading a rare real cross-entity rewrite
  (documented FN) for killing the whole class of disambiguation-noise FPs. Probes: 225
  weird pairs + 300 fuzz pairs crash-free, 0/10 FP corpus, 4/4 TP corpus, deterministic
  over 20 runs, 2.1s on 23k chars with units on.
- **Relicensed MIT -> Apache-2.0** (LICENSE, pyproject, NOTICE) ahead of adapting
  Apache-licensed RefChecker prompt patterns. README rewritten product-first; all
  guarded figures intact (`test_published_numbers.py` 8/8) and the stale "128 tests"
  claim removed.
- Fixed the editable install after the repo rename (memlint -> factwash); the six labeller
  integration tests that appeared to fail were `import factwash` dying in the subprocess, not
  test logic.

### v0.3.0 (2026-08-03)

Two measured negatives and one fix, all of them from pushing on the parts that had
never been measured.

- **Escalate mode is dead, and now there is a number for it.** A witness allowed to RAISE
  verdicts hits 93% recall on the held-out adversarial corpus, which is why the README
  called it a pending win. On the 44 hand-labelled real writes: recall 0.95 -> 0.95,
  precision 0.73 -> 0.66. It raised three verdicts and ALL THREE WERE WRONG. Zero recall
  gained, seven points of precision lost, and a call on every write instead of only
  flagged ones. `experiments/escalate_precision.py`, under a cent to reproduce.
  The gap between 93% and this is the gap between a corpus written to defeat a lexicon and
  real extractor output, where the lexicon already catches 95% and the writes left over
  are the ones a witness gets wrong.
- That experiment needed its own ground truth. `stance_tagger.py --mode escalate --corpus
  live` derives "should flag" from the record's `kind`, which is the labelling error this
  repo already corrected once; scoring against it would have reproduced a known-broken
  metric. And it tags the WHOLE transcript, though the witness prompt opens with "You
  label ONE sentence". The new harness uses the hand labels and is claim-local.
- **The harness had a flattering bug of its own, caught by cross-checking a control.** Its
  resume key was `id|memory[:60]`, which collided on two of the 44 pairs and silently
  scored 42. Both dropped items were false positives, so the deterministic baseline came
  out at 0.79 precision instead of 0.73. It was caught only because that baseline is
  pinned elsewhere and the two numbers disagreed.
- **TWSS had no notion of supersession.** A transcript is not a static document: it can
  assert something, deny it, and retract the denial once evidence arrives. Found on a real
  MemGPT trace where the agent says "I don't recall having a dog named Barnaby", searches
  its history, and corrects itself -- POLARITY_CHANGED matched the retracted sentence and
  reported the memory as asserting what the source denied. Locally true, globally wrong.
  `_superseded` now suppresses a polarity flag when a LATER source sentence makes the same
  claim without the negation. Narrow on purpose: it must come after, carry no negation of
  its own, and match the claim at least as well as the denying sentence. That last
  condition exists because the test written alongside it caught the first version letting
  "Bob has admin on the staging cluster" retract a denial about Alice.
- The MemGPT extractor was dropping the write turn's own content, which is the agent's
  inner monologue and the single most relevant piece of source context there is. With it
  included the Barnaby case resolves correctly and for the right reason: no spurious
  polarity flag, MANUFACTURED_CONFIDENCE firing on "appears" from "this appears to
  contradict my core memory", and LAUNDERED noting the fact came from retrieved history.
- Conditionals 0.55 -> 0.61 precision on held-out external text, from narrowings rather
  than additions: "subject to" is usually susceptibility, "assuming" is often a verb
  ("assuming command"), and an "if" meaning "whether" is a complement, not a condition.
- FRANK's clean-sentence flag rate 40% -> 37.5% with the CircE lift up to 1.59, as a side
  effect of the supersession fix.
- The parity test now carries five edge cases the fixture corpora never exercised.
  Supersession shipped in Python first and parity stayed green, because not one of the 165
  fixture pairs contains a retracted denial. 170 pairs now.

### v0.2.0 (2026-08-02)

External validation. Until now every quality number in this repo was measured on data this
project wrote, and that arrangement flattered the fix four separate times. The detectors
are now also scored against ~110,000 sentences annotated by other people, for other
reasons, before this project existed: BioScope, the Szeged Uncertainty Corpus, PolNeAR and
FRANK. All free, all offline, no API key. See `experiments/external/`.

- **The closed-class hypothesis is externally confirmed.** `lexicons.py` argued that
  closed-class detectors should generalise where open-class ones memorise. On held-out
  documents from domains none of it was tuned on: negation 0.91 F1, hedging 0.76,
  attribution 0.63. Both open-class detectors sit at high precision and roughly half
  recall, which is the whole argument for the optional witness. The architecture's central
  claim now rests on someone else's annotation rather than on our own corpus.
- **`LAUNDERED` has an external gold standard for the first time**, via PolNeAR (1,008
  political news articles, token-level source/cue/content, univocal, with the corpus
  authors' own train/dev/test split rather than one we drew). PARC 3.0 is the usual
  reference for attribution but annotates Wall Street Journal text needing a paid LDC
  licence; PolNeAR is free and larger. Attribution scores 0.91 precision, 0.49 recall.
- **Recall up on three of four detectors, all held-out, all at flat precision**: hedges
  0.47 -> 0.66, negation 0.88 -> 0.94, attribution 0.42 -> 0.49. Terms were mined from the
  DEV half under a rule fixed in advance (keep a candidate only if the sentences it newly
  fires on are >=60% gold-annotated and it fires >=10 times). Dev/test gaps are one point
  or less. Conditionals could not be improved at all; every candidate was rejected.
- **Three of those four wins were the same bug in different clothes: the lexicon had
  inflected forms and no stems.** It knew "suggests" and "suggested" but not "suggest",
  "said" and "says" but not "say". Substring matching means a stem covers every
  inflection, which is exactly why the gap was invisible from the inside. This also moved
  the adversarial held-out recall from 14% to 29% -- the first time that number has ever
  shifted -- because "sources say" is in that set and the lexicon finally has "say".
- **`tune_lexicon.py` shipped with a bug for one run, and it is worth recording because it
  failed in the rare direction.** It pooled every corpus, so attribution candidates were
  scored against BioScope and Szeged sentences that carry no attribution annotation at
  all, and every firing there counted as a false positive. Bare "say" came out at 282
  false positives and 0.17 precision when its real cost is 14. Under that bug the tuner
  rejected every negation and every attribution candidate, and an earlier draft of this
  changelog reported "every negation and conditional candidate was rejected" as a
  finding. It was an artefact. A tuner that rejects everything looks admirably strict,
  which is why a deflating bug is harder to notice than a flattering one.
- **Two real defects found by FRANK, neither reachable from any local corpus.**
  `POLARITY_CHANGED` and `LAUNDERED` were reading cues from neighbouring sentences;
  negation and attribution attach to a clause, so a "not" next door does not deny this
  claim. On long-form sources that fired on almost everything. Narrowing those windows is
  free on every local corpus (planted 12/12, clean 1/13, held-out 3/14, live recall 95%
  all byte-identical) and cut external false positives by a third. Hedging genuinely does
  float across sentence boundaries, so its window stays wide: narrowing it loses "Alice
  has admin on prod. Not sure though.", which is the failure this tool exists for. That
  split is measured, and pinned in `tests/test_core/test_window_scope.py` because no
  fixture covered it.
- **The memory-side lexicon had inflected forms and no stems**, so a memory reading
  "german media say" was blocked as laundering while "says" would have passed. Adding
  stems is safe here in a way it would not be on the source side, because this set only
  ever suppresses a flag. Safe is not free: the first draft added "quote", "state",
  "tell", "cite" and "describ" on the same reasoning, and "quote" immediately suppressed a
  planted case whose memory read "Vendor quote: $4,500". A price quote is not quoted
  speech, "real estate" contains "state", and "intelligence" contains "tell". Only the two
  stems with direct external evidence shipped.
- Net on the real task: **precision 68% to 73%, recall unchanged at 95%.** FRANK's flag
  rate on sentences all three annotators called clean fell from 65% to 40%, while the lift
  on circumstance errors, the one category TWSS targets, rose from 1.25 to 1.55. It
  fires less and discriminates better.
- **The redacted corpus is excluded on evidence, not by hand.** BioScope's public clinical
  file has every token replaced with "*", and scoring it produced a clean-looking 0.00
  precision across 6,383 sentences that was a property of the redaction, not of TWSS.
  `REDACTION_GUARD` refuses any corpus that is mostly placeholders, and is negative-tested
  against the file that motivated it (84% against a 25% threshold).
- **`demo/gate.js` lexicons are now actually generated.** The file carried a comment
  saying "GENERATED by demo/build.py, do not hand-edit" above a block that build.py had
  never generated, and it drifted the moment the lexicons changed. build.py now emits it
  from `lexicons.py`, sorted for determinism and idempotent on re-run.
- `lexicons.py` gained `hedges_in`, `negations_in` and friends so that "does the lexicon
  fire on this text" has exactly one definition. The checks call them and so does the
  external evaluation; measuring a reimplementation beside the tool would measure the
  wrong thing.
- What this does **not** show: these corpora contain no memory writes, so none of it
  measures verdict accuracy on the actual task. Held-out adversarial recall moved 14% to
  29%, which is two cases out of fourteen; the remaining gap is not a vocabulary problem.
  Academic and news prose does not hedge the way a person does in conversation.

### v0.1.0 (2026-08-02)

Initial release.

- The four-check write-time gate: BRITTLE, TRUNCATED, MANUFACTURED_CONFIDENCE, LAUNDERED, with a hard-coded verdict policy (PASS / PASS_WITH_FLAGS / REWRITE / REJECT) and N/A as a first-class status.
- Paper-verbatim lexicons (MC App. E) and prompts (Reclaim source-first distiller, MC hedge-preserving extractor), kept separate from TWSS's own extensions for auditability.
- Claim-localization layer (sentences, standalone-number extraction, content-word overlap matching with stance windows): the part the papers did by construction.
- `twss.check()`, `twss.fix()` (optional, `pip install twss[fix]`), `twss.wrap()` store-then-evict gate for mem0-shaped clients.
- CLI: `twss check` (exit codes 0/1/2) and `twss audit` (labeled memory-only surface scan).
- 43 tests: golden (paper examples), negative (lexicons proven load-bearing by breaking them), and two-corpus calibration (planted detection 12/12, clean false positives 0/12).
- The witness ships **inside the package**. It lived in `experiments/`, outside `src/`, so `pip install twss` could not reach the 94% precision the README advertised in its headline table. `twss.check(source, memory, witness=...)` now takes any callable `(sentence) -> {hedged, attributed, markers}`, which keeps it provider-agnostic and testable offline; `twss.witness.anthropic_witness()` is the batteries-included one, and `wrap()` accepts it too. Measured through the shipped API on the 44 labelled real writes: precision 68% to 94%, false positives 9 to 1. It can only lower a verdict, never raise one, and a witness that raises, times out, or answers unusably leaves the deterministic verdict standing.
- `tests/test_published_numbers.py`: every figure in the README is recomputed from the corpora and asserted against the file. This exists because the published numbers drifted twice unnoticed, once on a threshold change and once when the memory-side lexicon was broadened; both times the code improved and the README kept claiming the old result. Negative-tested by falsifying a claim and confirming the test names it. Corrected in the process: precision 70% to 68%, held-out recall 2 of 14 to 3 of 14, and two 2x2 cells.
- `TEMPORAL_SCOPE_DROPPED` (WARN): the source dated a claim and the memory stores it undated, so it will read as current later. Time expressions are a bounded pattern set, unlike hedges, so this half of temporal flattening is deterministic; it raises warnings on 2 of 89 should-pass items. The tense-flip half ("was" becoming "is") is not covered and needs a parser. WARN rather than FAIL because a dropped date is stale-risky, not wrong.
- Measured negative result on scope expansion, and a test to keep it that way. The obvious deterministic signal (a dropped modifier of a retained noun) fires on 86 of 89 should-pass items, because compression drops words constantly. Distinguishing broadening from summarising requires knowing a test server is a kind of server, which is ontology rather than vocabulary. Specified for the witness instead: emit scope qualifiers per sentence, span-validate them, compare sets in Python.
- False positive redefined for calibration as a write that is BLOCKED or ALTERED, not one that is annotated. PASS_WITH_FLAGS stores the memory unchanged, and the live-data precision numbers had always used REWRITE/REJECT as the criterion, so this makes calibration consistent with the measurement rather than the other way round.
- Two new checks, `POLARITY_CHANGED` (REJECT) and `CONDITION_DROPPED` (REWRITE), after testing eight proposed failure modes and catching 0 of 8. A negation dropped between source and memory stores the opposite fact and previously returned a clean PASS, which is worse than any laundering case in the repo. Both use word-boundary regexes rather than the substring matching used for hedges, because "not" is inside "note", "another" and "cannot". Only the dangerous direction is flagged: a memory that gains a negation is usually adding a caveat, and flagging both directions cost 5 false positives on 89 should-pass items versus 1 for one direction. Temporal flattening and scope expansion remain uncaught; they need semantics.
- Span validation on the LLM witness. Every marker it quotes must appear verbatim in the sentence it read, verdict fields must be real booleans, and a positive verdict with nothing to cite is malformed. An ungrounded tag becomes unusable and the caller falls back to the deterministic verdict. A witness that cannot point at the text is guessing, and a guess that reaches the verdict is indistinguishable from an LLM judge. Held-out performance is unchanged at 93%.
- Hand-labelled ground truth for all 49 distinct live (source, memory) pairs (`tests/fixtures/live_labels.json`), which overturned the production numbers. The old measurement labelled every hearsay-sourced item "should flag" regardless of what was stored, but the extractor preserved stance about half the time, so correct passes were scored as misses. Corrected: the lexical gate has 95% recall and 70% precision on real output. Recall was never the weakness.
- Inverted the cascade accordingly (`--mode veto`). The witness now runs only on FLAGGED writes and answers one question about the memory alone -- did this preserve the stance? -- so it can lower a verdict and never raise one. Precision 70% -> 94% (false positives 8 -> 1) for two lost detections and about a cent per hundred writes. The original escalate-on-PASS design was chasing recall that already existed.
- `experiments/stance_tagger.py`: an LLM WITNESS cascade that lifts held-out recall from 14% to 93% with precision unchanged, for ~$0.0016 per gated write. The model labels one sentence at a time for stance and never compares, decides, or returns a verdict; the comparison rule and verdict policy stay in Python, identical to the deterministic path, so the tool does not become another LLM judge. Runs only on PASS/UNCHECKABLE, so anything the lexical layer already flagged costs nothing. Known limit: it short-circuits on a lexical flag and therefore inherits that layer's false positives.
- The witness scored 100% until the prompt was audited. The first version was written while looking at the held-out failures and listed their exact idioms, so it measured the leak rather than the model. Stripping every corpus-specific example from the prompt gave the honest 93%. Same fitting trap as the lexicon, one level up, caught only because the held-out set existed first.
- Adversarial stress test, and the ceiling it measured. Precision is genuinely good: 20 of 20 confident memories containing domain uses of lexicon words ("insurance claim", "database record", "reported revenue") were correctly left alone. Recall is not: against hedge and attribution forms outside the lexicon, the gate catches 2 of 14. Forty added terms moved recall on the visible corpus from 25% to 92% while a corpus written afterwards stayed at 14%, so the lexicon memorizes rather than generalizes. Both figures are asserted at both ends in test_stress.py so the fitted number can never be reported as the honest one. Also fixed two self-inflicted false positives found this way: bare "heard" fired on "I heard the alarm" (perception, not hearsay), and "stated that" missed "states that" (a tense change defeated it). Lexicons are now asymmetric -- precise on the source side, broad on the memory side -- because a false positive costs more than a miss here.
- Closed the four gaps a measured audit surfaced. (1) `UNCHECKABLE` is now a verdict: when no check applies, the gate says so instead of returning PASS, which affected ~7% of real writes and was the flattering direction. (2) `MIN_CONTAINMENT` moved 0.34 to 0.25, swept over 101 real outputs — false positives are flat at 2/34 across 0.20-0.50 while detection falls as the value rises, so the old number cost recall for nothing; the fixtures cannot discriminate it at all, so the sweep is pinned against live data. (3) The mem0 wrapper now gates `UPDATE` as well as `ADD`; assuming only ADD was a version-dependent bet. (4) Established that BRITTLE/TRUNCATED are exercisable on real writes: they applied to 4 of 6 derived-figure memories and passed (mem0 keeps the basis), and fail on the same memory with the basis removed. Re-scoring moved the sonnet-5/naive cell to 8 of 10, which flips a claim: the prompt matters consistently, the model mostly does not.
- `experiments/demo_side_by_side.py`: the end-to-end demo. Two real `mem0.Memory` stores, mem0's own extractor, local fastembed embeddings, and a real access-control agent. Reproduces Manufactured Confidence live (hearsay in, confident dated fact out, unauthorized GRANT) and shows the gate flipping it to ESCALATE. Disables mem0 telemetry, which defaults to on.
- Claim matching now measures overlap against the shorter side, not against the memory. Extraction adds words by design (mem0's prompt asks for "contextually rich" statements), so a real stored claim carries dates and context the source never had; dividing by the memory's length punished exactly that. The demo caught it: a laundered admin claim matched at containment 0.30, fell under the 0.34 threshold, and every check went N/A, so the gate reported PASS while the store took the poisoned write and the agent granted on it. Silent, and in the flattering direction. Re-scoring moved one 2x2 cell (sonnet-5 on the naive prompt, 6 of 10 to 7 of 10); the conclusion is unchanged.
- Completed the model x prompt 2x2 with claude-sonnet-5 ($0.65 total across all live runs). Attribution-stripping never falls below half in any cell; a better prompt and a stronger model each help, and neither fixes it. Hedge-stripping stayed at 1-2 items per cell, far below the paper's 100%. Zero false positives on confident memories across all four cells (0 of 20).
- Three fixes the sonnet-5 runs forced. `max_tokens` now defaults to 1500 and thinking is disabled for the extraction role on think-by-default models: sonnet-5 runs adaptive thinking when `thinking` is omitted, `max_tokens` caps thinking AND visible text together, so the old 200 burned the whole budget reasoning and returned empty text on 8 of 15 items. An empty reply with `stop_reason: max_tokens` now raises rather than being recorded, because the re-scorer would otherwise have counted a truncation artifact as the extractor virtuously abstaining. And the system prompt is now cached (`cache_control: ephemeral`), which cut the sonnet/mem0 cell from $0.3929 to $0.0584 for the same 15 items.
- Cost accounting is cache-aware. With caching on, `usage.input_tokens` is only the uncached remainder; pricing just that field understated spend, and the budget cap is only as honest as the number it is checked against. Cache writes bill at 1.25x and reads at 0.10x of the input rate, and the ledger still reports full prompt size so cached and uncached runs stay comparable.
- Run `20260803_000406_..._mem0-fix_s3` is retained in `data/` for lineage but excluded from the published table: it is the truncated run described above, not data.
- First live run (claude-haiku-4-5, $0.0058, 23 calls) and the three fixes it forced: sentence splitting no longer breaks on `;` (which had cut a correct hedge-preserving rewrite in half and rejected it); checks stay claim-local rather than whole-memory, because real extractor preamble ("I've noted the following", "from your message") contains MC ATTRIB words that shield the bare fact underneath; and non-extractions (the model answering the operator instead of extracting) are named and excluded from the adjusted rates instead of counting as clean. 5 regression tests pin the real model output.
- `experiments/rescore.py`: re-runs the current gate over a finished run's stored (source, memory) pairs at $0. Re-scoring the first run lifted the repair rate from 6/8 to 7/8 on identical stored rewrites, without buying the data twice.
- `experiments/live_run.py` + `experiments/runlog.py`: metered, resumable live runs against a real extractor. Per-item `fsync` to a JSONL ledger, resume-by-item-id so nothing is paid for twice, and a hard budget cap that refuses a call before making it. 11 tests break each guarantee on purpose (torn final line, cap breach, double-pay).
- Calibration updated to 12/12 planted detection and 1/13 clean false positives (8%). The new false positive is real: MC App. E's attribution lexicon contains `record`, which matches "system of record". Found by the live corpus, not the fixtures; kept in the clean corpus and documented rather than patched out of the ported lexicon.
- 3 further opt-in tests (`TWSS_TEST_MEM0=1`) against real mem0 2.0.7: actual `Memory.add()`/`delete()` and a real qdrant store, only the extraction LLM and embedder stubbed. Confirmed mem0's return contract (`{"results": [{"id", "memory", "event": "ADD"}]}`) matches what the wrapper assumed.
