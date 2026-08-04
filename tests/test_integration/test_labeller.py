"""The corpus labeller's arithmetic, especially the part that could flatter.

`score` estimates recall by scaling misses found in a SAMPLED stratum by 1/rate. Get that
backwards, or forget the scaling entirely, and recall comes out inflated by exactly the
sampling factor while looking perfectly reasonable. That is the shape of every measurement
bug this repo has already shipped, so it is pinned here with hand-computable numbers.

Nothing here touches the network or a model.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LABEL_PY = ROOT / "experiments" / "corpus" / "label.py"


def _session(tmp_path, meta, items, labels):
    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join([json.dumps(meta)] + [json.dumps(i) for i in items]) + "\n",
        encoding="utf-8")
    (tmp_path / "session_labels.jsonl").write_text(
        "\n".join(json.dumps(l) for l in labels) + "\n", encoding="utf-8")
    return session


def _score(session):
    proc = subprocess.run(
        [sys.executable, str(LABEL_PY), "score", "--session", str(session)],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads((session.parent / "session_score.json").read_text(encoding="utf-8"))


def test_precision_is_a_direct_count_over_the_flagged_stratum(tmp_path):
    """8 flagged writes labelled, 6 correct -> precision 0.75, no weighting involved."""
    meta = {"_meta": True, "flag_sampling_rate": 1.0, "pass_sampling_rate": 0.5}
    items = [{"idx": i, "stratum": "flagged", "weight": 1.0} for i in range(8)]
    labels = [{"idx": i, "label": "flag" if i < 6 else "pass",
               "stratum": "flagged", "weight": 1.0} for i in range(8)]
    out = _score(_session(tmp_path, meta, items, labels))
    assert out["precision"] == 0.75
    assert out["flagged_stratum"]["true_positives"] == 6
    assert out["flagged_stratum"]["false_positives"] == 2


def test_recall_scales_sampled_misses_by_the_sampling_rate(tmp_path):
    """The number this test exists for.

    6 true positives in the flagged stratum. The passed stratum was sampled at 25% and
    two misses turned up in it, so the pool holds an estimated 2 / 0.25 = 8 misses, and
    recall is 6 / (6 + 8) = 0.429.

    Forgetting the scaling would give 6 / (6 + 2) = 0.75, which is not a rounding
    difference -- it is the tool looking 32 points better than it is.
    """
    meta = {"_meta": True, "flag_sampling_rate": 1.0, "pass_sampling_rate": 0.25}
    items = [{"idx": i, "stratum": "flagged" if i < 6 else "passed", "weight": 1.0}
             for i in range(16)]
    labels = ([{"idx": i, "label": "flag", "stratum": "flagged", "weight": 1.0}
               for i in range(6)] +
              [{"idx": i, "label": "flag" if i < 8 else "pass",
                "stratum": "passed", "weight": 4.0} for i in range(6, 16)])
    out = _score(_session(tmp_path, meta, items, labels))
    assert out["passed_stratum"]["misses_found"] == 2
    assert out["passed_stratum"]["estimated_total_misses"] == 8.0
    assert out["recall_estimated"] == 0.429
    assert out["recall_estimated"] < 0.75, "the sampling weight was not applied"


def test_ambiguous_is_excluded_from_both_and_reported(tmp_path):
    """An abstain must never be resolved toward whichever answer helps."""
    meta = {"_meta": True, "flag_sampling_rate": 1.0, "pass_sampling_rate": 1.0}
    items = [{"idx": i, "stratum": "flagged", "weight": 1.0} for i in range(4)]
    labels = [{"idx": 0, "label": "flag", "stratum": "flagged", "weight": 1.0},
              {"idx": 1, "label": "pass", "stratum": "flagged", "weight": 1.0},
              {"idx": 2, "label": "ambiguous", "stratum": "flagged", "weight": 1.0},
              {"idx": 3, "label": "skip", "stratum": "flagged", "weight": 1.0}]
    out = _score(_session(tmp_path, meta, items, labels))
    assert out["ambiguous"] == 1 and out["skipped"] == 1
    assert out["usable"] == 2
    assert out["precision"] == 0.5, "ambiguous or skip leaked into the precision count"


def test_a_perfect_flagged_stratum_still_cannot_claim_perfect_recall(tmp_path):
    """Precision 1.0 with misses in the sample must not report recall 1.0.

    This is the failure mode in plain form: every flag correct looks like a flawless
    tool, and the misses are in the stratum nobody looked at exhaustively.
    """
    meta = {"_meta": True, "flag_sampling_rate": 1.0, "pass_sampling_rate": 0.2}
    items = [{"idx": i, "stratum": "flagged" if i < 5 else "passed", "weight": 1.0}
             for i in range(10)]
    labels = ([{"idx": i, "label": "flag", "stratum": "flagged", "weight": 1.0}
               for i in range(5)] +
              [{"idx": i, "label": "flag" if i == 5 else "pass",
                "stratum": "passed", "weight": 5.0} for i in range(5, 10)])
    out = _score(_session(tmp_path, meta, items, labels))
    assert out["precision"] == 1.0
    assert out["recall_estimated"] == 0.5, "5 / (5 + 1/0.2) = 0.5"


def _label_session(tmp_path, keys):
    """Drive the labelling loop over a tiny session with piped keystrokes."""
    session = tmp_path / "s.jsonl"
    meta = {"_meta": True, "flag_sampling_rate": 1.0, "pass_sampling_rate": 1.0}
    items = [{"idx": i, "stratum": "flagged", "weight": 1.0,
              "source": f"User: Bob said item {i} shipped.", "memory": f"Item {i} shipped.",
              "verdict": "REWRITE"} for i in range(5)]
    session.write_text("\n".join([json.dumps(meta)] + [json.dumps(i) for i in items]) + "\n",
                       encoding="utf-8")
    proc = subprocess.run([sys.executable, str(LABEL_PY), "label", "--session", str(session)],
                          input=keys, capture_output=True, text=True, timeout=120)
    labels = tmp_path / "s_labels.jsonl"
    written = [json.loads(l) for l in labels.read_text(encoding="utf-8").splitlines()
               if l.strip()] if labels.exists() else []
    return proc, session, written


def test_labels_survive_an_interrupt_and_resume_skips_them(tmp_path):
    """Two hours of labelling must not depend on exiting politely.

    Every label is fsynced as the key is pressed, so a Ctrl+C, a closed terminal or a
    power cut loses nothing. This drives the loop, cuts stdin off mid-session, and then
    reopens it to confirm the finished items are not served again.
    """
    proc, session, written = _label_session(tmp_path, "f\np\n")
    assert proc.returncode == 0, proc.stderr
    assert len(written) == 2, f"labels lost on interrupt: {written}"
    assert [w["label"] for w in written] == ["flag", "pass"]
    assert "resume:" in proc.stdout, "the exit message must say how to resume"

    again = subprocess.run(
        [sys.executable, str(LABEL_PY), "label", "--session", str(session)],
        input="q\n", capture_output=True, text=True, timeout=120)
    assert "2 already labelled, 3 to go" in again.stdout, again.stdout


def test_an_interrupt_at_the_why_prompt_keeps_the_label(tmp_path):
    """The one place an interrupt could lose a real judgement.

    The reason prompt runs after the key is pressed. Writing the record only after that
    prompt meant Ctrl+C there discarded a decision the labeller had already made.
    """
    # Uppercase asks for a note, so stdin ending here lands exactly on that prompt.
    proc, _, written = _label_session(tmp_path, "F\n")
    assert len(written) == 1, "the label was thrown away at the reason prompt"
    assert written[0]["label"] == "flag" and written[0]["why"] == ""
    assert "last label kept" in proc.stdout


def test_the_labeller_never_writes_the_verdict_into_the_session():
    """Blindness is a property of the file, not of the operator's willpower.

    `sample` records the verdict so `score` can stratify, but the labelling loop must not
    render it. This asserts on the rendering function directly, because a well-meant
    'show a hint' change is exactly how a blind protocol stops being blind.
    """
    source = LABEL_PY.read_text(encoding="utf-8")
    render = source.split("def _render(", 1)[1].split("\ndef ", 1)[0]
    for leak in ("verdict", "flags", "stratum", "weight"):
        assert leak not in render, (
            f"_render() references {leak!r}; the labelling loop must show the source and "
            f"the memory and nothing else, or the labels stop being independent evidence"
        )
