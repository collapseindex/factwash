"""Report and the hard-coded verdict policy. No scores, no weights: named flags and verdicts."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .checks import FAIL, NA, WARN, CheckOutcome

REJECTING_CHECKS = {"BRITTLE", "TRUNCATED", "POLARITY_CHANGED"}          # fail here -> memory is uncorrectable
REWRITING_CHECKS = {"MANUFACTURED_CONFIDENCE", "LAUNDERED", "CONDITION_DROPPED"}  # fail here -> stance is fixable

EXIT_CODES = {"PASS": 0, "PASS_WITH_FLAGS": 0, "REWRITE": 1, "REJECT": 2, "UNCHECKABLE": 3}


def decide(outcomes: dict[str, CheckOutcome]) -> str:
    """Map check outcomes to a verdict.

    UNCHECKABLE is not a pass. When no check could apply, the gate did not find this
    memory clean -- it failed to find anything to look at, usually because no stored
    claim matched a source claim. Collapsing that into PASS is the same mistake the
    package refuses elsewhere (N/A is never a pass at the check level), and it is the
    flattering direction: on 101 real extractor outputs, 7% landed here and would have
    been reported as verified-clean writes.
    """
    if all(o.status == NA for o in outcomes.values()):
        return "UNCHECKABLE"
    failed = {name for name, o in outcomes.items() if o.status == FAIL}
    if failed & REJECTING_CHECKS:
        return "REJECT"
    if failed & REWRITING_CHECKS:
        return "REWRITE"
    if any(o.status == WARN for o in outcomes.values()):
        return "PASS_WITH_FLAGS"
    return "PASS"


@dataclass
class Report:
    verdict: str
    outcomes: dict
    witness: dict | None = None        # why the witness did or did not veto
    vetoed_flags: list | None = None   # flags the witness overruled, kept for audit

    @property
    def flags(self) -> list:
        return [f for o in self.outcomes.values() for f in o.flags]

    @property
    def applicable(self) -> list[str]:
        return [name for name, o in self.outcomes.items() if o.status != NA]

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            **({"witness": self.witness} if self.witness else {}),
            **({"vetoed_flags": self.vetoed_flags} if self.vetoed_flags else {}),
            "checks_applied": len(self.applicable),
            "checks": {name: {"status": o.status, "note": o.note,
                              "flags": [asdict(f) for f in o.flags]}
                       for name, o in self.outcomes.items()},
        }

    def render(self) -> str:
        lines = [f"verdict: {self.verdict}   (checks applied: {len(self.applicable)} of {len(self.outcomes)})"]
        for name, o in self.outcomes.items():
            head = f"  {name:<24} {o.status}"
            if o.note:
                head += f"   {o.note}"
            lines.append(head)
            for f in o.flags:
                tag = "[EVIDENTIAL] " if f.evidential else ""
                lines.append(f"      {f.severity.upper()}: {tag}{f.evidence}")
                lines.append(f"      cite: {f.citation}")
        return "\n".join(lines)
