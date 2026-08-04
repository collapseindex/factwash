"""The ADDED detector: reply validation (a witness that cannot point at the source is
a guess, and a guess never reaches a finding) and the transform-layer wiring with its
coverage accounting. All offline via fake backends; the live backend shares the parse."""
import pytest

import factwash
from factwash.added import UNUSABLE, parse_support

SOURCE = ("Mike asked Steve and Lynn whether logistics could build the weekly report. "
          "Dave will review the draft on Friday.")
FABRICATED = "Lynn works with Steve in logistics."


# --- parse_support validation ---------------------------------------------------------
def test_supported_with_valid_evidence_passes():
    r = parse_support('{"support": "supported", "evidence": ["Dave will review the draft"], "closest": []}',
                      SOURCE)
    assert r["support"] == "supported"


def test_unsupported_with_valid_closest_passes():
    r = parse_support('{"support": "unsupported", "evidence": [], "closest": ["whether logistics could build"]}',
                      SOURCE)
    assert r["support"] == "unsupported"


@pytest.mark.parametrize("reply,why", [
    ("no json here", "no JSON object"),
    ('{"support": "definitely"}', "unknown verdict"),
    ('{"support": "supported", "evidence": ["words not in the source"], "closest": []}',
     "fabricated evidence quote"),
    ('{"support": "supported", "evidence": [], "closest": []}',
     "supported without pointing at support"),
    ('{"support": "unsupported", "evidence": [], "closest": []}',
     "claims absence without proving it read the source"),
    ('{"support": "unsupported", "evidence": [], "closest": ["invented quote"]}',
     "closest quote not in source"),
])
def test_untrustworthy_replies_are_unusable(reply, why):
    assert parse_support(reply, SOURCE)["support"] is None, why


# --- transform wiring -----------------------------------------------------------------
def _backend(verdict, closest="Steve and Lynn"):
    def backend(source, claim):
        return {"support": verdict, "evidence": ["Dave will review"] if verdict == "supported" else [],
                "closest": [closest]}
    return backend


def test_unsupported_claim_becomes_an_added_change():
    r = factwash.inspect(SOURCE, FABRICATED, added_backend=_backend("unsupported"))
    added = [c for c in r.changes if c.check == "ADDED"]
    assert len(added) == 1
    assert (added[0].type, added[0].property, added[0].severity) == ("ADDED", "unsupported claim", "fail")
    assert "closest source text" in added[0].evidence
    assert r.verdict == "DRIFTED"
    assert "ADDED" not in r.not_checked


def test_supported_claims_produce_no_change_and_added_leaves_not_checked():
    r = factwash.inspect(SOURCE, "Dave will review the draft on Friday.",
                         added_backend=_backend("supported"))
    assert not [c for c in r.changes if c.check == "ADDED"]
    assert "ADDED" not in r.not_checked


def test_cannot_tell_is_declared_not_silently_passed():
    r = factwash.inspect(SOURCE, FABRICATED, added_backend=_backend("cannot_tell"))
    assert not [c for c in r.changes if c.check == "ADDED"]
    assert any("could not establish" in item for item in r.not_checked)


def test_raising_backend_is_declared_and_does_not_crash():
    def boom(source, claim):
        raise RuntimeError("backend died")
    r = factwash.inspect(SOURCE, FABRICATED, added_backend=boom)
    assert not [c for c in r.changes if c.check == "ADDED"]
    assert any("could not establish" in item for item in r.not_checked)


def test_without_backend_added_stays_declared_unchecked():
    r = factwash.inspect(SOURCE, FABRICATED)
    assert "ADDED" in r.not_checked


def test_added_composes_with_the_stance_checks():
    """The two directions fire together: hearsay laundered AND a fabricated specific."""
    src = "Someone said Alice may get access next week. Mike asked about the report."
    mem = "Alice has access. Lynn approved the report."
    def backend(source, claim):
        if "Lynn" in claim:
            return {"support": "unsupported", "evidence": [], "closest": ["Mike asked about the report"]}
        return {"support": "supported", "evidence": ["Alice may get access"], "closest": []}
    r = factwash.inspect(src, mem, added_backend=backend)
    kinds = {c.check for c in r.changes}
    assert "ADDED" in kinds
    assert kinds & {"LAUNDERED", "MANUFACTURED_CONFIDENCE"}


def test_quotes_survive_line_breaks_and_curly_apostrophes():
    """Sources are raw email: wrapping falls mid-sentence and apostrophes are curly.
    Verbatim matching rejected 39 of 46 honest replies on the blind corpus before this
    normalization; quote validation must care about the words, not the wrapping."""
    wrapped = "The meeting is on\nNovember 5 and it\u2019s mandatory for the ops team."
    r = parse_support(
        '{"support": "supported", "evidence": ["on November 5 and it\'s mandatory"], "closest": []}',
        wrapped)
    assert r["support"] == "supported"


def test_fabricated_quotes_still_die_after_normalization():
    wrapped = "The meeting is on\nNovember 5."
    r = parse_support(
        '{"support": "supported", "evidence": ["November 6 works too"], "closest": []}',
        wrapped)
    assert r["support"] is None
