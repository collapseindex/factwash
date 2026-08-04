"""Every number printed in the README must still be true.

This exists because the published figures drifted twice without anyone noticing: once
when a threshold moved and once when the memory-side lexicon was broadened. Both times
the code got better and the README kept claiming the old result. Every other invariant
in this repo is pinned by a test that fails on drift; the claims were not.

Each case here recomputes a figure from the corpora and asserts the exact string appears
in README.md. A number that changes for a good reason fails this test on purpose: update
the README in the same commit that changes the behaviour.

Figures needing a live model (the witness row) cannot be recomputed offline and are
listed in WITNESS_MEASURED below with the date and command that produced them.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

import factwash

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
FIXTURES = ROOT / "tests" / "fixtures"

BLOCKING = ("REWRITE", "REJECT")   # a flag is a write that gets blocked or altered

# Measured with a live model; see the command in the README. Recomputing these costs
# money and needs a key, so they are asserted as *present in the README* only, and the
# measurement itself is reproduced by experiments/stance_tagger.py.
WITNESS_MEASURED = {"recall": "85%", "precision": "**94%**"}

# The witness-vs-gold head-to-head (experiments/external/eval_witness.py). Needs an API
# key, so like the row above it is asserted as PRESENT rather than recomputed. The run
# ledgers are in data/raw/*witness-vs-gold* and the summaries in data/results/.
WITNESS_VS_GOLD = {
    "hedge lexicon": "| Hedges | lexicon | 0.97 | 0.62 | 0.76 |",
    "hedge witness": "| | **witness** | 0.96 | **0.79** | **0.87** |",
    "attribution lexicon": "| Attribution | lexicon | 0.85 | 0.45 | 0.59 |",
    "attribution witness": "| | **witness** | 0.87 | **0.60** | **0.71** |",
}


def _load(name):
    return [json.loads(l) for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if l.strip()]


def _flagged(source, memory):
    return factwash.check(source, memory).verdict in BLOCKING


def _assert_in_readme(fragment, what):
    assert fragment in README, (
        f"README no longer states the true value for {what}. Expected to find: {fragment!r}. "
        f"Recompute, update the README, and commit both together."
    )


# --- calibration ----------------------------------------------------------------------
def test_calibration_figures_match():
    planted, clean = _load("planted_corpus.jsonl"), _load("clean_corpus.jsonl")
    detected = sum(1 for i in planted if _flagged(i["source"], i["memory"]))
    false_pos = sum(1 for i in clean if _flagged(i["source"], i["memory"]))
    _assert_in_readme(f"| Planted failures, the original four checks | {len(planted)} | "
                      f"{detected}/{len(planted)} detected |", "planted detection")
    _assert_in_readme(f"| Clean memories | {len(clean)} | {false_pos}/{len(clean)} false positives |",
                      "clean false positives")


# --- the adversarial ceiling ----------------------------------------------------------
def test_heldout_recall_figure_matches():
    rows = [r for r in _load("stress_heldout.jsonl") if r["class"] == "evasion"]
    caught = sum(1 for r in rows if _flagged(r["source"], r["memory"]))
    pct = round(100 * caught / len(rows))
    _assert_in_readme(f"**{caught} of {len(rows)} ({pct}%)**", "held-out evasion recall")


def test_collision_precision_figure_matches():
    rows = [r for name in ("stress_corpus.jsonl", "stress_heldout.jsonl")
            for r in _load(name) if r["class"] == "collision"]
    correct = sum(1 for r in rows if not _flagged(r["source"], r["memory"]))
    _assert_in_readme(f"**{correct} of {len(rows)}**", "collision precision")


# --- the headline: real labelled writes -----------------------------------------------
def _live_pairs():
    labels = json.loads((FIXTURES / "live_labels.json").read_text(encoding="utf-8"))["labels"]

    def key(item_id, memory):
        for k in labels:
            kid, prefix = k.split("|", 1)
            if kid == item_id and memory.strip().startswith(prefix):
                return k
        return None

    pairs = {}
    for path in glob.glob(str(ROOT / "data" / "raw" / "*laundering*.jsonl")):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("error") or not rec.get("memory") or rec["kind"] != "injection":
                continue
            pairs[(rec["id"], rec["memory"].strip()[:200])] = rec

    out = []
    for (item_id, _), rec in pairs.items():
        k = key(item_id, rec["memory"])
        if k and labels[k]["label"] in ("flag", "pass"):
            out.append((rec["source"], rec["memory"], labels[k]["label"]))
    return out


def test_deterministic_recall_and_precision_match():
    pairs = _live_pairs()
    if len(pairs) < 20:
        pytest.skip("needs the paid-run ledgers in data/raw")

    tp = sum(1 for s, m, lab in pairs if lab == "flag" and _flagged(s, m))
    fn = sum(1 for s, m, lab in pairs if lab == "flag" and not _flagged(s, m))
    fp = sum(1 for s, m, lab in pairs if lab == "pass" and _flagged(s, m))

    _assert_in_readme(f"**{round(100 * tp / (tp + fn))}%** ({tp} of {tp + fn})", "deterministic recall")
    _assert_in_readme(f"| {round(100 * tp / (tp + fp))}% |", "deterministic precision")
    _assert_in_readme(f"**{len(pairs)} hand-labelled memory writes", "labelled corpus size")


def test_the_witness_row_is_still_stated():
    """Cannot be recomputed offline, so assert the claim is at least present and dated."""
    for what, fragment in WITNESS_MEASURED.items():
        _assert_in_readme(fragment, f"witness {what}")


def test_the_witness_vs_gold_table_is_intact():
    """The head-to-head against external annotation, row by row.

    Pinned because it is the single result the architecture rests on: if the witness
    stops beating the lexicon on somebody else's gold, the open-class argument that
    justifies having an LLM in this tool at all is in doubt.
    """
    for what, fragment in WITNESS_VS_GOLD.items():
        _assert_in_readme(fragment, f"witness-vs-gold {what}")


def test_the_witness_beats_the_lexicon_in_the_published_table():
    """Guards the direction, not just the digits: a table edit that quietly flipped the
    conclusion would still pass the row-presence check above if both rows were changed."""
    import re
    for task in ("Hedges", "Attribution"):
        block = README.split(f"| {task} | lexicon |", 1)
        assert len(block) == 2, f"the {task} lexicon row is gone from the README"
        nums = re.findall(r"0\.\d\d", block[1][:200])
        assert len(nums) >= 6, f"cannot read both {task} rows from the README table"
        lex_f1, wit_f1 = float(nums[2]), float(nums[5])
        assert wit_f1 > lex_f1, (
            f"the README now shows the witness ({wit_f1}) not beating the lexicon "
            f"({lex_f1}) on {task}; that inverts the argument for shipping a witness"
        )


# --- the 2x2 --------------------------------------------------------------------------
def test_two_by_two_cells_match():
    """Re-derives each cell from its rescored summary rather than trusting the table."""
    cells = {
        "haiku-4.5 | naive": "20260802_234540_laundering_claude-haiku-4-5_mc-fix_s0",
        "haiku-4.5 | mem0": "20260802_235442_laundering_claude-haiku-4-5_mem0-fix_s1",
        "sonnet-5 | naive": "20260803_000315_laundering_claude-sonnet-5_mc-fix_s2",
        "sonnet-5 | mem0": "20260803_000805_laundering_claude-sonnet-5_mem0-fix_s4",
    }
    checked = 0
    for label, stem in cells.items():
        path = ROOT / "data" / "results" / f"{stem}_rescored.json"
        if not path.is_file():
            continue
        block = json.loads(path.read_text(encoding="utf-8"))["injections_excluding_non_extractions"]
        _assert_in_readme(f"| {block['laundered']} of {block['n']} | {block['de_hedged']} of {block['n']} |",
                          f"2x2 cell {label}")
        checked += 1
    if checked == 0:
        pytest.skip("no rescored summaries present; run experiments/rescore.py")


# --- version parity -------------------------------------------------------------------
def test_version_matches_pyproject():
    """v0.4.0 shipped with __version__ still reading 0.3.0 and nothing caught it.
    The same drift discipline that guards the README's numbers now guards the version."""
    import re
    declared = re.search(r'version = "([^"]+)"',
                         (ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    assert factwash.__version__ == declared


# Measured with a live model (experiments/added_eval.py); asserted as PRESENT like the
# witness rows, since recomputing costs money and needs a key.
ADDED_MEASURED = {"precision": "**precision 0.57**", "recall": "**recall 0.30**",
                  "counts": "8 of 27 targets found", "coverage": "96.9% (95 of 98)",
                  "interval": "[0.16, 0.48]"}


def test_the_added_measurement_is_still_stated():
    for what, fragment in ADDED_MEASURED.items():
        _assert_in_readme(fragment, f"ADDED witness {what}")


# The LLM-judge baseline (experiments/judge_baseline.py). Needs a key, so asserted as
# PRESENT like the other live-model rows; ledgers in data/raw/*judgebaseline*.
JUDGE_BASELINE = {
    "gate row": "| Real writes (44, 20 pos.) | gate | 0.73 | **0.95** |",
    "small judge": "| | LLM judge (small) | 1.00 | 0.30 |",
    "large judge": "| | LLM judge (large) | 0.91 | 0.50 |",
    "adversarial judge": "| | LLM judge (small) | 1.00 | **0.92** |",
    "the mechanism": "the memory accurately captures the core fact",
    "the caveat": "89 of 90 items",
}


def test_the_judge_baseline_is_still_stated():
    for what, fragment in JUDGE_BASELINE.items():
        _assert_in_readme(fragment, f"judge baseline {what}")
