"""The missing number: what escalate mode costs in PRECISION on labelled memory writes.

The README has said for a while that a witness allowed to RAISE verdicts reaches 93%
held-out recall, and that it cannot ship until its precision is measured, because a check
that can raise a verdict can also raise a wrong one. This measures it.

Two things are done differently from `experiments/stance_tagger.py --mode escalate`, and
both are deliberate:

1. GROUND TRUTH. stance_tagger's `--corpus live` derives "should flag" from the record's
   `kind`, which is exactly the labelling error already corrected once in this repo: it
   marks every hearsay-sourced item as should-flag regardless of what was actually
   stored, and the extractor preserves stance about half the time. Scoring against it
   would reproduce a known-broken metric. This uses the hand labels in
   `tests/fixtures/live_labels.json`.

2. CLAIM-LOCAL. stance_tagger tags the WHOLE source and the WHOLE memory. The witness
   prompt opens with "You label ONE sentence", so handing it a multi-turn transcript
   violates its own contract and asks it to summarise rather than perceive. This tags the
   matched source window and the memory sentence, which mirrors the deterministic path:
   same localisation, same verdict policy, only the detector swapped.

The comparison rule and the verdict policy stay in Python. The model answers "does this
sentence hedge / attribute", nothing else.

Run:
    python experiments/escalate_precision.py --budget 0.25
    python experiments/escalate_precision.py --budget 0.25 --dry-run    # $0
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import factwash                                                        # noqa: E402
from factwash.claims import match_source_window, sentences, strip_roles  # noqa: E402
from factwash.witness import DEFAULT_MODEL, TAGGER_SYSTEM, parse_tag   # noqa: E402
from runlog import Budget, BudgetExceeded, RunLog, price_call         # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
BLOCKING = ("REWRITE", "REJECT")
MAX_TOKENS = 300


def live_pairs():
    """The 44 hand-labelled (source, memory, label) triples. Same loader as the pinned test."""
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
            out.append((rec["id"], rec["source"], rec["memory"], labels[k]["label"]))
    return out


def tag_sentence(client, model, sentence, budget, cache):
    """One witness call, cached by sentence so repeated windows are not paid for twice."""
    if sentence in cache:
        return cache[sentence], 0.0
    budget.check(0.002)
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=TAGGER_SYSTEM,
        messages=[{"role": "user", "content": sentence}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    tag = parse_tag(text, sentence)
    usage = resp.usage
    cost = price_call(model, usage.input_tokens, usage.output_tokens,
                      raw=usage.model_dump() if hasattr(usage, "model_dump") else None)
    budget.record(cost.usd)
    cache[sentence] = tag
    return tag, cost.usd


def escalate_verdict(source, memory, client, model, budget, cache):
    """Deterministic gate first; witness only on writes it PASSED.

    Claim-local: for each memory sentence that matched a source window, ask the witness
    about that window and that sentence. Python decides what the answers mean, using the
    same rule the deterministic checks use -- stance present in the source and absent
    from the memory is a flag.
    """
    base = factwash.check(source, memory)
    if base.verdict in BLOCKING:
        return base.verdict, "lexical", 0.0, []      # already flagged; nothing to add

    src_sents = sentences(strip_roles(source))
    spent, flags = 0.0, []
    for sent in sentences(memory):
        window = match_source_window(sent, src_sents)
        if window is None:
            continue
        src_tag, c1 = tag_sentence(client, model, window, budget, cache)
        spent += c1
        if src_tag.get("hedged") is None:
            continue                                  # unusable: keep the base verdict
        if not (src_tag["hedged"] or src_tag["attributed"]):
            continue                                  # nothing in the source to lose
        mem_tag, c2 = tag_sentence(client, model, sent, budget, cache)
        spent += c2
        if mem_tag.get("hedged") is None:
            continue
        if src_tag["hedged"] and not mem_tag["hedged"]:
            flags.append("MANUFACTURED_CONFIDENCE")
        if src_tag["attributed"] and not mem_tag["attributed"]:
            flags.append("LAUNDERED")
    if flags:
        return "REWRITE", "witness", spent, sorted(set(flags))
    return base.verdict, "witness_agreed", spent, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pairs = live_pairs()
    if len(pairs) < 20:
        print("needs the paid-run ledgers in data/raw", file=sys.stderr)
        return 1
    print(f"{len(pairs)} hand-labelled writes "
          f"({sum(1 for *_, l in pairs if l == 'flag')} should flag)")

    client = None
    if not args.dry_run:
        try:
            import anthropic
        except ImportError:
            print("needs: pip install anthropic", file=sys.stderr)
            return 1
        client = anthropic.Anthropic()

    budget = Budget(cap_usd=args.budget)
    log = RunLog(operation="escalate_precision", model=args.model,
                 params=f"n{len(pairs)}", seed=0, resume_path=args.resume)
    budget.spent_usd = log.prior_spend_usd
    cache: dict[str, dict] = {}

    try:
        # The index is part of the key on purpose. Keying on id+memory-prefix alone
        # collided on two of the 44 pairs and silently scored 42, which raised the
        # deterministic baseline from 0.73 to 0.79 precision because both dropped items
        # were false positives. A resume key that loses items is a measurement bug, and
        # this one flattered the number it was supposed to be a control for.
        for idx, (item_id, source, memory, label) in enumerate(pairs):
            key = f"{idx}|{item_id}|{memory[:60]}"
            if log.is_done(key):
                continue
            if args.dry_run:
                log.append({"id": key, "label": label, "dry_run": True, "cost_usd": 0.0})
                continue
            verdict, path, cost, flags = escalate_verdict(
                source, memory, client, args.model, budget, cache)
            log.append({"id": key, "label": label, "verdict": verdict, "path": path,
                        "witness_flags": flags,
                        "base_verdict": factwash.check(source, memory).verdict,
                        "cost_usd": cost})
    except BudgetExceeded as e:
        print(f"\nSTOPPED ON BUDGET: {e}\nresume: --resume {log.path}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\ninterrupted; resume: --resume {log.path}", file=sys.stderr)
    finally:
        log.close()

    recs = [r for r in log.records() if not r.get("dry_run")]
    if not recs:
        print("no scored records (dry run?)")
        return 0

    def rates(verdict_key):
        tp = sum(1 for r in recs if r["label"] == "flag" and r[verdict_key] in BLOCKING)
        fn = sum(1 for r in recs if r["label"] == "flag" and r[verdict_key] not in BLOCKING)
        fp = sum(1 for r in recs if r["label"] == "pass" and r[verdict_key] in BLOCKING)
        return (tp / (tp + fn) if tp + fn else 0.0,
                tp / (tp + fp) if tp + fp else 0.0, tp, fn, fp)

    er, ep, etp, efn, efp = rates("verdict")
    br, bp, btp, bfn, bfp = rates("base_verdict")
    raised = [r for r in recs if r["base_verdict"] not in BLOCKING and r["verdict"] in BLOCKING]

    summary = {
        "n": len(recs), "model": args.model,
        "deterministic": {"recall": bp and br, "precision": bp, "tp": btp, "fn": bfn, "fp": bfp},
        "escalate": {"recall": er, "precision": ep, "tp": etp, "fn": efn, "fp": efp},
        "verdicts_raised_by_the_witness": len(raised),
        "raised_correctly": sum(1 for r in raised if r["label"] == "flag"),
        "raised_wrongly": sum(1 for r in raised if r["label"] == "pass"),
        "spend_usd": round(budget.spent_usd, 4),
        "interpretation_caveat": (
            "Verdict-level, on 44 hand-labelled real extractor writes. Claim-local "
            "escalation, not the whole-transcript version in stance_tagger.py. n is "
            "small; the raised-wrongly count is the number that decides shipping."),
    }
    out = log.write_summary(summary)

    print(f"\n{'':14s} {'recall':>7s} {'precision':>10s}")
    print(f"{'deterministic':14s} {br:7.2f} {bp:10.2f}")
    print(f"{'escalate':14s} {er:7.2f} {ep:10.2f}")
    print(f"\nwitness raised {len(raised)} verdict(s): "
          f"{summary['raised_correctly']} correctly, {summary['raised_wrongly']} wrongly")
    print(f"spend: ${budget.spent_usd:.4f}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
