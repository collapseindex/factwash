"""Adversarial stress tests. These exist to keep the README's claim bounded and honest.

Two corpora, and the gap between them is the point:

  stress_corpus.jsonl   was visible while the lexicons were being fixed -> FITTED
  stress_heldout.jsonl  was written afterwards, using hedge and attribution forms
                        deliberately absent from the lexicon      -> HONEST

Recall on the fitted set is ~92%. On the held-out set it is ~14%. That gap is not a bug
to be closed by adding more terms -- adding forty terms is exactly what produced it. It is
the measured ceiling of substring matching, and the numbers below are asserted so nobody
can quietly report the fitted figure as if it were the real one.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import factwash

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Measured 2026-08-03. Floors, so improvements are welcome and regressions fail.
MIN_FITTED_EVASION = 10 / 12
MIN_HELDOUT_EVASION = 1 / 14        # deliberately low: this is a ceiling, not a target
MIN_PRECISION = 1.0                 # a false positive costs more than a miss here
MAX_HONEST_EVASION_CLAIM = 0.35     # if held-out recall ever exceeds this, update the README


def _load(name):
    return [json.loads(l) for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def _score(rows, cls):
    items = [r for r in rows if r["class"] == cls]
    ok = 0
    for r in items:
        verdict = factwash.check(r["source"], r["memory"]).verdict
        if r["expect"] == "flag":
            ok += verdict in ("REWRITE", "REJECT")
        elif r["expect"] == "pass":
            ok += verdict == "PASS"
        else:
            ok += verdict != "PASS"
    return ok, len(items)


def test_precision_is_the_property_this_tool_actually_has():
    """Both corpora: a confident memory containing domain uses of lexicon words
    ('insurance claim', 'database record', 'release notes', 'reported revenue')
    must not be flagged. Precision is what makes the tool keepable."""
    for name in ("stress_corpus.jsonl", "stress_heldout.jsonl"):
        ok, n = _score(_load(name), "collision")
        assert ok / n >= MIN_PRECISION, f"{name}: {ok}/{n} collisions handled"


def test_robustness_inputs_never_read_as_a_clean_pass():
    ok, n = _score(_load("stress_corpus.jsonl"), "robustness")
    assert ok == n, f"{ok}/{n}"


def test_fitted_evasion_recall_holds(capsys):
    ok, n = _score(_load("stress_corpus.jsonl"), "evasion")
    with capsys.disabled():
        print(f"\n[stress] fitted evasion recall   {ok}/{n} = {ok/n:.0%}")
    assert ok / n >= MIN_FITTED_EVASION


def test_heldout_evasion_recall_is_the_number_we_publish(capsys):
    """The honest recall figure. Asserted at BOTH ends.

    The floor catches a regression. The ceiling catches something more insidious: if
    held-out recall ever jumps, the most likely explanation is that these cases leaked
    into the lexicon and the set is no longer held out. Either way a human should look
    before the README's claim changes.
    """
    ok, n = _score(_load("stress_heldout.jsonl"), "evasion")
    with capsys.disabled():
        print(f"[stress] held-out evasion recall {ok}/{n} = {ok/n:.0%}   <- the honest number")
    assert ok / n >= MIN_HELDOUT_EVASION
    assert ok / n <= MAX_HONEST_EVASION_CLAIM, (
        f"held-out recall rose to {ok/n:.0%}. Either the method genuinely improved, or "
        f"these cases leaked into the lexicon and this set is no longer held out. "
        f"Check which, then update the README claim and this bound together."
    )


def test_the_two_corpora_do_not_share_phrasing():
    """A held-out set that reuses the fitted set's wording is not held out."""
    fitted = {r["source"].lower() for r in _load("stress_corpus.jsonl")}
    held = {r["source"].lower() for r in _load("stress_heldout.jsonl")}
    assert not (fitted & held), "held-out corpus reuses fitted sources"
