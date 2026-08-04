"""Score the LLM witness against expert annotation, head to head with the lexicon.

This is the experiment the whole architecture rests on and it had never been run.

The claim in the README is that hedging and attribution are OPEN classes, that no word
list can enumerate them, and that a model asked to *perceive* stance sees what a lexicon
cannot. Every number supporting that came from 44 memory writes this project produced and
labelled. Meanwhile there are now ~106,000 sentences with hedge, negation and attribution
cues marked by linguists who had never heard of Factwash.

So: give the witness and the lexicon the SAME sentences and the SAME gold, and see whether
the gap the architecture assumes is actually there.

Two outcomes, both worth having:

  the witness wins       the open-class argument is externally confirmed and the veto
                         is understating what the witness could do
  the witness does not   then the LLM buys precision on our own writes and nothing more,
                         and the README's framing of it needs rewriting

What this measures, precisely
-----------------------------
Stance PERCEPTION on one sentence, which is exactly the witness's job and exactly what the
gold annotates. It is NOT verdict accuracy: no memory writes are involved, and the witness
in the shipped gate only ever downgrades. A win here does not license a claim about the
gate; it licenses the claim about why the gate needs a witness at all.

The witness is run through the SHIPPED code path (`factwash.witness.anthropic_witness`),
including span validation, so a tag it cannot ground in the sentence counts as unusable
rather than as a correct answer.

Sampling is stratified and seeded: equal numbers of gold-positive and gold-negative
sentences, drawn from the TEST split only, so neither side is scored on text the lexicon
was tuned against.

Run (metered, resumable, hard-capped):
    python experiments/external/eval_witness.py --task hedge --n 200 --budget 0.40
    python experiments/external/eval_witness.py --task attribution --n 200 --budget 0.40
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

from factwash import lexicons as lex                                   # noqa: E402
from factwash.witness import DEFAULT_MODEL, TAGGER_SYSTEM, parse_tag   # noqa: E402
from runlog import Budget, BudgetExceeded, RunLog, price_call         # noqa: E402

NORMALIZED = ROOT / "data" / "external" / "normalized"

# task -> (gold cue classes, the shipped lexicon predicate, which witness field answers it)
TASKS = {
    "hedge": (("speculation", "epistemic", "doxastic"), lex.hedges_in, "hedged"),
    "attribution": (("attribution",), lex.attribs_in, "attributed"),
}
MAX_TOKENS = 300


def load_test_rows(gold_classes):
    rows = []
    for path in sorted(NORMALIZED.glob("*.jsonl")):
        corpus = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not any(c["cls"] in gold_classes for r in corpus for c in r["cues"]):
            continue          # this corpus does not annotate the class; it cannot score it
        rows += [r for r in corpus if r.get("split") == "test"]
    return rows


def sample(rows, gold_classes, n, seed):
    """Stratified 50/50 positive/negative. Unbalanced sampling would let a witness that
    always answers 'no' look good on corpora where most sentences carry no cue."""
    pos = [r for r in rows if any(c["cls"] in gold_classes for c in r["cues"])]
    neg = [r for r in rows if not any(c["cls"] in gold_classes for c in r["cues"])]
    rng = random.Random(seed)
    rng.shuffle(pos)
    rng.shuffle(neg)
    half = n // 2
    picked = pos[:half] + neg[:half]
    rng.shuffle(picked)
    return picked


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=sorted(TASKS), required=True)
    ap.add_argument("--n", type=int, default=200, help="sentences (half positive)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--budget", type=float, required=True, help="hard USD cap")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="no API calls, exercises the loop")
    args = ap.parse_args()

    gold_classes, detect, field = TASKS[args.task]
    rows = load_test_rows(gold_classes)
    if not rows:
        print("no test rows; run build_corpora.py first", file=sys.stderr)
        return 1
    picked = sample(rows, gold_classes, args.n, args.seed)
    print(f"{args.task}: {len(picked)} sentences from the TEST split "
          f"({sum(1 for r in picked if any(c['cls'] in gold_classes for c in r['cues']))} positive)")

    client = None
    if not args.dry_run:
        try:
            import anthropic
        except ImportError:
            print("needs: pip install anthropic", file=sys.stderr)
            return 1
        client = anthropic.Anthropic()

    budget = Budget(cap_usd=args.budget)
    log = RunLog(operation=f"witness_vs_gold_{args.task}", model=args.model,
                 params=f"n{len(picked)}", seed=args.seed, resume_path=args.resume)
    budget.spent_usd = log.prior_spend_usd
    if log.resumed:
        print(f"resuming {log.path.name}: {log.done_count} done, "
              f"${budget.spent_usd:.4f} already spent")

    try:
        for i, row in enumerate(picked):
            item_id = f"{row['corpus']}|{row['doc']}|{row['sid']}"
            if log.is_done(item_id):
                continue
            sentence = row["text"]
            gold = any(c["cls"] in gold_classes for c in row["cues"])
            lexical = bool(detect(sentence))

            if args.dry_run:
                log.append({"id": item_id, "corpus": row["corpus"], "gold": gold,
                            "lexical": lexical, "witness": None, "cost_usd": 0.0,
                            "dry_run": True})
                continue

            # Rough pre-estimate purely to keep the cap honest BEFORE the call.
            budget.check(0.002)
            resp = client.messages.create(
                model=args.model, max_tokens=MAX_TOKENS, system=TAGGER_SYSTEM,
                messages=[{"role": "user", "content": sentence}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            tag = parse_tag(text, sentence)          # shipped path: span validation included
            usage = resp.usage
            cost = price_call(args.model, usage.input_tokens, usage.output_tokens,
                              raw=usage.model_dump() if hasattr(usage, "model_dump") else None)
            budget.record(cost.usd)
            log.append({"id": item_id, "corpus": row["corpus"], "sentence": sentence,
                        "gold": gold, "lexical": lexical,
                        "witness": tag.get(field), "markers": tag.get("markers"),
                        "witness_error": tag.get("error"),
                        "gold_cues": [c["text"] for c in row["cues"] if c["cls"] in gold_classes],
                        "cost_usd": cost.usd, "cost": cost.to_dict()})
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(picked)}  ${budget.spent_usd:.4f}")
    except BudgetExceeded as e:
        print(f"\nSTOPPED ON BUDGET: {e}\nResume with --resume {log.path}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\ninterrupted; resume with --resume {log.path}", file=sys.stderr)
    finally:
        log.close()

    # --- score, counting unusable witness replies honestly -----------------------------
    recs = [r for r in log.records() if not r.get("dry_run")]
    if not recs:
        print("no scored records (dry run?)")
        return 0

    wit = prf(*[sum(1 for r in recs if cond(r)) for cond in (
        lambda r: r["gold"] and r["witness"] is True,
        lambda r: not r["gold"] and r["witness"] is True,
        lambda r: r["gold"] and r["witness"] is not True)])
    lexi = prf(*[sum(1 for r in recs if cond(r)) for cond in (
        lambda r: r["gold"] and r["lexical"],
        lambda r: not r["gold"] and r["lexical"],
        lambda r: r["gold"] and not r["lexical"])])
    unusable = sum(1 for r in recs if r["witness"] is None)

    summary = {
        "task": args.task, "model": args.model, "n": len(recs), "seed": args.seed,
        "split": "test", "witness": wit, "lexicon": lexi,
        "unusable_witness_replies": unusable,
        "spend_usd": round(budget.spent_usd, 4),
        "interpretation_caveat": (
            "Stance perception on single sentences, not verdict accuracy. No memory "
            "writes are involved. An unusable witness reply is counted as a MISS, not "
            "skipped, because in the shipped gate it leaves the deterministic verdict "
            "standing and therefore behaves like one."),
    }
    out = log.write_summary(summary)

    print(f"\n{'':10s} {'prec':>6s} {'rec':>6s} {'F1':>6s}   (n={len(recs)}, test split)")
    print(f"{'lexicon':10s} {lexi['precision']:6.2f} {lexi['recall']:6.2f} {lexi['f1']:6.2f}")
    print(f"{'witness':10s} {wit['precision']:6.2f} {wit['recall']:6.2f} {wit['f1']:6.2f}")
    print(f"\nunusable witness replies: {unusable}  (counted as misses)")
    print(f"spend: ${budget.spent_usd:.4f}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
