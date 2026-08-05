"""A second readout that uses no model at all.

Every outcome in this paper is a model's judgement of another model's output. Rescoring
with a fixed judge gave 98% agreement, but agreement between two model-based evaluations
is not validation against ground truth, and this project has already been bitten once by
an instrument that was confidently wrong in a systematic direction.

This scores the same stored memories with the deterministic gate from the companion
paper: no model, no LLM judge, just the source's stance cues checked against the stored
text. It is a genuinely different instrument, with genuinely different failure modes.

What it is NOT: human annotation. It cannot be, and nothing here should be read as
validation against human judgement. The gate has a documented recall ceiling on
open-class stance (hedging and attribution plateau near half), so it will UNDERCOUNT
retention in both arms. The question is not whether it agrees on absolute rates, which
it will not. The question is whether it agrees on the DIRECTION and rough size of the
difference between arms, since a shared direction across two instruments that fail
differently is worth more than either instrument alone.

The gate is also biased in a way that matters here and is stated rather than hidden: it
looks for stance CUES in the stored text, so a field record reading
``CERTAINTY: hedged`` contains no word its lexicon knows. That handicaps the field arm
specifically. If the field arm still wins under an instrument tilted against it, that is
informative; if it loses, that is expected and not evidence of anything.
"""
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

spec = importlib.util.spec_from_file_location(
    "a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

try:
    from factwash import inspect as fw_inspect  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


def gate_retains(source_note: str, stored: str) -> bool:
    """True when the deterministic gate does NOT flag stance loss between the two."""
    import factwash
    try:
        rep = factwash.check(source_note, stored)
    except Exception:
        return False
    bad = {"MANUFACTURED_CONFIDENCE", "LAUNDERED"}
    return not any(f.name in bad for f in rep.flags)


def sign_p(pos, neg):
    n = pos + neg
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) / 2 ** n)


def main() -> int:
    if not HAVE:
        print("factwash not importable; run `pip install -e .` first")
        return 1

    rows = [r for r in A.balance(A.load())[0]
            if r["corpus"] == "c60" and r["pressure"] in ("brutal", "severe")]
    if not rows:
        print("no sixty-claim rows found")
        return 1

    by_model = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        by_model[r["model"]][r["arm"]][r["pair"]].append(
            gate_retains(r["note"], r["stored"]))

    model_rows = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        model_rows[r["model"]][r["arm"]][r["pair"]].append(
            A.outcome(r) == "kept_qualified")

    out = {}
    print("deterministic gate (no model) vs the blind reader (a model), same memories")
    print(f"{'model':<20} {'instrument':<14} {'field':>7} {'paren':>7} {'diff':>8} "
          f"{'sign test':>16}")
    print("-" * 82)
    for model in sorted(by_model):
        for label, src in (("blind reader", model_rows[model]),
                           ("gate, no model", by_model[model])):
            f_all = [v for vs in src["field"].values() for v in vs]
            p_all = [v for vs in src["paren"].values() for v in vs]
            fr, pr = sum(f_all) / len(f_all), sum(p_all) / len(p_all)
            deltas = {}
            for c in src["field"]:
                if c in src["paren"]:
                    deltas[c] = (sum(src["field"][c]) / len(src["field"][c])
                                 - sum(src["paren"][c]) / len(src["paren"][c]))
            pos = sum(1 for d in deltas.values() if d > 0)
            neg = sum(1 for d in deltas.values() if d < 0)
            p = sign_p(pos, neg)
            out.setdefault(model, {})[label] = {
                "field_rate": round(fr, 4), "paren_rate": round(pr, 4),
                "mean_per_claim_delta": round(sum(deltas.values()) / len(deltas), 4),
                "positive": pos, "negative": neg, "sign_p": round(p, 5)}
            print(f"{model.replace('claude-', ''):<20} {label:<14} {fr:>7.3f} "
                  f"{pr:>7.3f} {sum(deltas.values()) / len(deltas):>+8.3f} "
                  f"{pos:>4}+/{neg:<3}- p={p:.4f}")

    print()
    print("The two instruments are not expected to agree on absolute rates: the gate has")
    print("a documented recall ceiling on open-class stance, and it is tilted AGAINST the")
    print("field arm because 'CERTAINTY: hedged' contains no word its lexicon knows.")
    print("The question is whether the DIRECTION of the difference survives an instrument")
    print("with different failure modes.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    dest = RESULTS / "mechanical_readout.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
