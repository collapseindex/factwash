"""mem0-style wrapper: gate every write in one line.

Mechanics honesty (README says this too): mem0's ``.add()`` runs its own LLM extraction
internally, so the candidate memory does not exist at intercept time. This wrapper is
store-then-evict: add, inspect what the store extracted, delete or rewrite what fails the
gate, and report what happened. The client is duck-typed (needs ``.add()`` returning
``{"results": [{"id", "memory", ...}]}`` and ``.delete(id)``), so any mem0-shaped store works.
"""
from __future__ import annotations

import logging

from .core import check
from .fixer import fix

logger = logging.getLogger(__name__)

_GATED_VERDICTS = ("REJECT", "REWRITE")
# Events that write text into the store and therefore need gating. DELETE and NONE
# carry nothing to launder. mem0 2.0.7 only emits ADD, but an UPDATE that rewrites a
# stored memory can launder it just as easily, and assuming otherwise was a
# version-dependent bet hidden under a confident sentence in the README.
_WRITING_EVENTS = (None, "ADD", "UPDATE")


def _to_text(messages) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, dict):
        messages = [messages]
    return "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)


class GatedMemory:
    """Duck-typed gate around a mem0-style client. Unknown attributes pass through."""

    def __init__(self, client, fix: bool = False, fix_model: str | None = None,
                 witness=None, _chat=None):
        self._client = client
        self._fix = fix
        self._fix_model = fix_model
        self._witness = witness
        self._chat = _chat  # test injection for the fixer

    def __getattr__(self, name):
        return getattr(self._client, name)

    def add(self, messages, **kwargs):
        source = _to_text(messages)
        raw = self._client.add(messages, **kwargs)
        results = raw.get("results", raw) if isinstance(raw, dict) else raw
        kept, gate_log = [], []
        for r in results:
            text = r.get("memory") or r.get("text") or ""
            if r.get("event") not in _WRITING_EVENTS or not text:
                kept.append(r)  # deletes/none: nothing written, nothing to gate
                continue
            report = check(source, text, witness=self._witness)
            entry = {"id": r.get("id"), "memory": text, "verdict": report.verdict,
                     "flags": [f.name for f in report.flags if f.severity != "info"],
                     "action": "kept"}
            if report.verdict == "UNCHECKABLE":
                # Kept, but never call this verified. No stored claim matched a source
                # claim, so the gate could not look -- reporting it as "kept" alongside
                # genuinely-passing writes would launder the gate's own uncertainty.
                entry["action"] = "kept_unchecked"
                kept.append(r)
            elif report.verdict in _GATED_VERDICTS:
                self._evict(r, entry, source, text, kwargs)
            else:
                kept.append(r)
            gate_log.append(entry)
        return {"results": kept, "factwash": gate_log}

    def _evict(self, result, entry, source, text, add_kwargs):
        memory_id = result.get("id")
        if memory_id is not None:
            try:
                self._client.delete(memory_id)
            except Exception as e:  # store already dropped it, or API hiccup: report, don't crash the app
                logger.warning("factwash: delete(%s) failed: %s", memory_id, e)
        entry["action"] = "deleted"
        if not (self._fix and entry["verdict"] == "REWRITE"):
            return
        try:
            kw = {"model": self._fix_model} if self._fix_model else {}
            fixed = fix(source, text, _chat=self._chat, **kw)
        except RuntimeError as e:
            logger.warning("factwash: fix unavailable, write deleted instead: %s", e)
            return
        if fixed.verdict in ("PASS", "PASS_WITH_FLAGS"):
            readd_kwargs = {k: v for k, v in add_kwargs.items()
                            if k in ("user_id", "agent_id", "run_id", "metadata")}
            self._client.add(fixed.text, infer=False, **readd_kwargs)
            entry["action"] = "rewritten"
            entry["rewrite"] = fixed.text


def wrap(client, fix: bool = False, fix_model: str | None = None, witness=None) -> GatedMemory:
    """One-line adoption hook: ``memory = factwash.wrap(Memory())``."""
    return GatedMemory(client, fix=fix, fix_model=fix_model, witness=witness)
