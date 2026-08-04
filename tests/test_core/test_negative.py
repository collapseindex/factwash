"""Negative tests: prove the checkers are load-bearing by breaking them.

An under-powered checker produces a confident null; these tests make sure detection flows
through the machinery we think it does (lexicons, cues), and that breaking a clean pair
makes the gate fire.
"""
import factwash
from factwash import lexicons as lex

SRC_MC = "User: I think Alice might be an admin at this point."
MEM_MC = "Alice is an admin."
SRC_55 = "User: The line items are 12, 18, and 25.\nAssistant: The total comes to $55."
MEM_55 = "The total was $55."


def test_hedge_lexicon_is_load_bearing(monkeypatch):
    assert factwash.check(SRC_MC, MEM_MC).verdict == "REWRITE"  # fires intact
    monkeypatch.setattr(lex, "HEDGE", ())
    rep = factwash.check(SRC_MC, MEM_MC)
    assert "MANUFACTURED_CONFIDENCE" not in {f.name for f in rep.flags}


def test_attrib_lexicon_is_load_bearing(monkeypatch):
    src, mem = "According to Dana, the vendor ships Monday.", "The vendor ships Monday."
    assert factwash.check(src, mem).verdict == "REWRITE"
    monkeypatch.setattr(lex, "ATTRIB", ())
    assert "LAUNDERED" not in {f.name for f in factwash.check(src, mem).flags}


def test_aggregate_cues_are_load_bearing(monkeypatch):
    assert factwash.check(SRC_55, MEM_55).verdict == "REJECT"
    monkeypatch.setattr(lex, "AGGREGATE_CUES", ())
    rep = factwash.check(SRC_55, MEM_55)
    assert rep.outcomes["BRITTLE"].status == "n/a"


def test_breaking_a_clean_pair_makes_the_gate_fire():
    clean_src = "The vendor ships Monday."
    clean_mem = "The vendor ships Monday."
    assert factwash.check(clean_src, clean_mem).verdict == "PASS"
    broken_src = "Rumor has it the vendor ships Monday."
    rep = factwash.check(broken_src, clean_mem)
    assert rep.verdict == "REWRITE"
    assert {f.name for f in rep.flags} >= {"MANUFACTURED_CONFIDENCE"}
