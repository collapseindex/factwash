"""The record checker: stance as a field, compared without a model and without needing
to recognise hedging in the rewrite at all."""
import pytest

import factwash
from factwash.record import check_record, parse_record

HEDGED = "Probably the API rate limit is 500 requests a minute; I'm going from memory here."
HEARSAY = "Someone said Alice was elevated this morning."
FLAT = "I set Alice's clearance to editor in the IAM console and saved it."


def rec(claim="X is true", source="the user", certainty="hedged", as_of="unspecified"):
    return (f"CLAIM: {claim}\nSOURCE: {source}\nCERTAINTY: {certainty}\nAS_OF: {as_of}")


# --- the case that motivated the module ------------------------------------------------
def test_controlled_vocabulary_is_read_as_stance():
    """'certainty: hedged' carries the source's hedge perfectly and contains no word a
    hedge lexicon knows. The prose gate flagged this; the record checker must not."""
    r = check_record(HEDGED, rec(certainty="hedged"))
    assert r.verdict == "PASS"


def test_certifying_a_hedged_source_fails():
    r = check_record(HEDGED, rec(certainty="asserted"))
    assert r.verdict == "REWRITE"
    assert any(f.name == "MANUFACTURED_CONFIDENCE" for f in r.flags)


def test_dropping_the_speaker_fails():
    r = check_record(HEARSAY, rec(source="unspecified", certainty="rumor", as_of="this morning"))
    assert r.verdict == "REWRITE"
    assert any(f.name == "LAUNDERED" for f in r.flags)


def test_a_flat_source_certified_as_asserted_passes():
    r = check_record(FLAT, rec(claim="Alice has editor clearance", source="direct observation",
                               certainty="asserted"))
    assert r.verdict == "PASS"


# --- malformed is not a pass ------------------------------------------------------------
def test_missing_retention_fields_are_malformed_not_pass():
    """A record without its retention fields was never written, so it cannot have passed.
    Same rule as UNCHECKABLE in the prose gate."""
    r = check_record(HEARSAY, "CLAIM: Alice is an administrator")
    assert r.verdict == "MALFORMED"
    assert set(r.missing) == {"SOURCE", "CERTAINTY", "AS_OF"}
    assert r.verdict != "PASS"


def test_empty_field_value_counts_as_missing():
    r = check_record(HEARSAY, "CLAIM: x\nSOURCE:\nCERTAINTY: rumor\nAS_OF: today")
    assert r.verdict == "MALFORMED" and "SOURCE" in r.missing


# --- parsing ----------------------------------------------------------------------------
def test_parse_tolerates_markdown_and_order():
    d = parse_record("- **AS_OF**: today\n# CLAIM: x\nSOURCE: bob\nCERTAINTY: rumor")
    assert d["CLAIM"] == "x" and d["AS_OF"] == "today" and d["SOURCE"] == "bob"


def test_unknown_certainty_value_warns_but_does_not_pass_silently():
    r = check_record(FLAT, rec(certainty="pretty sure", source="direct observation"))
    assert any(f.name == "CERTAINTY_UNRECOGNISED" for f in r.flags)
    assert r.verdict in ("PASS_WITH_FLAGS", "REWRITE")


def test_dict_input_works_like_text():
    a = check_record(HEDGED, rec(certainty="asserted")).verdict
    b = check_record(HEDGED, {"CLAIM": "X is true", "SOURCE": "the user",
                              "CERTAINTY": "asserted", "AS_OF": "unspecified"}).verdict
    assert a == b == "REWRITE"


def test_report_round_trips():
    d = check_record(HEARSAY, rec(source="unspecified", certainty="rumor")).to_dict()
    assert d["verdict"] == "REWRITE" and d["flags"] and d["record"]["CERTAINTY"] == "rumor"


def test_exported_from_package():
    assert hasattr(factwash, "check_record")
