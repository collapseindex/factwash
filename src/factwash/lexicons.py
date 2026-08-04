"""Lexicons ported from the papers, verbatim where marked.

MC_HEDGE and MC_ATTRIB are copied character-for-character from
manufactured-confidence ``src/manufactured_confidence/backends.py`` (App. E of the
paper). EXT_* tuples are Factwash additions needed for arbitrary text; they are kept
separate so the paper-verbatim core stays auditable at a glance.
"""

# --- Manufactured Confidence App. E, verbatim -----------------------------------------------------
MC_HEDGE = ("probably", "might", "may ", "maybe", "possibly", "perhaps", "seems", "appears", "reportedly",
            "allegedly", "rumor", "unverified", "unconfirmed", "not verified", "to be verified",
            "unreliable", "not reconciled", "uncertain", "alleged", "purported")

MC_ATTRIB = ("said", "says", "claim", "note", "noted", "record", "mention", "told", "reportedly",
             "user:", "asked", "message", "according", "stated that")

# --- Factwash extensions (NOT from the papers) -----------------------------------------------------
# Factwash's own additions. Two design rules, both learned from measured failures:
#
# 1. ASYMMETRY. The SOURCE side decides whether a flag is even possible, so it wants
#    recall: a hedge form we don't know makes the failure invisible by construction.
#    The MEMORY side decides whether to fire, so it wants breadth for a different
#    reason -- anything that plausibly preserves stance should suppress the flag,
#    because a false positive costs a user's trust in the whole tool. Hence the
#    memory-side sets below are supersets, not the same list used twice.
#
# 2. NO BARE "heard". It shipped for an hour and fired on "I heard the alarm go off",
#    which is perception, not hearsay. Reported speech needs a complement ("heard that",
#    "heard from"), and that distinction is the whole difference.
#
# Terms are drawn from the standard evidentiality / hedging vocabulary rather than from
# whatever the current stress corpus happens to contain; the held-out set exists to keep
# that honest.
EXT_HEDGE = ("i think", "i believe", "iirc", "if i recall", "supposedly", "sounds like",
             "heard that", "heard from", "not sure", "could be",
             "not confirmed", "yet to be confirmed", "not been verified",
             # evidential / epistemic markers the first live pass missed entirely
             "apparently", "evidently", "ostensibly", "presumably", "arguably",
             "suggests", "suggested", "indicates that", "may have", "might have",
             "believed to", "thought to", "understood to", "expected to",
             "pending confirmation", "not established", "not yet established",
             "subject to confirmation", "to be confirmed", "tbc", "unclear whether",
             "some indication", "early signs", "if true", "assuming")
EXT_ATTRIB = ("rumor", "heard that", "heard from", "word is", "someone", "fyi",
              # Relayed-speech markers: the source cited a person or channel.
              # NOT a bare "per " or "via ": those match "per year", "per request",
              # "via the API" -- measurement and transport, not attribution. That
              # over-reach shipped for one test run and pushed the calibration
              # false-positive rate from 1/13 to 2/13 before the ceiling caught it.
              "reported", "relayed", "passed on", "secondhand", "second-hand",
              "grapevine", "chatter", "as per", "per the", "from the team", "i'm told",
              "we're told", "was told", "hearsay", "attributed to", "credited to",
              "cites", "cited", "quoting", "paraphrasing")

# The memory side is checked against these SUPERSETS. Anything here counts as the
# memory having preserved stance, so a flag is suppressed. Tense and person vary
# freely in an extraction ("stated that" becomes "states that"), and treating that
# as laundering was a measured false positive.
MEMORY_HEDGE_EXTRA = ("state that", "states that", "stating", "claims", "claimed",
                      "claiming", "notes that", "noting", "mentions", "mentioning",
                      "says that", "saying", "tells", "telling", "recounts",
                      "unverified", "uncorroborated", "alleges", "alleging",
                      # BARE STEMS. The set above has inflected forms and no stems, so
                      # "german media say" was called laundering while "german media
                      # says" would have passed -- found on FRANK, where the memory
                      # attributed the claim in plain sight and the gate blocked it
                      # anyway. Substring matching means the stem covers every
                      # inflection, which is the whole reason the gap was invisible.
                      #
                      # Stems are safer HERE than on the source side: this set only ever
                      # SUPPRESSES a flag, so an over-broad term costs a missed detection
                      # rather than a false accusation. "Safer" is not "free", and the
                      # first draft of this line proved it -- "quote", "state", "tell",
                      # "cite" and "describ" all went in on the same reasoning and
                      # "quote" immediately suppressed a planted MANUFACTURED_CONFIDENCE
                      # case whose memory read "Vendor quote: $4,500". A price quote is
                      # not quoted speech. The same polysemy sinks the others: "real
                      # estate" contains "state", "intelligence" contains "tell", and
                      # "solicited" contains "cite" -- in an access-control domain, which
                      # is the demo domain.
                      #
                      # So only the two stems with direct external evidence survive.
                      # "say" is the one FRANK caught: a memory reading "german media
                      # say" was blocked as laundering because the set had "says" and
                      # "saying" but not the stem.
                      "say", "report")
MEMORY_ATTRIB_EXTRA = MEMORY_HEDGE_EXTRA

# --- terms derived from EXTERNAL expert annotation --------------------------------------
# Mined from the DEV half of BioScope + the Szeged Uncertainty Corpus (57,891 sentences
# annotated by linguists at HUN-REN-SZTE, years before this project existed) and chosen by
# a fixed rule rather than by eye: a candidate is kept only if the sentences it newly
# fires on are >=60% gold-annotated hedges and it fires at least 10 times on dev. The
# consequence is measured on the TEST half, whose documents are disjoint.
#
# Kept separate from EXT_HEDGE for provenance: those terms came from this project's own
# vocabulary, these came from an outside gold standard. See experiments/external/.
#
# Bare stems on purpose. Matching is substring, so "suggest" covers suggests/suggested/
# suggesting -- the shipped lexicon had the inflected forms but not the stem, and that one
# gap accounted for 429 of the misses on dev.
#
# What was REJECTED by the same rule is as informative as what was kept, and is recorded
# in experiments/external/tune_lexicon.py: no negation and no conditional candidate
# cleared the bar, which is consistent with those closed-class detectors already scoring
# 0.89 and 0.61 F1 externally. The lexicon's weakness is hedging, exactly as claimed.
EXT_HEDGE_EXTERNAL = ("suggest", "indicate", "likely", "considered to", "assume",
                      "believed that")

# Attribution terms mined the same way from PolNeAR's dev split (1,008 political news
# articles, token-level source/cue/content, Newell et al. 2018). PolNeAR is what LAUNDERED
# is scored against: PARC 3.0 is the usual reference for attribution but annotates Wall
# Street Journal text behind a paid LDC licence, and PolNeAR is free.
#
# "say" is the stem gap again, and the third time this pattern has cost real recall: the
# lexicon had "said" and "says" and not "say", so "sources say" was invisible.
EXT_ATTRIB_EXTERNAL = ("say", "added", "wrote", "agreed")

# Source-side: decides whether a flag is POSSIBLE. Precision-oriented.
HEDGE = MC_HEDGE + EXT_HEDGE + EXT_HEDGE_EXTERNAL
ATTRIB = MC_ATTRIB + EXT_ATTRIB + EXT_ATTRIB_EXTERNAL

# Memory-side: decides whether a flag FIRES. Deliberately broader, so an extraction
# that preserved stance in wording we did not anticipate is not called laundering.
HEDGE_IN_MEMORY = HEDGE + MEMORY_HEDGE_EXTRA
ATTRIB_IN_MEMORY = ATTRIB + MEMORY_ATTRIB_EXTRA

# The evidential class ("reportedly"-type hedges) is the near-universal blind spot in the paper's
# prompt-fix experiments, so flags carrying one of these are marked loudest.
EVIDENTIAL = ("reportedly", "allegedly", "rumor", "supposedly", "i heard", "someone", "word is")

# Cues that mark a DERIVED conclusion (an aggregate over source values). BRITTLE/TRUNCATED only
# fire on these; a plain stated fact is not a derivation and must not be flagged.
AGGREGATE_CUES = ("total", "in all", "altogether", "overall", "comes to", "came to", "sum",
                  "adds up", "grand total", "combined", "average")

# Markers that make a knowingly-partial memory honest (Reclaim's completeness tag).
COMPLETENESS_MARKERS = ("incomplete", "partial", "truncated", "subset", "some of", "not all")


# --- polarity and conditionals (Factwash additions) ------------------------------------
# These are CLOSED-CLASS, which is why they are expected to generalise where the hedge
# lexicon does not: English has a small, stable set of negators and conditional
# subordinators, unlike the open-ended ways to signal hearsay.
#
# Matched with word boundaries, NOT substrings. "not" is inside "note", "nothing",
# "another" and "cannot"; the substring matching used elsewhere in this file would fire
# on all of them. That distinction is the whole reason these live in their own regexes.
NEGATION_PATTERN = (
    r"\b(?:not|never|no|none|nobody|nothing|nowhere|neither|nor|cannot|without|"
    r"denied|declines?|declined|rejects?|rejected|refuses?|refused|revoked|"
    r"lacks?|excluded|prohibited|forbidden|disallowed)\b"
    r"|n't\b"
    # LEXICAL negation, added from BioScope's dev split. Not closed-class like the
    # negators above -- these are ordinary verbs and adjectives that happen to negate --
    # so they are grouped separately and were kept only because they cleared the same
    # >=60%-precision, >=10-firing bar: fail* 0.84, unable 1.00, lacking 1.00.
    # "absence" (0.53) and "absent" (0.62) did not clear it and are deliberately absent.
    r"|\b(?:fail(?:s|ed|ure|ing)?|unable|lacking)\b"
)

# "when" and "should" are deliberately absent: too often temporal or modal rather than
# conditional, and a false positive here costs more than the miss.
#
# Two narrowings below, both measured on the Szeged dev split and confirmed on test
# (precision 0.55 -> 0.61, recall 0.68 -> 0.67). Both fix cases that are wrong under
# Factwash's OWN definition, which is the bar used here: the Szeged scheme annotates
# speculative hypotheticals only, so many of its "false positives" are real conditions it
# simply does not mark. Chasing THOSE would make the tool worse at spotting a dropped
# condition on a permission, which is the job.
#
#   "subject to"  removed. In practice it is susceptibility, not a condition:
#                 "subject to redox regulation", "subject to change".
#   "assuming"    now excludes taking something on: "Assuming command at the most
#                 critical period of the war" is not positing a condition.
CONDITIONAL_PATTERN = (
    r"\b(?:if|unless|provided that|as long as|in case|only when|only if|"
    r"contingent on|conditional on|depending on|"
    r"assuming(?!\s+(?:command|control|office|power|responsibility|"
    r"the\s+(?:role|position|presidency|throne)))|"
    r"in the event that|so long as)\b"
)

# "if" that means "whether" is a complement, not a condition: "we tested if X held",
# "the relationship, if any". A memory that drops it has lost nothing to restore.
# Applied in conditionals_in() rather than in the pattern because it needs to look at
# the rest of the sentence, and only fires when "if" is the ONLY conditional present.
_INTERROGATIVE_IF = (
    r"\b(?:see|determine|test|tested|check|checked|investigate|investigated|examine|"
    r"examined|assess|assessed|ask|asked|know|wonder|evaluate|evaluated|verify|"
    r"verified|establish)\b[^.]{0,20}?\bif\b"
    r"|\bif\s+any\b"
)

# Time expressions are a bounded pattern set, unlike hedges, so "the source scoped this to
# a time and the memory did not" is buildable deterministically. That is the tractable
# half of temporal flattening: it catches the DROPPED SCOPE, not the tense flip. Detecting
# "was" becoming "is" needs verb alignment against the claim, which needs a parser.
TEMPORAL_PATTERN = (
    r"\b(?:19|20)\d\d\b"
    r"|\bq[1-4]\b"
    r"|\b(?:january|february|march|april|june|july|august|september|october|november|december)\b"
    r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    r"|\b(?:yesterday|today|tomorrow|tonight)\b"
    r"|\b(?:last|next|this|past|previous|coming)\s+"
    r"(?:night|week|month|quarter|year|morning|afternoon|evening|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    r"|\b(?:back\s+in|as\s+of|at\s+the\s+time|used\s+to|formerly|previously|historically|"
    r"since|ago|earlier|no\s+longer|at\s+that\s+point|at\s+one\s+point)\b"
)


# --- the matchers themselves ----------------------------------------------------------
# These exist so that "does the lexicon fire on this text" has exactly ONE definition.
# The checks call them, and so does the external evaluation against expert-annotated
# corpora; measuring a reimplementation beside the tool would measure the wrong thing.
#
# Matching is case-insensitive substring, not word-boundary, and that is deliberate for
# the OPEN-class sets: hedges inflect freely ("suggests"/"suggested"/"suggesting") and a
# missed source hedge makes a failure invisible. The closed-class sets (negation,
# conditionals, time) use the word-boundary regexes above instead, for the opposite
# reason documented there.
import re as _re

_NEG_RE = _re.compile(NEGATION_PATTERN, _re.IGNORECASE)
_COND_RE = _re.compile(CONDITIONAL_PATTERN, _re.IGNORECASE)
_TIME_RE = _re.compile(TEMPORAL_PATTERN, _re.IGNORECASE)


def _substrings_in(text: str, terms) -> list[str]:
    low = text.lower()
    return [t for t in terms if t in low]


def hedges_in(text: str) -> list[str]:
    """Source-side hedge terms present in `text`. Precision-oriented set."""
    return _substrings_in(text, HEDGE)


def hedges_in_memory(text: str) -> list[str]:
    """Memory-side hedge terms. Broader: anything here suppresses a flag."""
    return _substrings_in(text, HEDGE_IN_MEMORY)


def attribs_in(text: str) -> list[str]:
    return _substrings_in(text, ATTRIB)


def attribs_in_memory(text: str) -> list[str]:
    return _substrings_in(text, ATTRIB_IN_MEMORY)


def negations_in(text: str) -> list[str]:
    return [m.group(0) for m in _NEG_RE.finditer(text)]


_INTERROG_IF_RE = _re.compile(_INTERROGATIVE_IF, _re.IGNORECASE)


def conditionals_in(text: str) -> list[str]:
    hits = [m.group(0) for m in _COND_RE.finditer(text)]
    # Only suppress when "if" is the ONLY thing matched. A sentence carrying "unless" or
    # "provided that" alongside an interrogative "if" still has a real condition in it.
    if hits and all(h.lower() == "if" for h in hits) and _INTERROG_IF_RE.search(text):
        return []
    return hits


def times_in(text: str) -> list[str]:
    return [m.group(0) for m in _TIME_RE.finditer(text)]
