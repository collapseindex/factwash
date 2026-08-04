"""The external numbers in the README, recomputed and pinned.

Same rule as test_published_numbers.py: a figure that changes for a good reason fails
this test on purpose, so the README and the behaviour move in one commit.

These skip when the corpora are absent, because they are 44 MB and gitignored. Fetch with
`python experiments/external/fetch.py && python experiments/external/build_corpora.py`.
The skip is the honest behaviour, but it does mean CI without the corpora cannot catch
drift here -- which is why the numbers are also written down in the README prose that
these assertions check against.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "data" / "external" / "normalized"
sys.path.insert(0, str(ROOT / "experiments" / "external"))

README = (ROOT / "README.md").read_text(encoding="utf-8")


def _rows(split: str):
    files = sorted(NORMALIZED.glob("*.jsonl"))
    if not files:
        pytest.skip("external corpora absent; see experiments/external/README.md")
    out = []
    for p in files:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("split") == split:
                out.append(row)
    return out


def _score(split, task):
    from eval_lexicons import TASKS, prf, score
    classes, detect = TASKS[task]
    rows = _rows(split)
    tp = fp = fn = 0
    for p in sorted(NORMALIZED.glob("*.jsonl")):
        sub = [r for r in rows if r["corpus"] == p.stem]
        if not sub or not any(c["cls"] in classes for r in sub for c in r["cues"]):
            continue
        res = score(sub, classes, detect, drop_out_of_scope=(task == "hedge"))
        tp, fp, fn = tp + res["tp"], fp + res["fp"], fn + res["fn"]
    return prf(tp, fp, fn)


@pytest.mark.parametrize("task,precision,recall,f1", [
    ("negation", 0.89, 0.94, 0.91),
    ("hedge", 0.89, 0.66, 0.76),
    ("attribution", 0.91, 0.49, 0.63),
    ("conditional", 0.61, 0.67, 0.64),
])
def test_test_split_figures_match_the_readme(task, precision, recall, f1):
    got = _score("test", task)
    for name, expected in (("precision", precision), ("recall", recall), ("f1", f1)):
        assert round(got[name], 2) == expected, (
            f"{task} {name} on the held-out split is {got[name]:.2f}, README says "
            f"{expected:.2f}. Recompute with experiments/external/eval_lexicons.py and "
            f"update both together."
        )
    assert f"| {precision:.2f} | {recall:.2f} | **{f1:.2f}** |" in README \
        or f"| {precision:.2f} | {recall:.2f} | {f1:.2f} |" in README, \
        f"README no longer carries the {task} row {precision:.2f}/{recall:.2f}/{f1:.2f}"


def test_the_closed_class_hypothesis_still_holds():
    """The design claim in lexicons.py: closed-class generalises, open-class does not.

    This is the one external result the architecture rests on. If negation ever stops
    beating hedging on held-out text from an untuned domain, the comment justifying the
    whole asymmetric-lexicon design is wrong and should be rewritten, not quietly kept.
    """
    negation, hedge = _score("test", "negation"), _score("test", "hedge")
    assert negation["f1"] > hedge["f1"], (
        f"negation F1 {negation['f1']:.2f} no longer exceeds hedge F1 {hedge['f1']:.2f}; "
        f"the closed-class argument in lexicons.py needs revisiting"
    )


def test_dev_and_test_have_not_diverged():
    """A large dev/test gap means the mined terms memorised rather than generalised."""
    for task in ("hedge", "negation", "conditional"):
        dev, test = _score("dev", task), _score("test", task)
        assert abs(dev["f1"] - test["f1"]) < 0.10, (
            f"{task} F1 differs by {abs(dev['f1'] - test['f1']):.2f} between dev "
            f"({dev['f1']:.2f}) and test ({test['f1']:.2f}); the lexicon is fitting dev"
        )


def test_no_corpus_is_mostly_redacted():
    """The redaction guard, asserted downstream of where it runs."""
    for p in sorted(NORMALIZED.glob("*.jsonl")):
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not rows:
            continue
        redacted = sum(1 for r in rows
                       if r["text"].count("*") > max(len(r["text"].split()) // 2, 1))
        assert redacted / len(rows) <= 0.25, (
            f"{p.stem} is {100 * redacted / len(rows):.0f}% redaction placeholders and "
            f"should never have been written; check REDACTION_GUARD in build_corpora.py"
        )
