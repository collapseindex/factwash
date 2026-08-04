"""factwash bench: score a memory system on how much it launders.

Feed it the (source, memory) pairs a memory system produced; every write goes through
the gate and the bench aggregates. The headline is the laundering rate: the share of
checkable writes whose verdict is REWRITE or REJECT, i.e. writes that dropped the
stance or the basis of what the source said.

Three honesty rules are load-bearing and pinned by tests:

1. The rate is a FLAG RATE, not a verified count of laundering, and it errs in BOTH
   directions. Bounded recall pushes it down: the gate catches 29% of phrasing outside
   its lexicons, so a system can launder in ways this bench cannot see, and a zero is
   never an acquittal. Imperfect precision pushes it up: roughly one flag in four is a
   false alarm on real extractor output (0.73 measured), so the reported rate is not a
   floor either. An earlier version of this docstring called it a lower bound, which was
   one-sided in the flattering direction for anyone using the bench to indict a system.
2. UNCHECKABLE writes are never in the denominator. A write the gate could not align
   with its source is reported, not folded into either side.
3. Scores are comparable only across runs on the SAME stimulus set. Laundering base
   rates are stimulus-dependent (measured: 55% of bad writes in conversational hearsay,
   7% in business email), so a run carries its stimulus id and comparing across ids is
   a category error the report warns about.

Two ways in: score a JSONL of pairs (any system that can dump its writes), or drive a
live adapter, a callable ``(source: str) -> list[str]`` returning the memories the
system wrote for that source. A mem0 adapter ships; MemGPT traces become a pairs file
via ``experiments/external/eval_memgpt.py``.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .core import check

BLOCKING = ("REWRITE", "REJECT")

CAVEATS = (
    "this is a FLAG RATE, not a verified laundering count, and it errs BOTH ways: "
    "bounded recall (29% on unfamiliar phrasing) hides laundering, so a zero is not an "
    "acquittal; imperfect precision (~1 flag in 4 is a false alarm on real output) "
    "means it is not a floor either",
    "comparable only across runs on the SAME stimulus set: laundering base rates are "
    "stimulus-dependent",
)


@dataclass
class BenchResult:
    n: int
    verdicts: dict            # verdict -> count, all five
    mechanisms: dict          # flag name -> count, fail and warn severities
    adapter_errors: int = 0   # sources the adapter failed on; declared, not silent
    stimuli_id: str | None = None
    gate_version: str = __version__
    caveats: tuple = CAVEATS

    @property
    def uncheckable(self) -> int:
        return self.verdicts.get("UNCHECKABLE", 0)

    @property
    def checkable(self) -> int:
        return self.n - self.uncheckable

    @property
    def laundering_count(self) -> int:
        return sum(self.verdicts.get(v, 0) for v in BLOCKING)

    @property
    def laundering_rate(self) -> float | None:
        """Share of checkable writes the gate FLAGS (REWRITE+REJECT). Not a verified
        laundering count: see CAVEATS, it errs in both directions. None when nothing was
        checkable, because 0/0 reported as 0.0 would read as a clean bill."""
        if self.checkable == 0:
            return None
        return self.laundering_count / self.checkable

    def to_dict(self) -> dict:
        return {
            "gate_version": self.gate_version,
            "stimuli_id": self.stimuli_id,
            "n_writes": self.n,
            "checkable": self.checkable,
            "uncheckable": self.uncheckable,
            "adapter_errors": self.adapter_errors,
            "laundering_count": self.laundering_count,
            "laundering_flag_rate": self.laundering_rate,
            "verdicts": dict(self.verdicts),
            "mechanisms": dict(self.mechanisms),
            "caveats": list(self.caveats),
        }

    def render(self) -> str:
        rate = self.laundering_rate
        rate_s = "n/a (nothing checkable)" if rate is None else (
            f"{rate:.0%}  ({self.laundering_count} of {self.checkable} checkable writes "
            f"REWRITE or REJECT)")
        lines = [
            f"factwash bench (gate v{self.gate_version}"
            + (f", stimuli: {self.stimuli_id}" if self.stimuli_id else "") + ")",
            f"  writes: {self.n}   checkable: {self.checkable}   "
            f"uncheckable: {self.uncheckable} (reported, never in the denominator)"
            + (f"   adapter errors: {self.adapter_errors}" if self.adapter_errors else ""),
            f"  laundering FLAG rate: {rate_s}",
            "  verdicts: " + "  ".join(f"{v} {c}" for v, c in sorted(self.verdicts.items())),
        ]
        if self.mechanisms:
            lines.append("  mechanisms: " + ", ".join(
                f"{name} {c}" for name, c in Counter(self.mechanisms).most_common()))
        lines.append("  caveats: " + " | ".join(self.caveats))
        return "\n".join(lines)


def score_pairs(pairs, stimuli_id: str | None = None,
                adapter_errors: int = 0) -> BenchResult:
    """Score (source, memory) pairs. Accepts dicts with source/memory keys or tuples."""
    verdicts: Counter = Counter()
    mechanisms: Counter = Counter()
    n = 0
    for pair in pairs:
        source, memory = ((pair["source"], pair["memory"]) if isinstance(pair, dict)
                          else (pair[0], pair[1]))
        report = check(source, memory)
        verdicts[report.verdict] += 1
        n += 1
        for f in report.flags:
            if f.severity in ("fail", "warn"):
                mechanisms[f.name] += 1
    return BenchResult(n=n, verdicts=dict(verdicts), mechanisms=dict(mechanisms),
                       adapter_errors=adapter_errors, stimuli_id=stimuli_id)


def run_adapter(adapter, sources) -> tuple[list[dict], int]:
    """Drive a live adapter over sources. Returns (pairs, error_count); a source the
    adapter raises on is counted and skipped, never silently dropped."""
    pairs, errors = [], 0
    for source in sources:
        try:
            memories = adapter(source)
        except Exception:
            errors += 1
            continue
        pairs.extend({"source": source, "memory": m} for m in memories if m)
    return pairs, errors


def mem0_adapter(user_id: str = "factwash-bench"):
    """Adapter for a live mem0 store: feeds each source through `.add()`, captures what
    mem0 extracted and stored, then deletes it so the bench leaves no residue.

    Requires `mem0` installed and configured (its extractor calls an LLM, so this makes
    network calls and costs money; the bench itself remains deterministic). mem0 runs
    its own extraction inside add(), which is exactly the transformation under test.
    """
    from mem0 import Memory  # lazy: clear ImportError if absent

    store = Memory()

    def adapter(source: str) -> list[str]:
        result = store.add(source, user_id=user_id) or {}
        written = [(r.get("id"), r.get("memory", "")) for r in result.get("results", [])
                   if r.get("event") == "ADD"]
        for mem_id, _ in written:
            if mem_id:
                store.delete(mem_id)
        return [text for _, text in written if text]

    return adapter


def load_pairs(path: Path):
    """Read a pairs JSONL: one {source, memory} object per line."""
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        obj = json.loads(line)
        if "source" not in obj or "memory" not in obj:
            raise ValueError(f"{path.name} line {i + 1}: needs 'source' and 'memory' keys")
        yield obj
