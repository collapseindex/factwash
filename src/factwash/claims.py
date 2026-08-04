"""Claim-localization machinery: the part Factwash adds on top of the papers.

The papers localize claims by construction (a known token, a per-item source_tokens
list). Factwash has to find claims in arbitrary text, so everything here is a
sentence + rule heuristic: deliberately dumb, English-only, and calibrated by the
two-corpus tests in ``tests/test_integration/test_calibration.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TEXT_CHARS = 1_000_000  # bound input before processing

MIN_SHARED_CONTENT_WORDS = 2   # a memory claim must share this many content words with a source
# ...covering this fraction of the SHORTER side's content words.
#
# 0.25 is measured, not guessed. Swept over 101 real extractor outputs (see
# tests/test_integration/test_threshold_sweep.py): false positives on genuinely
# confident memories are FLAT at 2/34 everywhere from 0.20 to 0.50, while hearsay
# detection falls monotonically as the value rises (41/67 at 0.25 down to 37/67 at
# 0.50) and unmatched writes climb (6 to 10). The old 0.34 was strictly worse than
# 0.25 at no false-positive saving. The shipped fixtures cannot justify this number
# at all -- they score 12/12 and 1/13 identically across that entire range -- which
# is why the sweep runs against live data.
MIN_CONTAINMENT = 0.25
VALUE_TOLERANCE = 0.005        # numeric equality tolerance

# A semicolon joins clauses; it does not end a sentence. Splitting on it cut
# "…reportedly cut to $40,000 (according to unconfirmed reports; finance hasn't
# published…)" in half and judged the hedge-free trailing fragment on its own,
# rejecting a correct hedge-preserving rewrite (live Haiku run, 2026-08-02).
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN = re.compile(r"[a-z0-9$€£][\w.$€£%,-]*")
_NUMBER = re.compile(r"(?P<money>[$€£]\s?)?(?P<num>\d(?:[\d,]*\d)?(?:\.\d+)?)")
_YEAR = re.compile(r"(19|20)\d\d")
_ROLE = re.compile(r"(?im)^\s*(user|assistant|system|tool)\s*:\s*")

STOPWORDS = frozenset(
    "a an the and or but if so to of in on at for with from by is are was were be been being am "
    "i we you he she it they them this that these those as its their our your my me us him her "
    "do does did done have has had will would can could should shall must not no yes "
    "there here what which who whom when where why how all any both each few more most other some "
    "such only own same than too very just now then also let lets get got".split()
)


def validate_text(name: str, text: str) -> str:
    if not isinstance(text, str):
        raise TypeError(f"{name} must be a string, got {type(text).__name__}")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"{name} is {len(text):,} chars; max {MAX_TEXT_CHARS:,}")
    return text


def strip_roles(text: str) -> str:
    """Remove transcript role labels ('User:', 'Assistant:') so they are neither content words
    nor false attribution markers ('user:' is in the MC attribution lexicon for STORED text)."""
    return _ROLE.sub("", text)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]


def is_question(sentence: str) -> bool:
    return sentence.rstrip().endswith("?")


def content_words(text: str) -> set[str]:
    words = set()
    for tok in _TOKEN.findall(text.lower()):
        tok = tok.strip(".,-")
        if len(tok) < 2 and not tok.isdigit():
            continue
        if tok in STOPWORDS:
            continue
        words.add(tok)
    return words


@dataclass(frozen=True)
class Number:
    raw: str
    value: float
    is_money: bool


def numbers_with_pos(text: str) -> list[tuple[Number, int]]:
    """Extract standalone numeric values with their character positions. Skips word-glued digits
    (Q3, 3pm), date components (2026-06-12), decimal tails, and bare years: those are labels, not
    line items. That filter is a documented limitation, not a claim of perfect parsing."""
    out = []
    for m in _NUMBER.finditer(text):
        start, end = m.start(), m.end()
        prev = text[start - 1] if start else ""
        nxt = text[end] if end < len(text) else ""
        if prev.isalnum() or prev in ".-/":
            continue
        if nxt.isalpha():
            continue
        if nxt in "-/" and end + 1 < len(text) and text[end + 1].isdigit():
            continue
        num = m.group("num")
        is_money = bool(m.group("money"))
        if not is_money and _YEAR.fullmatch(num):
            continue
        try:
            value = float(num.replace(",", ""))
        except ValueError:  # pragma: no cover - regex should prevent this
            continue
        out.append((Number(raw=m.group(0).strip(), value=value, is_money=is_money), start))
    return out


def numbers(text: str) -> list[Number]:
    return [n for n, _ in numbers_with_pos(text)]


def match_source_window(mem_sentence: str, source_sentences: list[str],
                        neighbors: bool = True) -> str | None:
    """Find the source stance window for a memory sentence.

    With ``neighbors=True`` (the default) this returns the best-overlapping source
    sentence plus the one on each side, because hedges routinely live next door:
    "X is admin. Not sure though." Stance is a discourse-level property.

    With ``neighbors=False`` it returns the matched sentence alone. NEGATION is not a
    discourse-level property -- it attaches to a clause -- so a "not" in the previous
    sentence says nothing about whether THIS claim was denied. Scoring the gate against
    FRANK's 4,800 human-annotated summary sentences made the difference impossible to
    miss: on long-form source text POLARITY_CHANGED fired on 1,743 sentences, including
    36% of the ones all three annotators called clean, because a three-sentence window of
    news prose almost always contains a negation somewhere.

    Returns None when nothing overlaps enough; callers must report N/A, not guess.
    """
    mem_words = content_words(mem_sentence)
    if len(mem_words) < MIN_SHARED_CONTENT_WORDS:
        return None
    best_i, best_score = None, 0.0
    for i, src_sentence in enumerate(source_sentences):
        src_words = content_words(src_sentence)
        shared = mem_words & src_words
        if len(shared) < MIN_SHARED_CONTENT_WORDS:
            continue
        # Overlap against the SHORTER side, not against the memory. Extraction adds words
        # by design -- mem0's prompt asks for "contextually rich" statements, so a stored
        # claim routinely carries dates and context the source never had. Dividing by the
        # memory's length punished exactly that, and the failure was silent: no match ->
        # every check N/A -> PASS. A live run watched a laundered admin claim slip through
        # at containment 0.30 while the gate reported clean.
        score = len(shared) / min(len(mem_words), len(src_words))
        if score > best_score:
            best_i, best_score = i, score
    if best_i is None or best_score < MIN_CONTAINMENT:
        return None
    if not neighbors:
        return source_sentences[best_i]
    lo, hi = max(0, best_i - 1), min(len(source_sentences), best_i + 2)
    return " ".join(source_sentences[lo:hi])


def matching_source_indices(mem_sentence: str, source_sentences: list[str]) -> list[tuple[int, float]]:
    """Every (index, score) whose source sentence matches the memory claim, best first.

    match_source_window answers "which source sentence is this claim from". This answers
    "which source sentences talk about this claim at all, and how strongly", which is
    what supersession needs: a transcript can state something, deny it, and then retract
    the denial, and only the last word counts.

    The score is returned because topical overlap is not enough to retract a denial.
    "Alice does not have admin on the prod cluster" and "Bob has admin on the staging
    cluster" share {admin, cluster} and match the same claim at 0.25 containment; treating
    the second as retracting the first would blind the check to a real polarity flip.
    """
    mem_words = content_words(mem_sentence)
    if len(mem_words) < MIN_SHARED_CONTENT_WORDS:
        return []
    scored = []
    for i, src_sentence in enumerate(source_sentences):
        src_words = content_words(src_sentence)
        shared = mem_words & src_words
        if len(shared) < MIN_SHARED_CONTENT_WORDS:
            continue
        score = len(shared) / min(len(mem_words), len(src_words))
        if score >= MIN_CONTAINMENT:
            scored.append((i, score))
    return sorted(scored, key=lambda pair: -pair[1])
