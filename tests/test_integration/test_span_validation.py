"""The witness must be able to point at the text it is reporting on.

The whole design rests on the model being a witness rather than a judge. A witness that
reports a hedge it cannot quote is guessing, and a guess that reaches the verdict is
indistinguishable from an LLM judge. These tests use a fake chat callable, so no network
and no spend.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments"))

from runlog import Budget  # noqa: E402
from stance_tagger import tag  # noqa: E402


class FakeAgent:
    """Returns a canned reply, so the validator is what is under test."""

    def __init__(self, payload):
        self.payload = payload

    def chat(self, model, system, user, max_tokens):
        class Reply:
            text = self.payload

            class cost:
                usd = 0.0
        return Reply()


def run(payload, sentence="Someone said Alice was promoted."):
    return tag(FakeAgent(payload), "fake", sentence, Budget(cap_usd=1.0))


def test_a_grounded_tag_is_accepted():
    out = run('{"hedged": false, "attributed": true, "markers": ["Someone said"]}')
    assert out["attributed"] is True
    assert "parse_error" not in out


def test_a_marker_absent_from_the_text_invalidates_the_tag():
    """The failure this exists for: the model reports a hedge that is not there."""
    out = run('{"hedged": true, "attributed": true, "markers": ["allegedly"]}')
    assert out["hedged"] is None, "a hallucinated span must not reach the verdict"
    assert "not present in the text" in out["parse_error"]


def test_a_positive_verdict_with_no_span_is_rejected():
    out = run('{"hedged": true, "attributed": false, "markers": []}')
    assert out["hedged"] is None
    assert "no marker span" in out["parse_error"]


def test_a_negative_verdict_needs_no_span():
    """Nothing to cite is correct when the answer is 'no stance here'."""
    out = run('{"hedged": false, "attributed": false, "markers": []}',
              sentence="The batch job writes one row per order.")
    assert out["hedged"] is False and out["attributed"] is False
    assert "parse_error" not in out


def test_non_boolean_fields_are_malformed_not_falsy():
    """"maybe" must not quietly become False and be trusted."""
    out = run('{"hedged": "maybe", "attributed": true, "markers": ["Someone said"]}')
    assert out["hedged"] is None
    assert "non-boolean" in out["parse_error"]


def test_unparseable_output_is_unusable_rather_than_assumed_clean():
    out = run("I think this sentence is fine, honestly.")
    assert out["hedged"] is None


def test_span_matching_ignores_case_and_padding():
    out = run('{"hedged": false, "attributed": true, "markers": ["  SOMEONE SAID "]}')
    assert out["attributed"] is True
