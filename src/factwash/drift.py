"""Multi-hop drift: what a chain of rewrites did to the original, hop by hop.

Memories are not written once. Recursive summarization and consolidation rewrite the
same memory repeatedly, and the question a single-pair gate cannot answer is where in
the chain the stance was lost. ``drift(versions)`` runs the transformation view over
every adjacent pair and over the ends, then attributes each end-to-end change to the
first hop that shows it.

What the measurements behind this module found (probed before it was built):

* Within lexicon and alignment coverage, the gate COMPOSES: the first hop that drops a
  cue class's last cue fires, so an in-lexicon chain cannot launder gradually past a
  per-write gate. The composition tests pin this on the probe chains.
* Chains escape by decaying ALIGNMENT, not by passing: successive paraphrase makes hops
  UNCHECKABLE, and an unverifiable chain is where laundering hides. A chain that loses
  checkability is therefore reported loudly, not folded into "no findings".
* Class-straddling cues ("reportedly" reads as hedge and attribution at once) DELAY a
  loss rather than hide it: the certainty strengthening surfaces only at the hop where
  the straddling cue finally drops, and both checks fire there together. A change no
  hop shows (possible when end-to-end alignment picks a different source sentence than
  the hop path did) is reported as "only visible end-to-end" rather than being
  force-attributed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .transform import TransitionReport, inspect

BLOCKING = ("REWRITE", "REJECT")


@dataclass
class DriftReport:
    versions: int
    hops: list                      # TransitionReport per adjacent pair
    end_to_end: TransitionReport
    hop_of: dict = field(default_factory=dict)   # (type, property) -> 1-based hop, or None

    @property
    def checkability_lost_at(self) -> int | None:
        """First 1-based hop whose gate verdict is UNCHECKABLE, else None."""
        for i, hop in enumerate(self.hops, 1):
            if hop.gate.verdict == "UNCHECKABLE":
                return i
        return None

    @property
    def gradual(self) -> bool:
        """True when the ends launder but a per-write gate would have passed every hop.
        Not observed on any in-lexicon chain (the composition property), but computed
        rather than assumed so alignment-decay or lexicon-gap chains can set it."""
        if self.end_to_end.gate.verdict not in BLOCKING:
            return False
        return all(h.gate.verdict not in BLOCKING for h in self.hops)

    def to_dict(self) -> dict:
        return {
            "versions": self.versions,
            "hops": [h.to_dict() for h in self.hops],
            "end_to_end": self.end_to_end.to_dict(),
            "change_attribution": [
                {"type": t, "property": p, "hop": hop}
                for (t, p), hop in self.hop_of.items()],
            "checkability_lost_at_hop": self.checkability_lost_at,
            "gradual_laundering": self.gradual,
        }

    def render(self) -> str:
        lines = [f"drift across {self.versions} versions ({len(self.hops)} hops)"]
        for i, hop in enumerate(self.hops, 1):
            summary = ", ".join(sorted({f"{c.type} {c.property}" for c in hop.changes})) or "-"
            lines.append(f"  hop {i:>2}  {hop.verdict:11} (gate: {hop.gate.verdict:15}) {summary}")
        lines.append(f"  end-to-end  {self.end_to_end.verdict} (gate: {self.end_to_end.gate.verdict})")
        for c in self.end_to_end.changes:
            hop = self.hop_of.get((c.type, c.property))
            where = f"hop {hop}" if hop else "only visible end-to-end"
            lines.append(f"      {c.type:13} {c.property:16} <- {where}")
        lost = self.checkability_lost_at
        if lost is not None:
            lines.append(f"  CHECKABILITY LOST at hop {lost}: from there the chain cannot be "
                         f"verified against its origin, which is where laundering hides")
        if self.gradual:
            lines.append("  GRADUAL LAUNDERING: the ends launder but a per-write gate would "
                         "have passed every hop")
        return "\n".join(lines)


def drift(versions) -> DriftReport:
    """Trace a memory's version history. versions[0] is the origin (the source, or the
    first stored form); each later entry is the next rewrite of the same memory."""
    versions = list(versions)
    if len(versions) < 2:
        raise ValueError("drift needs at least two versions (origin and one rewrite)")
    hops = [inspect(versions[i], versions[i + 1]) for i in range(len(versions) - 1)]
    end = inspect(versions[0], versions[-1])
    hop_of = {}
    for c in end.changes:
        key = (c.type, c.property)
        hop_of[key] = next((i for i, h in enumerate(hops, 1)
                            if any((hc.type, hc.property) == key for hc in h.changes)),
                           None)
    return DriftReport(versions=len(versions), hops=hops, end_to_end=end, hop_of=hop_of)
