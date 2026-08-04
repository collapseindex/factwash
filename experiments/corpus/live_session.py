"""Turn the 44 hand-labelled conversational writes into a session `triage` can serve.

The Enron corpus said something important and incomplete: of 29 bad memory writes, 27
were fabrication or inference and only 2 were stance loss. That is either a fact about
BUSINESS EMAIL or a fact about MEMORY WRITES IN GENERAL, and those imply different
papers. The tool targets stance loss; if stance loss is rare everywhere, the tool targets
something that does not happen.

The comparison does not need new annotation. The 44 live writes came from conversational
hearsay -- the setting Manufactured Confidence constructed -- and 20 of them are already
labelled `flag`. Triaging those 20 by mechanism gives the other half of the comparison
from data that already exists.

    python experiments/corpus/live_session.py
    python experiments/corpus/label.py triage --session data/corpus/session_live.jsonl

Weights are 1.0 and the strata are nominal: this set was labelled exhaustively, not
sampled, so there is nothing to scale. Only the mechanism counts are read from it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

import test_published_numbers as tpn      # noqa: E402  (its loader is the pinned one)

OUT = ROOT / "data" / "corpus"


def main() -> int:
    pairs = tpn._live_pairs()
    if not pairs:
        print("no live pairs; the paid-run ledgers in data/raw are missing", file=sys.stderr)
        return 1

    flagged = [(s, m) for s, m, label in pairs if label == "flag"]
    if not flagged:
        print("no writes labelled 'flag' in the live corpus", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    session = OUT / "session_live.jsonl"
    labels = OUT / "session_live_labels.jsonl"

    meta = {"_meta": True, "pool": "live 44-write conversational corpus",
            "seed": 0, "exhaustive": True,
            "n_flagged_total": len(flagged), "n_flagged_sampled": len(flagged),
            "flag_sampling_rate": 1.0,
            "n_passed_total": 0, "n_passed_sampled": 0, "pass_sampling_rate": 1.0,
            "rubric_version": 1,
            "note": ("Built from tests/fixtures/live_labels.json for the mechanism "
                     "comparison against the Enron corpus. Not a sampled pool.")}

    items, labs = [], []
    for i, (src, mem) in enumerate(flagged):
        items.append({"idx": i, "source": src, "memory": mem,
                      "stratum": "flagged", "weight": 1.0, "verdict": "", "label": None})
        labs.append({"idx": i, "label": "flag", "why": "",
                     "stratum": "flagged", "weight": 1.0, "memory": mem[:200]})

    session.write_text(json.dumps(meta, ensure_ascii=False) + "\n" +
                       "\n".join(json.dumps(x, ensure_ascii=False) for x in items) + "\n",
                       encoding="utf-8")
    # Only written if absent: a triage pass already done must not be silently reset.
    if not labels.exists():
        labels.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in labs) + "\n",
                          encoding="utf-8")

    print(f"{len(flagged)} conversational writes already labelled 'flag' -> {session}")
    print(f"next: python experiments/corpus/label.py triage --session {session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
