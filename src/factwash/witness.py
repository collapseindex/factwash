"""The optional LLM witness: perception only, never judgement.

The deterministic gate has 95% recall and 68% precision on real extractor output. Recall
was never the weakness; precision is, and roughly one flagged write in three is wrong.
This module fixes that, measured, by asking a model one narrow question about one
sentence and letting the answer *lower* a verdict, never raise one.

The separation is the point:

    the model    answers "does this sentence hedge? does it attribute?"
    Python       decides what that means for the verdict

Asking a model "is this laundering?" would hand it the decision and make this another
LLM judge. It is also why every quoted marker is validated against the text: a witness
who cannot point at the sentence is guessing, and a guess that reaches a verdict is
indistinguishable from a judge.

A witness is any callable ``(sentence: str) -> dict`` returning ``hedged``, ``attributed``
and ``markers``. That keeps this provider-agnostic and testable without a network:

    from factwash.witness import anthropic_witness
    report = factwash.check(source, memory, witness=anthropic_witness())
"""
from __future__ import annotations

import json
import re

TAGGER_SYSTEM = """You label ONE sentence for epistemic stance. You do not judge, compare, or decide anything.

Answer two questions about the sentence you are given:

hedged: does the sentence mark the claim as uncertain, tentative, unofficial, provisional,
  second-hand, or otherwise not established as fact?

attributed: does the sentence indicate the claim came from some person, group, channel, or
  document, rather than asserting it flatly on the speaker's own authority?

A sentence can be both, either, or neither. Judge only what the sentence itself says, by
its meaning rather than by any fixed list of words. Ordinary domain vocabulary is not
stance: a confident statement stays confident even when it happens to contain words that
look epistemic in other contexts.

Reply with ONLY this JSON and nothing else:
{"hedged": true/false, "attributed": true/false, "markers": ["the exact words that made you say yes"]}"""

# This prompt deliberately contains NO example idioms. An earlier version listed the exact
# phrasings from the held-out corpus because it was written while looking at the failures;
# it scored 100%, which measured the leak rather than the model. Stripping them gave the
# honest 93%. Do not "improve" this by adding examples from a corpus you are scoring on.

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 300
_JSON = re.compile(r"\{.*\}", re.DOTALL)

UNUSABLE = {"hedged": None, "attributed": None, "markers": []}


def parse_tag(reply_text: str, sentence: str) -> dict:
    """Validate a witness reply. Returns hedged/attributed as None when unusable.

    Unusable is not "no stance found". It means the answer cannot be trusted, so the
    caller keeps the deterministic verdict rather than acting on a guess.
    """
    match = _JSON.search(reply_text or "")
    if not match:
        return {**UNUSABLE, "error": "no JSON object in reply"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {**UNUSABLE, "error": "unparseable JSON"}

    hedged, attributed = data.get("hedged"), data.get("attributed")
    markers = [m for m in (data.get("markers") or []) if isinstance(m, str) and m.strip()]

    # A truthy string like "maybe" must not silently become a boolean.
    if not isinstance(hedged, bool) or not isinstance(attributed, bool):
        return {**UNUSABLE, "error": f"non-boolean verdict fields: {hedged!r}, {attributed!r}"}

    low = sentence.lower()
    ungrounded = [m for m in markers if m.strip().lower() not in low]
    if ungrounded:
        return {**UNUSABLE, "error": f"markers absent from the text: {ungrounded}"}
    if (hedged or attributed) and not markers:
        return {**UNUSABLE, "error": "positive verdict with no marker span"}

    return {"hedged": hedged, "attributed": attributed, "markers": markers}


def anthropic_witness(model: str = DEFAULT_MODEL, client=None):
    """A witness backed by Claude. Needs the optional `anthropic` dependency."""
    if client is None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "the witness needs the optional dependency: pip install 'factwash[fix]'"
            ) from e
        client = anthropic.Anthropic()

    def witness(sentence: str) -> dict:
        kwargs = {}
        if model in ("claude-sonnet-5", "claude-opus-5"):
            # These think by default and max_tokens caps thinking plus text together,
            # which returns empty output on a small budget. Labelling is not a
            # reasoning task, so it is switched off rather than paid for.
            kwargs["thinking"] = {"type": "disabled"}
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=TAGGER_SYSTEM,
            messages=[{"role": "user", "content": sentence}], **kwargs,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return parse_tag(text, sentence)

    return witness


def apply_veto(report, memory: str, witness) -> tuple[bool, dict]:
    """Ask the witness whether a FLAGGED memory actually preserved its stance.

    Returns (vetoed, detail). Only ever downgrades: if the memory carries stance the
    lexicon did not recognise ("User believes ...", "status: unconfirmed"), the flag was
    a false positive. An unusable answer changes nothing.

    Runs only on flagged writes, which is where the errors are: the deterministic layer
    is 95% recall and 68% precision, so escalating on PASS would buy almost nothing.
    """
    if report.verdict not in ("REWRITE", "REJECT") or not memory.strip():
        return False, {"reason": "not a flagged write"}
    try:
        tag = witness(memory)
    except Exception as e:                       # a broken witness must not break the gate
        return False, {"reason": f"witness raised: {e!r}"}
    if tag.get("hedged") is None:
        return False, {"reason": tag.get("error", "unusable witness reply"), "tag": tag}
    if tag["hedged"] or tag["attributed"]:
        return True, {"reason": "stance preserved in wording the lexicon missed", "tag": tag}
    return False, {"reason": "witness agrees the stance is gone", "tag": tag}
