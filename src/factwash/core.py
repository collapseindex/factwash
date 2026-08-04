"""The gate: factwash.check(source_context, candidate_memory) -> Report."""
from __future__ import annotations

from .checks import (check_brittle, check_condition, check_dehedged, check_laundered,
                     check_polarity, check_temporal, check_truncated)
from .claims import strip_roles, validate_text
from .report import Report, decide
from .witness import apply_veto


def check(source_context: str, candidate_memory: str, witness=None) -> Report:
    """Run the seven deterministic checks on a candidate memory against its source.

    Args:
        source_context: The session/transcript the memory was written from. Role labels
            ('User:', 'Assistant:') are stripped before analysis.
        candidate_memory: The memory text about to be stored.

    Args (continued):
        witness: optional callable (sentence) -> {"hedged", "attributed", "markers"}.
            When given, a FLAGGED write is re-checked and the flag is dropped if the
            memory preserved its stance in wording the lexicon does not know. It can
            only lower a verdict. See factwash.witness.anthropic_witness.

    Returns:
        Report with verdict PASS | PASS_WITH_FLAGS | REWRITE | REJECT and per-check outcomes
        (including N/A for checks that could not apply; N/A never counts as a pass).
    """
    source = strip_roles(validate_text("source_context", source_context))
    memory = validate_text("candidate_memory", candidate_memory)
    outcomes = {o.check: o for o in (
        check_brittle(source, memory),
        check_truncated(source, memory),
        check_dehedged(source, memory),
        check_laundered(source, memory),
        check_polarity(source, memory),
        check_condition(source, memory),
        check_temporal(source, memory),
    )}
    report = Report(verdict=decide(outcomes), outcomes=outcomes)

    # Optional, opt-in, and strictly a downgrade. Without a witness this function is
    # exactly what it has always been: deterministic, offline, zero-dependency.
    if witness is not None:
        vetoed, detail = apply_veto(report, memory, witness)
        report.witness = detail
        if vetoed:
            report.verdict = "PASS"
            report.vetoed_flags = [f.name for f in report.flags if f.severity == "fail"]
    return report
