"""Checking a structured memory record, where the stance is a field rather than prose.

The gate reads prose: it looks for the source's stance cues surviving into the stored
text. That is the wrong instrument for a record like

    CLAIM: API rate limit ~500 req/min
    SOURCE: the user
    CERTAINTY: hedged
    AS_OF: unspecified

which preserves the stance perfectly and contains none of the words a hedge lexicon
knows. Measured: a schema-through memory scored *worse* than a prose one under the prose
gate, entirely because "certainty: hedged" is invisible to a detector looking for
"probably". The record is more machine-readable, not less; it just needs to be read as a
record.

So this module does the comparison the schema makes possible, and it needs no model and
no lexicon of hedged phrasings at all:

    the source carries stance  ->  the record's CERTAINTY must not say "asserted"
    the source names a speaker ->  the record's SOURCE must not be empty or unspecified
    the source dates it        ->  the record's AS_OF must not be empty or unspecified

Detecting stance in the SOURCE still uses the deterministic lexicons, with all the
open-class limits documented in the README. What this removes is the second, harder
problem: recognising stance in the rewrite. A field does not need recognising.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .checks import Flag
from .claims import sentences, strip_roles, validate_text
from . import lexicons as lex

REQUIRED = ("CLAIM", "SOURCE", "CERTAINTY", "AS_OF")
CERTAINTY_VALUES = ("asserted", "hedged", "rumor", "unverified")
EMPTY = ("", "unspecified", "unknown", "n/a", "none")

# A record whose CERTAINTY is one of these is claiming the source asserted it plainly.
ASSERTED = ("asserted",)


@dataclass
class RecordReport:
    verdict: str                      # PASS | REWRITE | REJECT | MALFORMED
    flags: list = field(default_factory=list)
    record: dict = field(default_factory=dict)
    missing: tuple = ()

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "record": self.record,
                "missing_fields": list(self.missing),
                "flags": [{"name": f.name, "evidence": f.evidence} for f in self.flags]}

    def render(self) -> str:
        lines = [f"verdict: {self.verdict}"]
        if self.missing:
            lines.append(f"  missing fields: {', '.join(self.missing)}")
        for f in self.flags:
            lines.append(f"  {f.severity.upper()}: {f.name}: {f.evidence}")
        return "\n".join(lines)


def parse_record(text: str) -> dict:
    """Read FIELD: value lines. Unknown lines are ignored; order does not matter.

    Markdown is stripped from BOTH ends of the key, because models reliably emit
    ``- **CERTAINTY**: rumor`` and a left-only strip leaves the trailing asterisks
    attached, silently dropping the field.
    """
    out = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().strip("-*#>` ").upper().replace(" ", "_")
        if key in REQUIRED:
            out[key] = val.strip().strip("*`").strip()
    return out


def _cues(text: str, table) -> list:
    """Stance cues present in the source, claim-local sentences only."""
    hits = []
    for sent in sentences(text):
        low = " " + " ".join(sent.lower().split()) + " "
        hits += [c for c in table if c.strip().lower() in low]
    return sorted(set(hits))


def check_record(source: str, record) -> RecordReport:
    """Compare a structured memory record against the source it was written from.

    Args:
        source: the conversation text the record was written from.
        record: the record, either as ``FIELD: value`` text or as a dict.

    Returns:
        RecordReport. MALFORMED when required fields are absent, because a record
        missing its retention fields is not a record that passed, it is one that was
        never written. That mirrors UNCHECKABLE in the prose gate: absence of evidence
        is never reported as evidence of absence.
    """
    src = strip_roles(validate_text("source", source))
    rec = record if isinstance(record, dict) else parse_record(
        validate_text("record", record))
    rec = {k: (v or "").strip() for k, v in rec.items()}

    missing = tuple(k for k in REQUIRED if not rec.get(k))
    if missing:
        return RecordReport("MALFORMED", [], rec, missing)

    flags = []
    certainty = rec["CERTAINTY"].lower()
    if certainty not in CERTAINTY_VALUES:
        flags.append(Flag("CERTAINTY_UNRECOGNISED", "CERTAINTY", "warn",
                          f"CERTAINTY is {rec['CERTAINTY']!r}, not one of {CERTAINTY_VALUES}",
                          "Factwash: record schema"))

    hedges = _cues(src, lex.MC_HEDGE)
    attribs = _cues(src, lex.MC_ATTRIB)
    dates = _cues(src, getattr(lex, "EXT_TEMPORAL", ()))

    if hedges and certainty in ASSERTED:
        flags.append(Flag("MANUFACTURED_CONFIDENCE", "CERTAINTY", "fail",
                          f"source hedges {hedges} but the record certifies it as "
                          f"{rec['CERTAINTY']!r}", "Factwash: record schema"))
    if attribs and rec["SOURCE"].lower() in EMPTY:
        flags.append(Flag("LAUNDERED", "SOURCE", "fail",
                          f"source attributes the claim {attribs} but the record's SOURCE "
                          f"is {rec['SOURCE']!r}", "Factwash: record schema"))
    if dates and rec["AS_OF"].lower() in EMPTY:
        flags.append(Flag("TEMPORAL_SCOPE_DROPPED", "AS_OF", "warn",
                          f"source dates the claim {dates} but the record's AS_OF is "
                          f"{rec['AS_OF']!r}", "Factwash: record schema"))

    fails = [f for f in flags if f.severity == "fail"]
    verdict = "REWRITE" if fails else ("PASS_WITH_FLAGS" if flags else "PASS")
    return RecordReport(verdict, flags, rec, ())
