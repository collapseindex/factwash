"""Unit tests for the localization layer, N/A behavior, and the verdict policy."""
import pytest

from factwash.claims import (MAX_TEXT_CHARS, content_words, match_source_window, numbers,
                            sentences, strip_roles, validate_text)
from factwash.checks import CheckOutcome, check_brittle, check_dehedged, check_truncated
from factwash.report import decide
import factwash


# --- input validation -----------------------------------------------------------------------------
def test_validate_text_rejects_non_string():
    with pytest.raises(TypeError):
        validate_text("x", 42)


def test_validate_text_rejects_oversized():
    with pytest.raises(ValueError):
        validate_text("x", "a" * (MAX_TEXT_CHARS + 1))


# --- number extraction filters --------------------------------------------------------------------
def test_numbers_extracts_values_and_money():
    got = numbers("items are 12, 18, and $25.")
    assert [(n.value, n.is_money) for n in got] == [(12.0, False), (18.0, False), (25.0, True)]


def test_numbers_skips_labels_dates_years_versions():
    assert numbers("Q3 at 3pm on 2026-06-12 in 2026, app v0.3.34") == []


def test_role_labels_are_stripped():
    assert strip_roles("User: hello\nAssistant: hi") == "hello\nhi"


# --- matching -------------------------------------------------------------------------------------
def test_no_match_means_none_not_a_guess():
    assert match_source_window("Completely unrelated words here.",
                               sentences("The vendor ships Monday.")) is None


def test_window_includes_neighbors():
    win = match_source_window("Alice is an administrator.",
                              sentences("Alice is an administrator now; not sure though."))
    assert win is not None and "not sure" in win.lower()


# --- N/A is first-class ---------------------------------------------------------------------------
def test_no_derived_conclusion_is_na_not_pass():
    out = check_brittle("some source", "User prefers dark mode.")
    assert out.status == "n/a" and "no derived conclusion" in out.note


def test_stated_total_without_inputs_is_na():
    rep = factwash.check("User: The Q3 budget is $1,200 total. Plan around it.",
                        "Q3 budget: $1,200 total.")
    assert rep.outcomes["BRITTLE"].status == "n/a"
    assert rep.outcomes["TRUNCATED"].status == "n/a"
    assert rep.verdict == "PASS"


def test_uncertifiable_derivation_is_na():
    out = check_truncated("values were 10 and 20, average 15", "The average was 15.")
    assert out.status == "n/a"


def test_unmatched_memory_is_na_for_stance_checks():
    rep = factwash.check("User: totally different topic entirely.", "Alice is an admin.")
    assert rep.outcomes["MANUFACTURED_CONFIDENCE"].status == "n/a"
    assert rep.outcomes["LAUNDERED"].status == "n/a"


def test_questions_are_not_conclusions():
    out = check_brittle("items 12 and 18 total 30", "Was the total $30?")
    assert out.status == "n/a"


# --- verdict policy -------------------------------------------------------------------------------
def _o(check, status):
    return CheckOutcome(check, status)


def test_verdict_policy_mapping():
    assert decide({"BRITTLE": _o("BRITTLE", "fail")}) == "REJECT"
    assert decide({"TRUNCATED": _o("TRUNCATED", "fail"),
                   "LAUNDERED": _o("LAUNDERED", "fail")}) == "REJECT"
    assert decide({"MANUFACTURED_CONFIDENCE": _o("MANUFACTURED_CONFIDENCE", "fail")}) == "REWRITE"
    assert decide({"BRITTLE": _o("BRITTLE", "warn")}) == "PASS_WITH_FLAGS"
    # all-N/A is NOT a pass: the gate found nothing to look at.
    assert decide({"BRITTLE": _o("BRITTLE", "n/a")}) == "UNCHECKABLE"
    assert decide({"BRITTLE": _o("BRITTLE", "n/a"),
                   "LAUNDERED": _o("LAUNDERED", "pass")}) == "PASS"


def test_report_counts_applicable_checks():
    rep = factwash.check("unrelated source text entirely.", "Nothing checkable here at all.")
    assert len(rep.applicable) == 0
    assert rep.verdict == "UNCHECKABLE"      # not PASS: nothing was verified
    assert "checks applied: 0 of 7" in rep.render()


# --- de-hedging direction -------------------------------------------------------------------------
def test_hedge_kept_does_not_fire():
    out = check_dehedged("I think the deploy is Friday.", "Deploy is probably Friday.")
    assert out.status == "pass"


def test_hedge_stripped_fires():
    out = check_dehedged("I think the deploy is Friday.", "Deploy is Friday.")
    assert out.status == "fail"
