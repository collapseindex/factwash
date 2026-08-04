"""Memory-only SURFACE SCAN for `factwash audit`.

This is NOT the write-time gate. All four paper checks need the source context, and an
existing store has already dropped it (that is the reclaim thesis). These are weak,
info-severity heuristics for triage, and every caller prints that disclaimer.
"""
from __future__ import annotations

import re

from . import lexicons as lex
from .checks import Flag, _conclusions, _trunc
from .claims import VALUE_TOLERANCE, is_question, numbers, sentences, validate_text

_DATE = re.compile(r"\b(19|20)\d\d-\d\d-\d\d\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}\b",
                   re.IGNORECASE)

DISCLAIMER = ("Factwash SURFACE SCAN (memory-only heuristics)\n"
              "This is NOT the write-time gate: the store did not keep source context, so the four\n"
              "paper checks cannot run. Findings below are weak signals for triage, not verdicts.")


def surface_scan(memory_text: str) -> list[Flag]:
    memory_text = validate_text("memory_text", memory_text)
    flags = []
    all_nums = numbers(memory_text)
    for sent in sentences(memory_text):
        if is_question(sent):
            continue
        low = sent.lower()
        hedged = any(t in low for t in lex.HEDGE)
        attributed = any(t in low for t in lex.ATTRIB)
        anchored = any(n.is_money for n in numbers(sent)) or _DATE.search(sent)
        if anchored and not hedged and not attributed:
            flags.append(Flag("UNATTRIBUTED_CONFIDENT_FACT", "SURFACE", "info",
                              f"confident dated/priced fact with no hedge or attribution: '{_trunc(sent)}'",
                              "surface heuristic (no source available; echo of MC App. E)"))
    for sent, target in _conclusions(memory_text):
        basis = [n for n in all_nums if abs(n.value - target.value) > VALUE_TOLERANCE]
        if len(basis) < 2:
            flags.append(Flag("AGGREGATE_WITHOUT_BASIS", "SURFACE", "info",
                              f"aggregate value with no basis values in the memory: '{_trunc(sent)}'",
                              "surface heuristic (no source available; echo of Reclaim §4)"))
    return flags
