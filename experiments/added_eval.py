"""Measure the ADDED witness against the blind-labelled corpus.

Ground truth: writes labelled bad with mechanism out_of_scope (wrong/invented/inferred
claims) are ADDED-positives; writes labelled pass are negatives. The two stance-loss
bad writes are excluded: they are the gate's territory, and scoring ADDED on them would
blur the two directions this repo keeps separate.

Prediction: a write is ADDED-positive when any of its sentences comes back unsupported
(the same aggregation inspect() uses). Sentences the backend could not establish are
counted as coverage loss and never as findings; a write with zero established sentences
predicts negative and is reported in the coverage figures.

Run discipline: every item is flushed and fsynced before the next call, resume skips
completed idxs, and the call counter hard-stops at --max-calls. --dry-run exercises the
whole pipeline with a stub backend for $0.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CORPUS = ROOT / "data" / "corpus"
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "data" / "results"


def _load_env():
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _items():
    sess = (CORPUS / "session_pool_enron_s0_s0.jsonl").read_text(encoding="utf-8").splitlines()
    items = {it["idx"]: it for it in (json.loads(l) for l in sess[1:] if l.strip())}
    labels = {r["idx"]: r["label"] for r in
              (json.loads(l) for l in
               (CORPUS / "session_pool_enron_s0_s0_labels.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip())}
    mechs = {m["idx"]: m["mechanism"] for m in
             (json.loads(l) for l in
              (CORPUS / "session_pool_enron_s0_s0_mechanisms.jsonl").read_text(encoding="utf-8").splitlines()
              if l.strip())}
    out = []
    for idx, lab in labels.items():
        if lab == "pass":
            out.append((idx, items[idx], 0))
        elif lab == "flag" and mechs.get(idx) == "out_of_scope":
            out.append((idx, items[idx], 1))
    return sorted(out)


def _stub_backend(source, claim):
    """Dry-run stub: deterministic, free, exercises every branch."""
    if len(claim) % 7 == 0:
        return {"support": "cannot_tell", "evidence": [], "closest": []}
    words = [w for w in claim.split() if len(w) > 4]
    hit = any(w.lower() in source.lower() for w in words)
    closest = source.split(".")[0][:60]
    return ({"support": "supported", "evidence": [closest], "closest": []} if hit
            else {"support": "unsupported", "evidence": [], "closest": [closest]})


def run(args) -> Path:
    from factwash.transform import _added_changes

    calls = {"n": 0}
    if args.dry_run:
        backend = _stub_backend
        out_path = RAW / f"{time.strftime('%Y%m%d_%H%M%S')}_addedeval_dryrun_n92_s0.jsonl"
    else:
        _load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("no ANTHROPIC_API_KEY; aborting before any call")
        from factwash.added import anthropic_added_witness
        inner = anthropic_added_witness(model=args.model)

        def backend(source, claim):
            if calls["n"] >= args.max_calls:
                raise SystemExit(f"hard stop: --max-calls {args.max_calls} reached; "
                                 f"run again to resume (nothing is lost)")
            calls["n"] += 1
            return inner(source, claim)
        out_path = RAW / (f"{time.strftime('%Y%m%d_%H%M%S')}_addedeval_"
                          f"{args.model}_n92_s0.jsonl")

    if args.resume:
        out_path = Path(args.resume)
    done = set()
    if out_path.exists():
        done = {json.loads(l)["idx"] for l in out_path.read_text(encoding="utf-8").splitlines()
                if l.strip()}
    RAW.mkdir(parents=True, exist_ok=True)

    items = _items()
    with open(out_path, "a", encoding="utf-8") as fh:
        for n, (idx, item, truth) in enumerate(items, 1):
            if idx in done:
                continue
            changes, not_established, n_sents = _added_changes(
                item["source"], item["memory"], backend)
            rec = {"idx": idx, "truth": truth, "n_sentences": n_sents,
                   "n_unsupported": len(changes), "not_established": not_established,
                   "evidence": [c.evidence for c in changes]}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            print(f"  [{n}/{len(items)}] idx {idx} truth={truth} "
                  f"unsupported={len(changes)} not_established={not_established}/{n_sents}")
    print(f"\nledger: {out_path}  (backend calls this run: {calls['n']})")
    return out_path


def score(path: Path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    tp = sum(1 for r in rows if r["truth"] == 1 and r["n_unsupported"] > 0)
    fp = sum(1 for r in rows if r["truth"] == 0 and r["n_unsupported"] > 0)
    fn = sum(1 for r in rows if r["truth"] == 1 and r["n_unsupported"] == 0)
    tn = sum(1 for r in rows if r["truth"] == 0 and r["n_unsupported"] == 0)
    sents = sum(r["n_sentences"] for r in rows)
    lost = sum(r["not_established"] for r in rows)
    summary = {
        "n_writes": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "sentence_coverage": {"sentences": sents, "not_established": lost,
                              "rate": round(lost / sents, 3) if sents else None},
        "interpretation_caveat": (
            "single-labeller ground truth (self-agreement 70%, kappa 0.47); "
            "out_of_scope approximates 'fabricated/inferred' but was labelled against a "
            "broader misleads-a-reader rubric; write-level aggregation of "
            "sentence-level answers; stance-loss bad writes excluded by design"),
    }
    print(json.dumps(summary, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / (path.stem + "_summary.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--resume", help="existing ledger to resume/score")
    ap.add_argument("--score-only", action="store_true")
    args = ap.parse_args()
    if args.score_only:
        score(Path(args.resume))
        return 0
    path = run(args)
    score(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
