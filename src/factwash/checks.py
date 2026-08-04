"""The seven checks. Four verdict patterns come from the papers; POLARITY_CHANGED,
CONDITION_DROPPED and TEMPORAL_SCOPE_DROPPED are Factwash's own. Localization comes
from claims.py.

Every check returns a CheckOutcome with status pass | warn | fail | n/a. N/A is first-class:
a check that cannot apply says so instead of passing silently (an always-passing check is
decorating, not validating).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import lexicons as lex
from .claims import (VALUE_TOLERANCE, is_question, match_source_window, matching_source_indices, numbers,
                     numbers_with_pos, sentences)

PASS, WARN, FAIL, NA = "pass", "warn", "fail", "n/a"

CITATIONS = {  # ASCII-safe on purpose: Windows consoles mangle the section sign
    "BRITTLE": "Reclaim Sec. 4, source-token test (locating/governed.py::source_preserved)",
    "TRUNCATED": "Reclaim Sec. 7, recompute certificate + completeness tag",
    "MANUFACTURED_CONFIDENCE": "Manufactured Confidence App. E, dehedged()",
    "LAUNDERED": "Manufactured Confidence App. E, laundering metric",
}

_COMPLETENESS_KOFN = re.compile(r"\b\d+\s+of\s+\d+\b")


@dataclass
class Flag:
    name: str
    check: str
    severity: str          # fail | warn | info
    evidence: str
    citation: str
    evidential: bool = False


@dataclass
class CheckOutcome:
    check: str
    status: str
    flags: list = field(default_factory=list)
    note: str = ""


def _trunc(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _fmt(values) -> str:
    return "[" + ", ".join(f"{v:g}" for v in values) + "]"


# --- derivation extraction (shared by BRITTLE and TRUNCATED) --------------------------------------
@dataclass
class Derivation:
    sentence: str
    claimed: float
    inputs: list            # source Numbers != claimed (with multiplicity)
    distinct_inputs: list   # distinct input values
    retained: list          # distinct input values present in the memory
    missing: list


def _conclusions(memory: str):
    """Memory sentences asserting a DERIVED value: aggregate cue + number. The claimed value is
    the number nearest the cue (so 'total $400 (had the $200...)' reads 400, not 200)."""
    out = []
    for sent in sentences(memory):
        if is_question(sent):
            continue
        low = sent.lower()
        cue_pos = min((low.find(c) for c in lex.AGGREGATE_CUES if c in low), default=-1)
        if cue_pos < 0:
            continue
        best, best_dist = None, None
        for num, pos in numbers_with_pos(sent):
            dist = abs(pos - cue_pos) - (1000 if num.is_money else 0)  # prefer money values
            if best is None or dist < best_dist:
                best, best_dist = num, dist
        if best is not None:
            out.append((sent, best))
    return out


def _derivations(source: str, memory: str) -> list[Derivation]:
    src_nums = numbers(source)
    mem_nums = numbers(memory)
    out = []
    for sent, target in _conclusions(memory):
        claimed = target.value
        inputs = [n for n in src_nums if abs(n.value - claimed) > VALUE_TOLERANCE]
        distinct = sorted({round(n.value, 2) for n in inputs})
        mem_vals = {round(n.value, 2) for n in mem_nums if abs(n.value - claimed) > VALUE_TOLERANCE}
        retained = [v for v in distinct if v in mem_vals]
        missing = [v for v in distinct if v not in mem_vals]
        out.append(Derivation(sent, claimed, inputs, distinct, retained, missing))
    return out


# --- check 1: BRITTLE -----------------------------------------------------------------------------
def check_brittle(source: str, memory: str) -> CheckOutcome:
    ders = _derivations(source, memory)
    if not ders:
        return CheckOutcome("BRITTLE", NA, note="no derived conclusion (aggregate cue + value) in memory")
    applicable = [d for d in ders if len(d.distinct_inputs) >= 2]
    if not applicable:
        return CheckOutcome("BRITTLE", NA, note="conclusion present but source has no re-derivation values")
    flags, status = [], PASS
    for d in applicable:
        cite = CITATIONS["BRITTLE"]
        if not d.retained:
            status = FAIL
            flags.append(Flag("BRITTLE", "BRITTLE", FAIL,
                              f"conclusion kept ('{_trunc(d.sentence)}') but none of the source values "
                              f"{_fmt(d.distinct_inputs)} are retained", cite))
        elif d.missing:
            if status != FAIL:
                status = WARN
            flags.append(Flag("BRITTLE", "BRITTLE", WARN,
                              f"partial basis for '{_trunc(d.sentence)}': retained {_fmt(d.retained)}, "
                              f"missing {_fmt(d.missing)}", cite))
    return CheckOutcome("BRITTLE", status, flags)


# --- check 2: TRUNCATED ---------------------------------------------------------------------------
def _has_completeness_tag(memory: str) -> bool:
    low = memory.lower()
    return bool(_COMPLETENESS_KOFN.search(low)) or any(m in low for m in lex.COMPLETENESS_MARKERS)


def check_truncated(source: str, memory: str) -> CheckOutcome:
    ders = _derivations(source, memory)
    if not ders:
        return CheckOutcome("TRUNCATED", NA, note="no derived conclusion in memory")
    flags, status, certified_any = [], PASS, False
    for d in ders:
        certified = None
        for candidate in (d.inputs, [n for n in d.inputs if n.is_money]):
            if len(candidate) >= 2 and abs(sum(n.value for n in candidate) - d.claimed) <= 0.01:
                certified = candidate
                break
        if certified is None:
            continue
        certified_any = True
        cite = CITATIONS["TRUNCATED"]
        if not d.missing:
            note = (f"certificate: recomputed {d.claimed:g} from {len(d.distinct_inputs)} of "
                    f"{len(d.distinct_inputs)} retained values")
            flags.append(Flag("TRUNCATED", "TRUNCATED", "info", note, cite))
        elif _has_completeness_tag(memory):
            if status != FAIL:
                status = WARN
            flags.append(Flag("TRUNCATED", "TRUNCATED", WARN,
                              f"incomplete but tagged: missing {_fmt(d.missing)} behind a completeness marker",
                              cite))
        else:
            status = FAIL
            retained_sum = sum(n.value for n in certified if round(n.value, 2) in set(d.retained))
            flags.append(Flag("TRUNCATED", "TRUNCATED", FAIL,
                              f"memory claims {d.claimed:g} but retained values recompute to {retained_sum:g}; "
                              f"completeness tag missing (add 'k of N items')", cite))
    if not certified_any:
        return CheckOutcome("TRUNCATED", NA,
                            note="no recomputable derivation (source values do not recompute the claimed total)")
    return CheckOutcome("TRUNCATED", status, flags)


# --- checks 3 and 4: MANUFACTURED_CONFIDENCE and LAUNDERED ----------------------------------------
def _stance_pairs(source: str, memory: str, neighbors: bool = True):
    """Yield (memory_sentence, source_window) for every memory claim that matches a source claim.

    ``neighbors=False`` narrows the window to the single matched sentence; see
    match_source_window for why negation needs that and stance does not.
    """
    src_sents = sentences(source)
    for sent in sentences(memory):
        if is_question(sent):
            continue
        window = match_source_window(sent, src_sents, neighbors=neighbors)
        if window is not None:
            yield sent, window


CITATIONS["POLARITY_CHANGED"] = "Factwash: closed-class negation, not from the papers"
CITATIONS["CONDITION_DROPPED"] = "Factwash: closed-class conditionals, not from the papers"


def _superseded(mem_sentence: str, window: str, src_sents: list[str]) -> bool:
    """True when a LATER source sentence makes the same claim without the negation.

    A transcript is not a static document. It can assert something, deny it, and then
    retract the denial once evidence arrives, and only the last word counts. Found on a
    real MemGPT trace: the agent says "I don't recall having a dog named Barnaby",
    searches its history, finds evidence, and corrects itself -- and POLARITY_CHANGED
    fired on the retracted sentence, reporting that the memory asserted what the source
    denied. Locally true, globally wrong.

    Deliberately narrow, in three ways. The later sentence must carry no negation of its
    own, so a repeated denial is not a retraction. It must come after. And it must match
    the claim AT LEAST AS WELL as the denying sentence does, because topical overlap is
    not agreement: "Alice does not have admin on the prod cluster" followed by "Bob has
    admin on the staging cluster" shares {admin, cluster} and would otherwise suppress a
    real polarity flip. That third condition was added because the test written alongside
    this function caught the first version doing exactly that.

    Every local corpus is a single exchange, so none of this could have been found there.
    """
    try:
        here = src_sents.index(window)
    except ValueError:
        return False
    matches = dict(matching_source_indices(mem_sentence, src_sents))
    denial_score = matches.get(here, 0.0)
    for i, score in matches.items():
        if i > here and score >= denial_score and not lex.negations_in(src_sents[i]):
            return True
    return False


def check_polarity(source: str, memory: str) -> CheckOutcome:
    """The memory asserts what the source denied, or denies what it asserted.

    Strictly worse than laundering. Laundering keeps the fact and drops the stance;
    a polarity flip stores the opposite fact. Before this check, "Alice is not an
    administrator" -> "Alice is an administrator" returned a clean PASS.

    Negators are closed-class, so unlike the hedge lexicon this should generalise
    rather than memorise. It is matched with word boundaries because "not" is inside
    "note", "another" and "cannot".
    """
    # Memory side is checked WHOLE, unlike the stance checks. Negation attaches to a
    # clause, and an extractor routinely splits one source sentence across two stored
    # ones: "X was cut, though finance hasn't published it" becomes "X was cut." plus
    # "Finance has not yet published." Comparing the source window against a single
    # memory sentence called that a polarity flip 7 times out of 89 should-pass items.
    flags, matched = [], False
    mem_neg_all = lex.negations_in(memory)
    src_sents = sentences(source)
    # neighbors=False: the negation has to be in the SAME sentence as the matched claim.
    for sent, window in _stance_pairs(source, memory, neighbors=False):
        matched = True
        src_neg = lex.negations_in(window)
        mem_neg = mem_neg_all
        if src_neg and _superseded(sent, window, src_sents):
            continue
        # ONE direction only: the source denied it and the memory asserts it.
        #
        # The reverse (memory gains a negation) is almost always the extractor ADDING a
        # caveat -- "though they acknowledge this may not be precise", "Note: not
        # confirmed" -- which is the behaviour we want, not a flip. Flagging both
        # directions produced 5 false positives on 89 should-pass items and 4 of them
        # were exactly that. Dropping a negation inverts a fact; adding one qualifies it.
        if src_neg and not mem_neg:
            flags.append(Flag("POLARITY_CHANGED", "POLARITY_CHANGED", FAIL,
                              f"source denied it, memory asserts it: source {src_neg} vs memory [] "
                              f"('{_trunc(window)}' -> '{_trunc(sent)}')",
                              CITATIONS["POLARITY_CHANGED"]))
    if not matched:
        return CheckOutcome("POLARITY_CHANGED", NA, note="no memory claim matched a source claim")
    return CheckOutcome("POLARITY_CHANGED", FAIL if flags else PASS, flags)


def check_condition(source: str, memory: str) -> CheckOutcome:
    """The source made the claim conditional and the memory stored it unconditionally.

    "Alice can approve it if Bob is absent" -> "Alice can approve it" grants a standing
    permission that was never given. Restorable, so this is a REWRITE rather than a
    REJECT: the condition can be put back.
    """
    flags, matched = [], False
    for sent, window in _stance_pairs(source, memory):
        matched = True
        src_cond = lex.conditionals_in(window)
        if src_cond and not lex.conditionals_in(sent):
            flags.append(Flag("CONDITION_DROPPED", "CONDITION_DROPPED", FAIL,
                              f"condition {src_cond} in source ('{_trunc(window)}') dropped in "
                              f"memory ('{_trunc(sent)}'), storing it as unconditional",
                              CITATIONS["CONDITION_DROPPED"]))
    if not matched:
        return CheckOutcome("CONDITION_DROPPED", NA, note="no memory claim matched a source claim")
    return CheckOutcome("CONDITION_DROPPED", FAIL if flags else PASS, flags)


CITATIONS["TEMPORAL_SCOPE_DROPPED"] = "Factwash: bounded time expressions, not from the papers"


def check_temporal(source: str, memory: str) -> CheckOutcome:
    """The source scoped the claim to a time and the memory stored it undated.

    "Alice was an admin back in 2024" becoming "Alice is an admin" turns a historical
    fact into a current one. This is the tractable half of temporal flattening: it
    catches the dropped scope, not the tense flip, because deciding that "was" became
    "is" requires aligning verbs to the claim rather than spotting a token.

    WARN, not FAIL. A memory that drops a date is *stale-risky*, not necessarily wrong,
    and evicting on that would cost far more than it saves. It surfaces as
    PASS_WITH_FLAGS: informative without blocking the write.
    """
    flags, matched = [], False
    mem_times = lex.times_in(memory)
    for sent, window in _stance_pairs(source, memory):
        matched = True
        src_times = lex.times_in(window)
        if src_times and not mem_times:
            flags.append(Flag("TEMPORAL_SCOPE_DROPPED", "TEMPORAL_SCOPE_DROPPED", WARN,
                              f"source scoped this to {src_times} ('{_trunc(window)}') and the memory "
                              f"stores it undated ('{_trunc(sent)}'), so it will read as current later",
                              CITATIONS["TEMPORAL_SCOPE_DROPPED"]))
    if not matched:
        return CheckOutcome("TEMPORAL_SCOPE_DROPPED", NA, note="no memory claim matched a source claim")
    return CheckOutcome("TEMPORAL_SCOPE_DROPPED", WARN if flags else PASS, flags)


def check_dehedged(source: str, memory: str) -> CheckOutcome:
    # Claim-local, NOT whole-memory. MC App. E tests the whole stored blob, which works
    # on the paper's single-line memories but is defeated by real extractor output: a
    # preamble like "I've noted the following:" or "from your message" contains lexicon
    # words that would shield the bare laundered fact underneath it (observed on a live
    # Haiku run, 2026-08-02). Locality is what survives conversational scaffolding.
    flags, matched = [], False
    for sent, window in _stance_pairs(source, memory):
        matched = True
        src_hedges = lex.hedges_in(window)
        if src_hedges and not lex.hedges_in_memory(sent):
            evidential = any(t in lex.EVIDENTIAL for t in src_hedges)
            flags.append(Flag("MANUFACTURED_CONFIDENCE", "MANUFACTURED_CONFIDENCE", FAIL,
                              f"hedge {src_hedges} in source ('{_trunc(window)}') stripped in memory "
                              f"('{_trunc(sent)}')", CITATIONS["MANUFACTURED_CONFIDENCE"],
                              evidential=evidential))
    if not matched:
        return CheckOutcome("MANUFACTURED_CONFIDENCE", NA, note="no memory claim matched a source claim")
    return CheckOutcome("MANUFACTURED_CONFIDENCE", FAIL if flags else PASS, flags)


def check_laundered(source: str, memory: str) -> CheckOutcome:
    # Claim-local, for the preamble-shielding reason documented in check_dehedged, AND
    # single-sentence, unlike check_dehedged. Attribution is clause-attached -- "Bob told
    # me the deploy is frozen" governs its own complement -- so a "said" in the next
    # sentence is not evidence that THIS claim was attributed.
    #
    # Hedging genuinely is not clause-attached, which is why check_dehedged keeps the
    # wider window. That asymmetry is measured, not assumed. Narrowing both windows and
    # scoring against FRANK's 4,800 human-annotated summary sentences:
    #
    #     window            FRANK false positives on annotator-clean text
    #     both 3-sentence                 0.509
    #     laundered 1-sentence            0.343      <- shipped
    #     both 1-sentence                 0.250
    #
    # and every local corpus (planted 12/12, clean 1/13, held-out 3/14, live recall 95%
    # / precision 73%) is byte-identical across all four configurations. The 0.250 row
    # is tempting and is NOT taken: narrowing the hedge window loses "Alice has admin on
    # prod. Not sure though." -> "Alice has admin on prod", which is the exact failure
    # this tool exists for. No local corpus covered that case, so it is pinned in
    # tests/test_core/test_window_scope.py rather than left to the next refactor.
    flags, matched = [], False
    for sent, window in _stance_pairs(source, memory, neighbors=False):
        matched = True
        src_attrib = lex.attribs_in(window)
        if src_attrib and not lex.attribs_in_memory(sent):
            flags.append(Flag("LAUNDERED", "LAUNDERED", FAIL,
                              f"attribution {src_attrib} in source ('{_trunc(window)}') dropped in memory "
                              f"('{_trunc(sent)}')", CITATIONS["LAUNDERED"]))
    if not matched:
        return CheckOutcome("LAUNDERED", NA, note="no memory claim matched a source claim")
    return CheckOutcome("LAUNDERED", FAIL if flags else PASS, flags)
