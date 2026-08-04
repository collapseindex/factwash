"""Factwash (That's What Source Said): a write-time gate for AI memory.

Checks a candidate memory against its source and rejects or rewrites memories that would
become uncorrectable (source dropped) or falsely confident (hedge stripped, attribution
laundered). The judge is deterministic; the optional fixer is an LLM rewriter whose output
must pass the same deterministic judge.
"""
__version__ = "0.5.0"

from .added import anthropic_added_witness
from .checks import CheckOutcome, Flag
from .core import check
from .fixer import FixResult, fix
from .record import RecordReport, check_record, parse_record
from .report import Report
from .surface import surface_scan
from .drift import DriftReport, drift
from .transform import Change, TransitionReport, inspect
from .witness import anthropic_witness, apply_veto, parse_tag
from .wrap import GatedMemory, wrap


def bench(pairs, stimuli_id=None):
    """Score the (source, memory) pairs a memory system produced. See factwash.bench."""
    from .bench import score_pairs
    return score_pairs(pairs, stimuli_id=stimuli_id)


__all__ = ["check", "check_record", "fix", "wrap", "surface_scan", "inspect", "bench",
           "parse_record", "RecordReport", "Report", "Flag",
           "CheckOutcome", "FixResult", "GatedMemory", "Change", "TransitionReport",
           "drift", "DriftReport",
           "anthropic_witness", "anthropic_added_witness", "apply_veto", "parse_tag",
           "__version__"]
