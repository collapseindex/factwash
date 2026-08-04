"""The bench: aggregation over the gate, and the three honesty rules it exists to keep
(lower-bound framing, UNCHECKABLE out of the denominator, stimulus-set comparability)."""
import json
from pathlib import Path

import pytest

from factwash.bench import BenchResult, load_pairs, run_adapter, score_pairs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _fixture_pairs(name):
    return [json.loads(l) for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if l.strip()]


# --- the bench must reproduce the shipped calibration numbers -------------------------
def test_planted_corpus_scores_at_full_laundering_rate():
    r = score_pairs(_fixture_pairs("planted_corpus.jsonl"))
    assert r.n == 12
    assert r.laundering_count == 12
    assert r.laundering_rate == 1.0


def test_clean_corpus_scores_at_the_known_false_positive_rate():
    r = score_pairs(_fixture_pairs("clean_corpus.jsonl"))
    assert r.n == 13
    assert r.laundering_count == 1          # the calibration table's 1/13
    assert r.uncheckable == 0


# --- honesty rules --------------------------------------------------------------------
def test_uncheckable_is_reported_and_out_of_the_denominator():
    pairs = [{"source": "The vendor ships the beta on Monday.",
              "memory": "User prefers dark mode."},
             {"source": "Someone said Alice was promoted.",
              "memory": "Alice was promoted."}]
    r = score_pairs(pairs)
    assert r.uncheckable == 1
    assert r.checkable == 1
    assert r.laundering_rate == 1.0          # 1 of 1 checkable, not 1 of 2


def test_nothing_checkable_is_none_not_zero():
    r = score_pairs([{"source": "Completely unrelated.", "memory": "Something else."}])
    assert r.laundering_rate is None
    assert "n/a" in r.render()


def test_render_carries_the_flag_rate_framing_and_uncheckable_lines():
    r = score_pairs(_fixture_pairs("planted_corpus.jsonl"), stimuli_id="calib-v1")
    out = r.render()
    assert "FLAG rate" in out
    assert "never in the denominator" in out
    assert "calib-v1" in out
    assert "SAME stimulus set" in " ".join(r.caveats)
    caveats = " ".join(r.caveats)
    assert "errs BOTH ways" in caveats, "the rate must not be framed one-sidedly"
    assert "not a floor" in caveats and "not an" in caveats


def test_mechanism_profile_names_the_checks_that_fired():
    r = score_pairs(_fixture_pairs("planted_corpus.jsonl"))
    assert set(r.mechanisms) & {"LAUNDERED", "MANUFACTURED_CONFIDENCE", "BRITTLE", "TRUNCATED"}


def test_to_dict_round_trips_the_headline_fields():
    d = score_pairs(_fixture_pairs("clean_corpus.jsonl"), stimuli_id="calib-v1").to_dict()
    assert d["stimuli_id"] == "calib-v1"
    assert d["checkable"] == d["n_writes"] - d["uncheckable"]
    assert d["laundering_flag_rate"] == pytest.approx(d["laundering_count"] / d["checkable"])
    assert d["caveats"]


# --- adapter contract -----------------------------------------------------------------
def test_adapter_pairs_and_error_accounting():
    def flaky(source):
        if "boom" in source:
            raise RuntimeError("adapter died")
        return [f"memory of: {source}", ""]     # empty memories are dropped

    pairs, errors, seen, no_write = run_adapter(flaky, ["a", "boom please", "b"])
    assert errors == 1 and seen == 3 and no_write == 0
    assert [p["source"] for p in pairs] == ["a", "b"]
    r = score_pairs(pairs, adapter_errors=errors, sources_seen=seen,
                    sources_no_write=no_write)
    assert r.adapter_errors == 1
    assert "adapter errors: 1" in r.render()


def test_abstention_is_counted_and_reported():
    """A source the system stores nothing for is the safest outcome, but it also
    shrinks the benchmark's exposure, so it must be visible rather than invisible."""
    def silent(source):
        return [] if "quiet" in source else [f"memory of {source}"]

    pairs, errors, seen, no_write = run_adapter(silent, ["a", "quiet one", "b", "quiet two"])
    assert (errors, seen, no_write) == (0, 4, 2)
    r = score_pairs(pairs, sources_seen=seen, sources_no_write=no_write)
    assert r.abstention_rate == 0.5
    assert "abstention 50%" in r.render()


def test_the_evasion_vector_is_reported_beside_the_flag_rate():
    """The benchmark's gaming vector: a system whose writes cannot be aligned offers
    fewer chances to be flagged. A high uncheckable rate must appear next to the flag
    rate, and the caveats must name the incentive."""
    pairs = [{"source": "Someone said Alice may get access.", "memory": "Alice has access."},
             {"source": "The vendor ships Monday.", "memory": "User prefers dark mode."}]
    r = score_pairs(pairs)
    assert r.uncheckable_rate == 0.5
    out = r.render()
    assert "uncheckable 50%" in out
    assert "evasion rather than" in " ".join(r.caveats)


def test_rates_are_none_not_zero_when_undefined():
    r = score_pairs([])
    assert r.uncheckable_rate is None and r.abstention_rate is None


def test_load_pairs_rejects_rows_missing_keys(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"source": "s"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        list(load_pairs(bad))
