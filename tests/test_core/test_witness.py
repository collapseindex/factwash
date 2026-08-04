"""The witness as shipped: opt-in, downgrade-only, and safe when it misbehaves.

No network. A witness is any callable, so every case here injects a fake one and the
tests assert on the package's own behaviour rather than on a model's.
"""
import factwash
from factwash.witness import apply_veto, parse_tag

SOURCE = "Per the IAM system of record, Alice has editor clearance."
MEMORY = "Alice clearance is editor (set in IAM console)."


def stance(hedged=False, attributed=False, markers=None):
    return lambda sentence: {"hedged": hedged, "attributed": attributed,
                             "markers": markers or []}


# --- the default path is unchanged ----------------------------------------------------
def test_check_without_a_witness_is_untouched():
    """The deterministic gate must stay deterministic, offline and dependency-free."""
    report = factwash.check(SOURCE, MEMORY)
    assert report.verdict == "REWRITE"
    assert report.witness is None


# --- downgrade only -------------------------------------------------------------------
def test_witness_can_clear_a_false_positive():
    """The measured failure: a memory preserved stance in wording the lexicon missed."""
    report = factwash.check(SOURCE, MEMORY, witness=stance(attributed=True, markers=["IAM console"]))
    assert report.verdict == "PASS"
    assert "LAUNDERED" in report.vetoed_flags
    assert report.witness["reason"].startswith("stance preserved")


def test_witness_cannot_create_a_flag():
    """It may only lower a verdict. A clean write stays clean however the witness answers."""
    clean_source = "I prefer dark mode in all my editors."
    clean_memory = "User prefers dark mode."
    report = factwash.check(clean_source, clean_memory,
                           witness=stance(hedged=True, attributed=True, markers=["prefers"]))
    assert report.verdict == "PASS"
    assert report.vetoed_flags is None


def test_witness_agreeing_leaves_the_flag_standing():
    report = factwash.check(SOURCE, MEMORY, witness=stance(hedged=False, attributed=False))
    assert report.verdict == "REWRITE"
    assert report.witness["reason"] == "witness agrees the stance is gone"


# --- misbehaviour must never break the gate -------------------------------------------
def test_a_witness_that_raises_does_not_break_the_write():
    def broken(sentence):
        raise RuntimeError("provider down")
    report = factwash.check(SOURCE, MEMORY, witness=broken)
    assert report.verdict == "REWRITE"          # falls back to the deterministic verdict
    assert "witness raised" in report.witness["reason"]


def test_an_unusable_answer_changes_nothing():
    report = factwash.check(SOURCE, MEMORY, witness=lambda s: {"hedged": None, "attributed": None})
    assert report.verdict == "REWRITE"


# --- span validation, which is what keeps it a witness rather than a judge ------------
def test_parse_tag_rejects_a_marker_that_is_not_in_the_sentence():
    out = parse_tag('{"hedged": true, "attributed": false, "markers": ["allegedly"]}',
                    "Someone said Alice was promoted.")
    assert out["hedged"] is None and "absent from the text" in out["error"]


def test_parse_tag_rejects_a_positive_verdict_with_no_span():
    out = parse_tag('{"hedged": true, "attributed": false, "markers": []}', "Alice is an admin.")
    assert out["hedged"] is None


def test_parse_tag_rejects_non_boolean_fields():
    out = parse_tag('{"hedged": "maybe", "attributed": false, "markers": []}', "Alice is an admin.")
    assert out["hedged"] is None and "non-boolean" in out["error"]


def test_parse_tag_accepts_a_grounded_answer():
    out = parse_tag('{"hedged": false, "attributed": true, "markers": ["Someone said"]}',
                    "Someone said Alice was promoted.")
    assert out["attributed"] is True and "error" not in out


# --- the veto only ever looks at flagged writes ---------------------------------------
def test_veto_is_not_consulted_on_a_passing_write():
    """Escalating on PASS would spend money where ~1 detection is left to win."""
    called = []
    factwash.check("I prefer dark mode.", "User prefers dark mode.",
                  witness=lambda s: called.append(s) or {"hedged": True, "attributed": True,
                                                         "markers": ["prefers"]})
    assert called == [], "witness must not be called on a non-flagged write"


def test_apply_veto_is_a_noop_on_empty_memory():
    report = factwash.check(SOURCE, MEMORY)
    vetoed, detail = apply_veto(report, "   ", stance(hedged=True, markers=["x"]))
    assert vetoed is False
