"""Fix mode: the only place an LLM appears.

The judge is deterministic; the fixer is an optional LLM rewriter whose output must pass the
same deterministic judge. Both prompts are verbatim from the papers (marked below).
"""
from __future__ import annotations

from dataclasses import dataclass

from .checks import FAIL
from .core import check
from .report import REJECTING_CHECKS, Report

# Reclaim locating/writers.py::SOURCE_FIRST, verbatim
SOURCE_FIRST = ("You are compressing a work session into a short memory note for later. In {w} words or "
                "fewer, summarize it so a future assistant could REDO the final calculation from "
                "scratch. Preserve any rule, unit, rate, or fact needed to recompute the result. "
                "Write only the note.")

# Manufactured Confidence experiments/prompt_fix.py::HEDGEKEEP, verbatim
HEDGEKEEP = ("You maintain a long-term memory store. Extract durable facts from the user's message as "
             "short standalone statements (one per line), but PRESERVE the user's epistemic stance: if a "
             "claim was hedged, casual, attributed, or unverified (e.g. 'probably', 'a user mentioned', "
             "'rumor', 'last week'), keep that hedge in the stored statement; never upgrade a tentative "
             "claim into a settled fact.")

DEFAULT_MODEL = "claude-sonnet-5"
MAX_REWRITE_TOKENS = 300


@dataclass
class FixResult:
    text: str          # the memory to store (original if it already passed)
    verdict: str       # verdict of the stored text; REJECT if the rewrite still fails
    report: Report     # gate report for `text`
    prompt_used: str | None  # 'source_first' | 'hedgekeep' | None


def _anthropic_chat(model: str, client=None):
    if client is None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "fix mode needs the optional 'anthropic' dependency: "
                "pip install 'factwash[fix]' and set ANTHROPIC_API_KEY"
            ) from e
        client = anthropic.Anthropic()

    def chat(system: str, user: str) -> str:
        resp = client.messages.create(model=model, max_tokens=MAX_REWRITE_TOKENS, system=system,
                                      messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()

    return chat


def fix(source_context: str, candidate_memory: str, model: str = DEFAULT_MODEL,
        word_budget: int = 60, client=None, _chat=None) -> FixResult:
    """Rewrite a failing memory with the paper prompts, then re-gate the rewrite.

    A rewrite that still fails the gate is REJECTED, never stored. `_chat` injects a
    (system, user) -> str callable for tests; normal use goes through the Anthropic SDK.
    """
    report = check(source_context, candidate_memory)
    # UNCHECKABLE included on purpose: no claim was located, so there is nothing
    # to rewrite and an LLM pass would be guessing at what to preserve.
    if report.verdict in ("PASS", "PASS_WITH_FLAGS", "UNCHECKABLE"):
        return FixResult(candidate_memory, report.verdict, report, None)

    failed = {f.check for f in report.flags if f.severity == FAIL}
    if failed & REJECTING_CHECKS:
        system, prompt_used = SOURCE_FIRST.format(w=word_budget), "source_first"
    else:
        system, prompt_used = HEDGEKEEP, "hedgekeep"

    chat = _chat or _anthropic_chat(model, client)
    rewrite = chat(system, source_context)
    regate = check(source_context, rewrite)
    verdict = regate.verdict if regate.verdict in ("PASS", "PASS_WITH_FLAGS") else "REJECT"
    return FixResult(rewrite, verdict, regate, prompt_used)
