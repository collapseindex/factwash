"""The containment threshold must be defended by data, not by whoever typed it.

MIN_CONTAINMENT decides whether a stored claim is matched to a source claim at all, and
an unmatched claim is never checked. A wrong value fails silently and in the flattering
direction, so this sweeps it over the real corpus and asserts the shipped value is on the
right side of the trade.

Skipped when data/raw is empty (a fresh clone has no paid runs).
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

import factwash
import factwash.claims as claims

ROOT = Path(__file__).resolve().parents[2]
SWEEP = (0.20, 0.25, 0.30, 0.34, 0.40, 0.50)
SHIPPED = 0.25          # keep in step with claims.MIN_CONTAINMENT


def _live():
    out = []
    for path in glob.glob(str(ROOT / "data" / "raw" / "*laundering*.jsonl")):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("memory"):
                continue
            out.append(rec)
    return out


@pytest.fixture
def restore_threshold():
    original = claims.MIN_CONTAINMENT
    yield
    claims.MIN_CONTAINMENT = original


def _score(records, threshold):
    claims.MIN_CONTAINMENT = threshold
    hearsay = [r for r in records if r["kind"] == "injection"]
    confident = [r for r in records if r["kind"] == "legit"]
    flagged = sum(1 for r in hearsay
                  if factwash.check(r["source"], r["memory"]).verdict in ("REWRITE", "REJECT"))
    false_pos = sum(1 for r in confident
                    if factwash.check(r["source"], r["memory"]).verdict in ("REWRITE", "REJECT"))
    unmatched = sum(1 for r in records
                    if factwash.check(r["source"], r["memory"]).verdict == "UNCHECKABLE")
    return {"flagged": flagged, "false_pos": false_pos, "unmatched": unmatched,
            "hearsay": len(hearsay), "confident": len(confident)}


def test_shipped_threshold_is_not_beaten_by_any_swept_alternative(restore_threshold, capsys):
    records = _live()
    if len(records) < 40:
        pytest.skip("needs paid-run data in data/raw")

    results = {t: _score(records, t) for t in SWEEP}
    here = _score(records, SHIPPED)

    with capsys.disabled():
        print("\n[threshold sweep] over", len(records), "real extractor outputs")
        for t, r in results.items():
            print(f"  {t:.2f}  hearsay flagged {r['flagged']:>3}/{r['hearsay']}   "
                  f"confident wrongly flagged {r['false_pos']}/{r['confident']}   "
                  f"unmatched {r['unmatched']}")

    # No alternative may catch more hearsay without also costing false positives.
    for t, r in results.items():
        better_recall = r["flagged"] > here["flagged"]
        assert not (better_recall and r["false_pos"] <= here["false_pos"]), (
            f"threshold {t} strictly beats the shipped {SHIPPED}: "
            f"{r['flagged']} vs {here['flagged']} hearsay flagged at "
            f"{r['false_pos']} vs {here['false_pos']} false positives"
        )


def test_the_fixture_corpora_cannot_justify_this_threshold(restore_threshold):
    """Documents WHY the sweep runs on live data: the fixtures are blind to this knob.

    If this ever fails, the fixtures have become sensitive enough to tune against and
    the sweep above could move onto them.
    """
    def fixture_scores(threshold):
        claims.MIN_CONTAINMENT = threshold
        scores = []
        for name in ("planted_corpus", "clean_corpus"):
            path = ROOT / "tests" / "fixtures" / f"{name}.jsonl"
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    scores.append(factwash.check(rec["source"], rec["memory"]).verdict)
        return scores

    assert fixture_scores(0.25) == fixture_scores(0.50), (
        "fixtures now discriminate between 0.25 and 0.50 -- update the comment in claims.py"
    )


def test_sweep_constant_matches_what_ships():
    """A sweep that defends a number the package no longer uses defends nothing."""
    assert claims.MIN_CONTAINMENT == SHIPPED
