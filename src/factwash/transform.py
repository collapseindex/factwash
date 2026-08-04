"""The transformation view: factwash.inspect(source, output) -> TransitionReport.

The gate (core.check) answers "should this memory be stored?". This layer answers the
broader product question "what did the rewrite do to the source?", typing the gate's
findings as ADDED / DROPPED / STRENGTHENED / REVERSED / CHANGED with the gate's own
evidence. Same checks, same verdict policy underneath: nothing here re-decides what the
gate decided, and a witness veto upstream removes the corresponding changes here.

Change types with no backing detector yet (ADDED, BROADENED, WEAKENED) are listed in
TransitionReport.not_checked instead of being silently absent. A report that only lists
what it found reads as "nothing else happened", which is the flattering direction.

There is no AMBIGUOUS verdict yet for the same reason there is no score: the
deterministic checks cannot currently produce one, and a state nothing can reach is
decoration, not reporting. It gets added when a detector can actually emit it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .core import check
from .report import Report

# Verdicts. UNCHECKABLE passes through from the gate and is never PRESERVED: failing to
# align the output with its source is not evidence the transformation was faithful.
PRESERVED, DRIFTED, UNCHECKABLE = "PRESERVED", "DRIFTED", "UNCHECKABLE"

# One source of truth for how gate checks read as transformations. Keys must stay in
# lockstep with the checks core.check runs; tests assert the parity.
CHECK_TO_CHANGE = {
    "LAUNDERED": ("DROPPED", "attribution"),
    "MANUFACTURED_CONFIDENCE": ("STRENGTHENED", "certainty"),
    "POLARITY_CHANGED": ("REVERSED", "polarity"),
    "CONDITION_DROPPED": ("DROPPED", "condition"),
    "TEMPORAL_SCOPE_DROPPED": ("DROPPED", "temporal scope"),
    "BRITTLE": ("DROPPED", "supporting values"),
    "TRUNCATED": ("CHANGED", "numeric derivation"),
}

# Declared but undetected: shown on every report so absence of a finding is never
# mistaken for a finding of absence.
NOT_CHECKED = ("ADDED", "BROADENED", "WEAKENED")

# Units are checked only when the optional parser is installed; when it is not, the
# report says so instead of quietly narrowing its own coverage.
UNITS_HINT = "unit changes (pip install factwash[units])"

SUPPORTED_KINDS = ("memory_write",)


def units_available() -> bool:
    try:
        import quantulum3  # noqa: F401
        return True
    except ImportError:
        return False


def _units_changes(source: str, output: str) -> list:
    """Unit drift on values that survived: '5 mg' -> '5 g' (CHANGED) or '5 mg' -> bare
    '5' (DROPPED). Value-keyed on purpose: a quantity that vanished entirely is the
    brittle/truncated checks' territory, and flagging ordinary compression here would
    be the modifier-loss mistake again (fires on everything, discriminates nothing)."""
    from quantulum3 import classifier, parser

    # Heuristic disambiguation only. The ML path drags sklearn+stemming in (and crashes
    # if they are half-installed), and an ML disambiguator inside a deterministic
    # detector would be a judge with extra steps anyway.
    classifier.USE_CLF = False

    src_real = [q for q in parser.parse(source) if q.unit.name != "dimensionless"]
    if not src_real:
        return []
    names_by_value: dict = {}
    entities_by_value: dict = {}
    surface_by_value: dict = {}
    for q in src_real:
        key = round(q.value, 2)
        names_by_value.setdefault(key, set()).add(q.unit.name)
        entities_by_value.setdefault(key, set()).add(q.unit.entity.name)
        surface_by_value.setdefault(key, q.surface)

    changes = []
    for q in parser.parse(output):
        key = round(q.value, 2)
        if key not in names_by_value:
            continue
        src_surface = surface_by_value[key]
        if q.unit.name == "dimensionless":
            changes.append(Change("DROPPED", "unit", "warn",
                                  f"source '{src_surface}' stored as bare '{q.surface}'",
                                  "UNITS"))
        elif (q.unit.name not in names_by_value[key]
              and q.unit.entity.name in entities_by_value[key]):
            # Same entity, different unit: '5 mg' -> '5 g', dollars -> euros. A unit
            # whose ENTITY disagrees with the source's is skipped, not flagged: the
            # heuristic disambiguator resolves 'minutes' to minute-of-arc (angle) but
            # 'min' to time, and flagging that resolved '5 minutes' vs '5 min' as a
            # change. Cross-entity drift at the same value is overwhelmingly parser
            # noise; real rewrites change units within an entity. Known false negative:
            # a genuine cross-entity rewrite (minutes -> milliliters) is not flagged.
            changes.append(Change("CHANGED", "unit", "fail",
                                  f"source '{src_surface}' became '{q.surface}'",
                                  "UNITS"))
    return changes


@dataclass
class Change:
    type: str        # DROPPED | STRENGTHENED | REVERSED | CHANGED
    property: str    # attribution, certainty, polarity, condition, temporal scope, ...
    severity: str    # fail | warn | info, straight from the gate flag
    evidence: str    # the gate flag's evidence sentence, spans included
    check: str       # originating check, for tracing a change back to its detector


@dataclass
class TransitionReport:
    verdict: str
    changes: list = field(default_factory=list)
    kind: str = "memory_write"
    not_checked: tuple = NOT_CHECKED
    gate: Report | None = None      # the full underlying report, for audit

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "kind": self.kind,
            "changes": [vars(c) for c in self.changes],
            "not_checked": list(self.not_checked),
            "gate_verdict": self.gate.verdict if self.gate else None,
        }

    def render(self) -> str:
        lines = [f"verdict: {self.verdict}   (kind: {self.kind}, gate: "
                 f"{self.gate.verdict if self.gate else 'none'})"]
        for c in self.changes:
            lines.append(f"  {c.type:<13} {c.property:<16} {c.severity.upper()}")
            lines.append(f"      {c.evidence}")
        lines.append(f"  not checked: {', '.join(self.not_checked)}")
        return "\n".join(lines)


def _added_changes(source: str, output: str, backend) -> tuple:
    """Run the ADDED backend per memory sentence. Returns (changes, not_established,
    n_sentences); not_established counts cannot_tell + unusable + backend errors, all
    of which produce nothing and are declared on the report, never silently passed."""
    from .claims import sentences

    changes, not_established = [], 0
    sents = [x for x in sentences(output) if x.strip()]
    for sent in sents:
        try:
            reply = backend(source, sent)
        except Exception:  # noqa: BLE001 - a broken backend must not break the report
            not_established += 1
            continue
        support = reply.get("support")
        if support == "unsupported":
            closest = reply.get("closest") or [""]
            claim = sent if len(sent) <= 90 else sent[:87] + "..."
            changes.append(Change("ADDED", "unsupported claim", "fail",
                                  f"'{claim}' has no support in the source "
                                  f"(closest source text: '{closest[0]}')", "ADDED"))
        elif support != "supported":
            not_established += 1
    return changes, not_established, len(sents)


def inspect(source: str, output: str, kind: str = "memory_write",
            witness=None, added_backend=None) -> TransitionReport:
    """Type the changes an AI rewrite made to its source.

    Args:
        source: The text the output was produced from.
        output: The AI-generated rewrite (currently: a candidate memory).
        kind: Transformation kind. Only "memory_write" is implemented; other kinds
            raise rather than run checks calibrated for the wrong transformation.
        witness: Optional witness passed through to the gate (see core.check).
        added_backend: Optional callable ``(source, claim) -> dict`` (see
            factwash.added). When given, ADDED is checked per memory sentence and
            leaves ``not_checked``; sentences the backend could not establish are
            counted and declared instead of silently passing.

    Returns:
        TransitionReport with verdict PRESERVED | DRIFTED | UNCHECKABLE and one Change
        per gate flag, carrying the gate's evidence verbatim.
    """
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"unsupported kind {kind!r}; supported: {SUPPORTED_KINDS}")
    gate = check(source, output, witness=witness)

    changes = []
    for name, outcome in gate.outcomes.items():
        ctype, prop = CHECK_TO_CHANGE[name]
        for f in outcome.flags:
            changes.append(Change(ctype, prop, f.severity, f.evidence, name))

    extra = ()
    if added_backend is None:
        base = NOT_CHECKED
    else:
        base = tuple(t for t in NOT_CHECKED if t != "ADDED")
        added, not_established, n_sents = _added_changes(source, output, added_backend)
        changes.extend(added)
        if not_established:
            extra = (f"ADDED on {not_established} of {n_sents} sentences "
                     f"(backend could not establish)",)

    if units_available():
        try:
            changes.extend(_units_changes(source, output))
            not_checked = base + extra
        except Exception as e:  # noqa: BLE001 - third-party parser, unknown exception
            # surface; a detector must never take down the report. The failure is
            # declared on the report itself, which is the only log a caller reads.
            not_checked = base + extra + (f"unit changes (parser failed: {type(e).__name__})",)
    else:
        not_checked = base + extra + (UNITS_HINT,)

    # A units change found on a gate-UNCHECKABLE pair is still evidence of drift: the
    # value match that produced it is itself an alignment, so DRIFTED outranks
    # UNCHECKABLE here.
    if changes:
        verdict = DRIFTED
    elif gate.verdict == "UNCHECKABLE":
        verdict = UNCHECKABLE
    else:
        verdict = PRESERVED
    return TransitionReport(verdict=verdict, changes=changes, kind=kind, gate=gate,
                            not_checked=not_checked)
