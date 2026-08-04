"""Two-corpus calibration: the launch-gate numbers for the README.

Planted corpus: every expected flag must fire (detection). Clean corpus: the gate must
stay quiet (false positives). The two corpora must produce different rates; a checker
that fires everywhere is as useless as one that fires nowhere.
"""
import json
from pathlib import Path

import factwash

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

PLANTED_DETECTION_FLOOR = 0.90
CLEAN_FP_CEILING = 0.10


def _load(name):
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _fired(report):
    return {f.name for f in report.flags if f.severity in ("fail", "warn")}


# A false positive is a write that gets BLOCKED or ALTERED, not one that gets annotated.
# PASS_WITH_FLAGS stores the memory unchanged and attaches a note, so counting it as a
# false positive would penalise the tool for being informative. This matches the
# definition already used for the live-data precision numbers, where "flagged" has always
# meant REWRITE or REJECT; the change here is to make calibration consistent with it.
BLOCKING = ("REWRITE", "REJECT")


def test_two_corpus_calibration(capsys):
    planted, clean = _load("planted_corpus.jsonl"), _load("clean_corpus.jsonl")

    detected, missed = 0, []
    for item in planted:
        rep = factwash.check(item["source"], item["memory"])
        if set(item["expected_flags"]) <= _fired(rep) and rep.verdict in BLOCKING:
            detected += 1
        else:
            missed.append((item["id"], rep.verdict, sorted(_fired(rep))))
    detection_rate = detected / len(planted)

    false_pos = [(item["id"], rep.verdict, sorted(_fired(rep)))
                 for item in clean
                 if (rep := factwash.check(item["source"], item["memory"])).verdict in BLOCKING]
    fp_rate = len(false_pos) / len(clean)

    with capsys.disabled():
        print(f"\n[calibration] planted detection {detected}/{len(planted)} = {detection_rate:.2f}   "
              f"clean false-positive {len(false_pos)}/{len(clean)} = {fp_rate:.2f}")

    assert detection_rate >= PLANTED_DETECTION_FLOOR, f"missed: {missed}"
    assert fp_rate <= CLEAN_FP_CEILING, f"false positives: {false_pos}"
    # the two corpora must have known-different answers, and the tool must tell them apart
    assert detection_rate > fp_rate
