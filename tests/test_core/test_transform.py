"""The transformation layer: typed changes over the gate, and the honesty guarantees
(UNCHECKABLE is not PRESERVED; undetected change types are declared, not omitted;
the mapping cannot silently drift from the checks the gate actually runs)."""
import pytest

import factwash
from factwash.transform import CHECK_TO_CHANGE, NOT_CHECKED

HERO_SOURCE = "According to Jason, Alice may have access to the test server until Friday."
HERO_MEMORY = "Alice has server access."


# --- the hero example -----------------------------------------------------------------------------
def test_hero_example_types_the_three_losses():
    r = factwash.inspect(HERO_SOURCE, HERO_MEMORY)
    assert r.verdict == "DRIFTED"
    got = {(c.type, c.property) for c in r.changes}
    assert ("DROPPED", "attribution") in got
    assert ("STRENGTHENED", "certainty") in got
    assert ("DROPPED", "temporal scope") in got


def test_broadening_is_not_claimed_on_the_hero_example():
    """'test server' -> 'server' IS a broadening, and no detector exists for it yet.
    The report must say so via not_checked instead of quietly finding nothing."""
    r = factwash.inspect(HERO_SOURCE, HERO_MEMORY)
    assert all(c.type != "BROADENED" for c in r.changes)
    assert "BROADENED" in r.not_checked
    assert "ADDED" in r.not_checked


def test_changes_carry_the_gate_evidence_verbatim():
    r = factwash.inspect(HERO_SOURCE, HERO_MEMORY)
    dropped = next(c for c in r.changes if c.property == "attribution")
    assert "according" in dropped.evidence.lower()
    assert dropped.check == "LAUNDERED"


# --- verdict semantics ----------------------------------------------------------------------------
def test_uncheckable_is_not_preserved():
    r = factwash.inspect("The vendor ships the beta on Monday.", "User prefers dark mode.")
    assert r.verdict == "UNCHECKABLE"
    assert r.changes == []


def test_faithful_write_is_preserved():
    r = factwash.inspect("I think the deploy might be risky.",
                     "User thinks the deploy might be risky.")
    assert r.verdict == "PRESERVED"
    assert r.changes == []


def test_report_round_trips_to_dict():
    d = factwash.inspect(HERO_SOURCE, HERO_MEMORY).to_dict()
    assert d["verdict"] == "DRIFTED"
    assert d["gate_verdict"] == "REWRITE"
    assert d["not_checked"] == list(NOT_CHECKED)
    assert all({"type", "property", "severity", "evidence", "check"} <= set(c) for c in d["changes"])


# --- the mapping cannot drift from the gate -------------------------------------------------------
def test_mapping_covers_exactly_the_checks_the_gate_runs():
    """A check renamed or added in core without a mapping entry must fail loudly here,
    not silently drop out of transformation reports."""
    gate = factwash.check("some source text", "some memory text")
    assert set(CHECK_TO_CHANGE) == set(gate.outcomes)


def test_unsupported_kind_raises_instead_of_pretending():
    with pytest.raises(ValueError):
        factwash.inspect(HERO_SOURCE, HERO_MEMORY, kind="summary")


# --- units (optional detector, quantulum3 behind factwash[units]) -------------------------------------
quantulum3 = pytest.importorskip("quantulum3")


def test_unit_changed_is_a_fail():
    r = factwash.inspect("The dose is 5 mg daily.", "The dose is 5 g daily.")
    got = [(c.type, c.property, c.severity) for c in r.changes if c.check == "UNITS"]
    assert ("CHANGED", "unit", "fail") in got
    assert r.verdict == "DRIFTED"


def test_unit_dropped_to_bare_number_is_a_warn():
    r = factwash.inspect("The dose is 5 mg daily.", "The dose is 5 daily.")
    got = [(c.type, c.property, c.severity) for c in r.changes if c.check == "UNITS"]
    assert ("DROPPED", "unit", "warn") in got


def test_same_unit_does_not_fire():
    r = factwash.inspect("The dose is 5 mg daily.", "Dose: 5 mg daily.")
    assert not [c for c in r.changes if c.check == "UNITS"]


def test_vanished_quantity_is_out_of_scope_for_units():
    """A dropped value entirely is brittle/truncated territory; the units detector
    firing on ordinary compression would be the modifier-loss mistake again."""
    r = factwash.inspect("The dose is 5 mg daily, taken with food.", "Dose is taken with food.")
    assert not [c for c in r.changes if c.check == "UNITS"]


def test_hero_example_produces_no_unit_changes():
    r = factwash.inspect(HERO_SOURCE, HERO_MEMORY)
    assert not [c for c in r.changes if c.check == "UNITS"]


def test_abbreviated_same_unit_does_not_fire():
    """'5 minutes' -> '5 min'. The heuristic disambiguator resolves these to different
    ENTITIES (minute-of-arc vs time), which is parser noise, not a rewrite. Caught by
    the stress probe; pinned so nobody re-broadens the rule without meeting this case."""
    r = factwash.inspect("It takes 5 minutes.", "It takes 5 min.")
    assert not [c for c in r.changes if c.check == "UNITS"]


def test_time_unit_change_still_fires():
    r = factwash.inspect("Timeout is 30 seconds.", "Timeout is 30 minutes.")
    got = [(c.type, c.severity) for c in r.changes if c.check == "UNITS"]
    assert ("CHANGED", "fail") in got


def test_parser_failure_degrades_to_declared_not_checked(monkeypatch):
    from factwash import transform

    def boom(source, output):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(transform, "_units_changes", boom)
    r = transform.inspect("The dose is 5 mg.", "The dose is 5 g.")
    assert any("parser failed" in item for item in r.not_checked)


def test_missing_parser_is_declared_not_silent(monkeypatch):
    from factwash import transform
    monkeypatch.setattr(transform, "units_available", lambda: False)
    r = transform.inspect("The dose is 5 mg daily.", "The dose is 5 g daily.")
    assert any("units" in item for item in r.not_checked)
    assert not [c for c in r.changes if c.check == "UNITS"]
