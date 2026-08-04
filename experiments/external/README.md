# External evaluation

Every other number in this repo is measured on data this project built. That arrangement
flattered the fix four separate times, so these scripts measure the detectors against
corpora annotated by other people, for other reasons, before this project existed.

The corpora are not committed (~98 MB, and `data/` is gitignored). Fetch them once:

```bash
python experiments/external/fetch.py        # ~98 MB, five public downloads
python experiments/external/build_corpora.py   # normalise to data/external/normalized/
python experiments/external/eval_lexicons.py   # cue detection vs expert annotation
python experiments/external/eval_frank.py      # the whole gate vs human error labels
python experiments/external/tune_lexicon.py    # candidate terms, scored on DEV only
```

No API key, no network after the fetch, no cost.

## What each corpus is, and what it can and cannot tell us

### BioScope + the Szeged Uncertainty Corpus

Hand-annotated by linguists at HUN-REN-SZTE (Vincze et al. 2008; Szarvas et al. 2012).
57,891 sentences across biomedical abstracts, full papers, Wikipedia, and news, with
speculation and negation cue spans marked inside their scopes.

The Szeged taxonomy is the more useful of the two because its subtypes land on TWSS's
own distinctions instead of cutting across them:

| corpus cue type | TWSS class | scored against |
|---|---|---|
| `speculation_modal_probable_` / `_possible_` | epistemic | `HEDGE` |
| `speculation_hypo_doxastic_` | doxastic | `HEDGE` |
| `speculation_hypo_condition_` | conditional | `CONDITIONAL_PATTERN` |
| `negation` (BioScope) | negation | `NEGATION_PATTERN` |
| `speculation_hypo_investigation_` | investigation | **nothing** — out of scope |

`investigation` marks research framing ("we examined whether X"). That is a real
uncertainty cue in a paper and irrelevant to a memory write, so scoring TWSS against it
would be scoring it on a task it never claimed. Sentences whose *only* cue is
`investigation` are excluded from the hedge score, the count is printed, and the
alternative scoring is printed beside it.

**This measures cue detection, not verdicts.** These corpora contain no memory writes.
Recall here is an upper bound on recall in the gate — a cue TWSS cannot see is a
laundering it can never flag — and nothing more.

**Dev/test.** Documents are split 50/50 by a stable hash (`SPLIT_SEED` in
`build_corpora.py`), so no sentence from a tuned-on document reaches the reported score.
Mine candidates from dev with `tune_lexicon.py`; read the consequence off test.

**The redacted clinical file is excluded on evidence, not by hand.** BioScope's public
`clinical_records_anon.xml` has every token replaced with `*`, and scoring it produced a
clean-looking 0.00 precision across 6,383 sentences that was a property of the redaction.
`REDACTION_GUARD` refuses any corpus that is mostly placeholders.

### PolNeAR

Newell, Margolin et al. 2018 (LREC). 1,008 political news articles from seven publishers
covering the year before the 2016 US election, with attributions annotated token-level and
**univocally**: every token carries at most one of `Source`, `Cue`, `Content`, and belongs
to at most one attribution relation. 47,705 sentences here, 47.9% carrying a cue.

This is `LAUNDERED`'s only external gold standard. PARC 3.0 is the usual reference for
attribution relations, but it annotates Wall Street Journal text from the Penn Treebank,
which needs a paid LDC licence; PolNeAR is free, larger, and annotates the same relation.

**It ships its own train/dev/test split**, which is used as-is. That is strictly better
than the hash split applied to the other corpora, because someone with no stake in
TWSS's numbers drew the line.

BRAT standoff format: a `.ann` of character spans beside a `.txt` article. Offsets are
UTF-8 character offsets and were verified against the text before use. Only `Cue` spans are
read; the `Attribution` lines repeat the cue span as a relation anchor and counting both
would double every cue.

**What it will not tell you.** PolNeAR annotates the conventions of a newsroom, including
punctuation that introduces a quotation — a colon, a typographic dash. Those are gold cues
there and meaningless in a memory write, so they are left in the missed-cue list rather
than chased. Roughly half the remaining recall gap is verbs that are reporting verbs in
news and ordinary verbs in conversation ("called", "found", "shows").

### FRANK

Pagnoni et al. 2021 (NAACL). Source articles, generated summary sentences, and three
annotators' typed factual-error labels. This is the only external corpus shaped like
TWSS's actual input: a source, text derived from it, and an outside judgement of
whether the derivation broke.

Read it carefully. FRANK's typology is dominated by hallucination — wrong entity, wrong
predicate, invented content — which TWSS has never claimed to detect and structurally
cannot: a fabricated name is perfectly well-hedged and perfectly well-attributed. A high
score against FRANK overall would mean the checks were firing for the wrong reasons.

The two informative numbers are written down in `eval_frank.py` before the result:

1. the **lift on `CircE`** (circumstance: time, place, manner), the one category that maps
   onto `TEMPORAL_SCOPE_DROPPED` and `CONDITION_DROPPED`;
2. the **flag rate on sentences all three annotators called clean**, which is an external
   false-positive rate and is the number that can hurt.

It did hurt, and it was worth it: item 2 found two defects no local corpus could reach.
See the external section of the top-level README.

### MemGPT function-call traces

The only external corpus that contains actual **memory writes**. An agent with a
completely different memory API decided on its own what to store, and the conversation
that preceded each write sits beside it in the trace.

**Check the count before quoting anything.** The dataset advertises ~2,750 function calls
and is overwhelmingly retrieval:

| call | count |
|---|---|
| `send_message` / `conversation_search` / `archival_memory_search` | ~2,730 |
| `core_memory_append` | 17 |
| `archival_memory_insert` | 1 |
| `core_memory_replace` | **0**, despite being a documented call |

After de-duplicating (`msc_correct_only` is a subset of `msc_full`) that is **13 unique
writes**, unlabelled. It is a smoke test. No precision or recall figure may be quoted from
it, and `eval_memgpt.py` says so in its own summary output.

Two things came out of it anyway, which is why it is kept:

**One write is a textbook instance of the target failure.** The agent asks itself about a
dog named Barnaby, searches history, finds evidence, and reasons: *"this appears to
contradict my core memory... I wonder why this discrepancy occurred."* It then writes to
core memory: *"I have a German Shepherd named Barnaby. Barnaby is gray in color."* The
unresolved contradiction, the uncertainty, and the fact that this came from retrieved
history rather than established knowledge are all gone. That is manufactured confidence in
a production trace from a system nobody here built.

**One exposed a limitation no local corpus could.** TWSS treats a transcript as one
flat source. In that same trace an early turn says *"I don't recall having a dog named
Barnaby"* and a later turn retracts it once evidence arrives. `POLARITY_CHANGED` matched
the early turn and reported that the memory asserts what the source denied -- locally
true, globally wrong, because **the source updated itself**. Local corpora are short
single-exchange conversations, so supersession never arose. See the Limitations section of
the top-level README.

## Licences

| corpus | licence | notes |
|---|---|---|
| BioScope | free for research use | Vincze et al. 2008, BMC Bioinformatics |
| Szeged Uncertainty Corpus | free for research use | Szarvas et al. 2012, Computational Linguistics |
| PolNeAR | see repo | Newell et al. 2018, LREC |
| FRANK | MIT (repo) | built on CNN/DM + XSum |

Cite the originals if you publish anything from these numbers. None of this annotation is
TWSS's work.

## Corpora considered and not used

- **PARC 3.0** (19,712 attribution relations annotated as source/cue/content) is the
  usual external reference for attribution, but it annotates Wall Street Journal text from
  the Penn Treebank, which needs a paid LDC licence. PolNeAR covers the same relation type
  on more articles for free, so PARC is not needed. Still worth adding if the licence is
  already available, since it is a different domain.
- **CoNLL-2010 shared task** releases only trial data publicly; the full annotation is the
  Szeged corpus above, which is what these scripts use.
