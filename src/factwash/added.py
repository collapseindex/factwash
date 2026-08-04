"""The ADDED detector: does the memory claim anything the source does not support?

This is the quadrant the seven checks structurally cannot see. The gate asks whether
what was in the source SURVIVED; ADDED asks the opposite direction, whether what is in
the memory was EVER THERE. On the blind labelled corpus, 27 of 29 bad writes were
wrong, invented or inferred claims: this detector's territory, not the gate's.

Same constitution as the stance witness, adapted for the comparative question:

* The model answers a three-way question about ONE memory sentence against the source:
  supported / unsupported / cannot_tell (the RefChecker entailment discipline: judge
  only against the provided text, never from world knowledge).
* Every answer must point at the source. "supported" must quote the supporting words;
  "unsupported" must quote the CLOSEST words the source has on the topic, which proves
  the model read the source before claiming absence. Quotes are validated verbatim
  against the source; an answer that cannot point is unusable and produces nothing.
* cannot_tell and unusable are never findings and never passes. They are counted and
  declared on the report.
* The backend is any callable ``(source, claim) -> dict``, so it is provider-agnostic
  and testable offline. ``anthropic_added_witness()`` ships as the default.
"""
from __future__ import annotations

import json
import re

SUPPORT_SYSTEM = """You check ONE claim against a SOURCE text. You do not use your own knowledge, only the source.

Answer: is the claim supported by what the source says?

- "supported": the source states it or directly entails it. Quote the exact source words that support it in "evidence".
- "unsupported": the source does not state or entail it (including relationships, roles, and specifics the source never asserts). Quote the exact source words CLOSEST to the claim's topic in "closest", so it is clear you read the source.
- "cannot_tell": the source is genuinely ambiguous about it.

A claim can be on-topic and still unsupported: mentioning the same people is not asserting the same relationship. Judge what the source SAYS, not what is plausible.

Reply with ONLY this JSON and nothing else:
{"support": "supported" | "unsupported" | "cannot_tell", "evidence": ["exact source words"], "closest": ["exact source words"]}"""

# No example claims and no example sources, for the same reason the stance witness has
# no example idioms: an earlier prompt in this repo scored a fake 100% by listing the
# held-out phrasings it was scored on.

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 400
_JSON = re.compile(r"\{.*\}", re.DOTALL)

UNUSABLE = {"support": None, "evidence": [], "closest": []}
VERDICTS = ("supported", "unsupported", "cannot_tell")


def _norm(text: str) -> str:
    """Whitespace- and apostrophe-normalized lowercase, for quote validation only.

    Sources are raw email: line breaks fall mid-sentence and apostrophes are curly, so
    verbatim substring matching rejected honest quotes wholesale (measured: 39 of 46
    dead replies on the blind corpus were exactly this). Validation still requires the
    words in order from the source; it just stops caring how they were wrapped."""
    return " ".join(text.replace("’", "'").replace("‘", "'")
                    .replace("“", '"').replace("”", '"').split()).lower()


def parse_support(reply_text: str, source: str) -> dict:
    """Validate a support reply. support=None means the answer cannot be trusted.

    The asymmetry is deliberate: "supported" must ground its evidence in the source,
    and "unsupported" must ground its `closest` quote in the source. Either way a reply
    that cannot point at the text is a guess, and a guess never reaches a finding.
    """
    match = _JSON.search(reply_text or "")
    if not match:
        return {**UNUSABLE, "error": "no JSON object in reply"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {**UNUSABLE, "error": "unparseable JSON"}

    support = data.get("support")
    if support not in VERDICTS:
        return {**UNUSABLE, "error": f"support not one of {VERDICTS}: {support!r}"}

    low = _norm(source)
    evidence = [q for q in (data.get("evidence") or []) if isinstance(q, str) and q.strip()]
    closest = [q for q in (data.get("closest") or []) if isinstance(q, str) and q.strip()]
    bad = [q for q in evidence + closest if _norm(q) not in low]
    if bad:
        return {**UNUSABLE, "error": f"quotes absent from the source: {bad}"}
    if support == "supported" and not evidence:
        return {**UNUSABLE, "error": "supported with no evidence quote"}
    if support == "unsupported" and not closest:
        return {**UNUSABLE, "error": "unsupported with no closest quote (did it read the source?)"}

    return {"support": support, "evidence": evidence, "closest": closest}


def anthropic_added_witness(model: str = DEFAULT_MODEL, client=None):
    """An ADDED backend backed by Claude. Needs the optional `anthropic` dependency.
    One call per memory sentence, source included each time; sends data to the
    configured provider, so like every model component it is strictly opt-in."""
    if client is None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "the ADDED witness needs the optional dependency: pip install 'factwash[fix]'"
            ) from e
        client = anthropic.Anthropic()

    def backend(source: str, claim: str) -> dict:
        kwargs = {}
        if model in ("claude-sonnet-5", "claude-opus-5"):
            kwargs["thinking"] = {"type": "disabled"}
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=SUPPORT_SYSTEM,
            messages=[{"role": "user",
                       "content": f"SOURCE:\n{source}\n\nCLAIM:\n{claim}"}], **kwargs,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return parse_support(text, source)

    return backend
