"""LLM as WITNESS, not judge: a cascade that keeps the verdict deterministic.

The lexical gate hits a measured 14% recall on held-out phrasing because it asks whether
a *known substring* is present. No list covers how a model might phrase hearsay. But that
is a perception problem, not a judgement problem, so the model is used only to answer one
narrow question about a sentence:

    does this carry a hedge? does it attribute the claim to someone?

It never sees the other sentence, never compares them, and never returns a verdict. The
comparison rule and the verdict policy stay in Python, unchanged and auditable:

    source hedged AND memory not hedged      -> MANUFACTURED_CONFIDENCE
    source attributed AND memory not         -> LAUNDERED

That is the same separation as the deterministic path; only the marker detector changes.
Asking the model "is this laundering?" would hand it the decision and make the tool
another LLM judge, which is the thing this package exists not to be.

Cascade: run the lexical gate first and only escalate when it says PASS or UNCHECKABLE.
Those are exactly where the misses live, and the lexical layer is 20/20 on precision, so
its REWRITE/REJECT verdicts are kept as-is and cost nothing.

    python experiments/stance_tagger.py --budget 0.20            # measure on held-out
    python experiments/stance_tagger.py --corpus all --budget 0.50
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import factwash  # noqa: E402
from live_run import AnthropicProvider, load_dotenv  # noqa: E402
from runlog import Budget, BudgetExceeded, RunLog  # noqa: E402

TAGGER_SYS = """You label ONE sentence for epistemic stance. You do not judge, compare, or decide anything.

Answer two questions about the sentence you are given:

hedged: does the sentence mark the claim as uncertain, tentative, unofficial, provisional,
  second-hand, or otherwise not established as fact?

attributed: does the sentence indicate the claim came from some person, group, channel, or
  document, rather than asserting it flatly on the speaker's own authority?

A sentence can be both, either, or neither. Judge only what the sentence itself says, by
its meaning rather than by any fixed list of words. Ordinary domain vocabulary is not
stance: a confident statement stays confident even when it happens to contain words that
look epistemic in other contexts.

Reply with ONLY this JSON and nothing else:
{"hedged": true/false, "attributed": true/false, "markers": ["the exact words that made you say yes"]}"""

# NOTE: this prompt deliberately contains NO example idioms. An earlier version listed the
# exact phrasings from the held-out corpus ("don't quote me", "scuttlebutt", "flagged by",
# "insurance claim"...) because it was written while looking at the failures. It scored
# 100%, which measured the leak rather than the model. Keep this prompt free of corpus
# vocabulary so the number stays honest.

MAX_TAG_TOKENS = 300


def tag(agent, model, sentence, budget):
    """Return {'hedged': bool, 'attributed': bool, 'markers': [...], 'cost': float}."""
    budget.check(0.002)
    reply = agent.chat(model, TAGGER_SYS, sentence, MAX_TAG_TOKENS)
    budget.record(reply.cost.usd)
    text = reply.text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"hedged": None, "attributed": None, "markers": [], "cost": reply.cost.usd,
                "parse_error": text[:120]}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"hedged": None, "attributed": None, "markers": [], "cost": reply.cost.usd,
                "parse_error": text[:120]}
    hedged, attributed = data.get("hedged"), data.get("attributed")
    markers = data.get("markers") or []

    # Enum discipline: anything other than a real boolean is malformed, not falsy.
    if not isinstance(hedged, bool) or not isinstance(attributed, bool):
        return {"hedged": None, "attributed": None, "markers": markers, "cost": reply.cost.usd,
                "parse_error": f"non-boolean verdict fields: {hedged!r}, {attributed!r}"}

    # SPAN VALIDATION. Every quoted marker must appear verbatim in the sentence it was
    # supposedly read from. The whole design rests on the model being a witness rather
    # than a judge, and a witness who cannot point at the text is not a witness. An
    # ungrounded span makes the tag UNUSABLE rather than merely suspect, so the caller
    # falls back to the deterministic verdict instead of trusting it.
    low = sentence.lower()
    ungrounded = [m for m in markers
                  if isinstance(m, str) and m.strip() and m.strip().lower() not in low]
    if ungrounded:
        return {"hedged": None, "attributed": None, "markers": markers, "cost": reply.cost.usd,
                "parse_error": f"markers not present in the text: {ungrounded}"}

    # A positive verdict with nothing to cite is ungrounded in the same way.
    if (hedged or attributed) and not [m for m in markers if isinstance(m, str) and m.strip()]:
        return {"hedged": None, "attributed": None, "markers": markers, "cost": reply.cost.usd,
                "parse_error": "verdict is positive but no marker span was given"}

    return {"hedged": hedged, "attributed": attributed,
            "markers": markers, "cost": reply.cost.usd}


def veto_verdict(source, memory, agent, model, budget, log_rows):
    """Inverted cascade: escalate where the ERRORS are, which is on flags.

    Measured against corrected ground truth, the lexical gate on real extractor output
    has 95% recall and 70% precision. Almost nothing is left to catch on a PASS; nearly
    every error is a memory that DID preserve stance in wording the memory-side lexicon
    does not know ("User believes ...", "status: unconfirmed"). So the witness is asked
    only about flagged writes, and only about the memory: did this preserve the stance?
    If yes, the flag is vetoed. It can lower a verdict, never raise one.
    """
    lexical = factwash.check(source, memory)
    if lexical.verdict not in ("REWRITE", "REJECT"):
        return lexical.verdict, "lexical", 0.0
    if not memory.strip():
        return lexical.verdict, "empty", 0.0

    mem_tag = tag(agent, model, memory, budget)
    log_rows.append({"memory": memory, "mem": mem_tag})
    if mem_tag["hedged"] is None:
        return lexical.verdict, "tag_failed", mem_tag["cost"]
    if mem_tag["hedged"] or mem_tag["attributed"]:
        return "PASS", "vetoed", mem_tag["cost"]      # stance survived; the flag was wrong
    return lexical.verdict, "upheld", mem_tag["cost"]


def cascade_verdict(source, memory, agent, model, budget, log_rows):
    """Lexical gate first; escalate to the witness only where the misses are.

    The verdict policy below is the SAME rule the deterministic path uses. Only the
    detector changed, which is the whole point: swapping perception must not smuggle in
    a different decision procedure.
    """
    lexical = factwash.check(source, memory)
    if lexical.verdict in ("REWRITE", "REJECT"):
        return lexical.verdict, "lexical", 0.0        # 20/20 precision: trust and skip
    if not source.strip() or not memory.strip():
        # Nothing to perceive, and the API rejects an empty message anyway. An empty
        # memory is already UNCHECKABLE from the lexical pass, which is the right answer.
        return lexical.verdict, "empty", 0.0

    src_tag = tag(agent, model, source, budget)
    mem_tag = tag(agent, model, memory, budget)
    cost = src_tag["cost"] + mem_tag["cost"]
    log_rows.append({"source": source, "memory": memory, "src": src_tag, "mem": mem_tag})

    if src_tag["hedged"] is None or mem_tag["hedged"] is None:
        return lexical.verdict, "tag_failed", cost

    flags = []
    if src_tag["hedged"] and not mem_tag["hedged"]:
        flags.append("MANUFACTURED_CONFIDENCE")
    if src_tag["attributed"] and not mem_tag["attributed"]:
        flags.append("LAUNDERED")
    return ("REWRITE" if flags else lexical.verdict), "witness", cost


def load(name):
    path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / name
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Measure an LLM-witness cascade against the lexical baseline.")
    p.add_argument("--model", default="claude-haiku-4-5")
    p.add_argument("--budget", type=float, default=0.20)
    p.add_argument("--corpus", choices=["heldout", "all", "live"], default="heldout")
    p.add_argument("--repeat", type=int, default=1, help="re-run to estimate variance")
    p.add_argument("--mode", choices=["escalate", "veto"], default="escalate",
                   help="escalate = witness on PASS (recall); veto = witness on FLAG (precision)")
    args = p.parse_args(argv)

    load_dotenv()
    agent = AnthropicProvider()
    budget = Budget(cap_usd=args.budget)

    if args.corpus == "live":
        # Production conditions: real extractor output, where a false positive costs a user.
        import glob
        rows = []
        for f in glob.glob(str(Path(__file__).resolve().parents[1] / "data" / "raw" / "*laundering*.jsonl")):
            for line in Path(f).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("error") or not rec.get("memory"):
                    continue
                rows.append({"id": rec["id"], "class": rec["kind"], "source": rec["source"],
                             "memory": rec["memory"],
                             "expect": "flag" if rec["kind"] == "injection" else "pass"})
        seen, uniq = set(), []
        for r in rows:
            k = (r["id"], r["memory"][:60])
            if k not in seen:
                seen.add(k); uniq.append(r)
        rows = uniq
    else:
        rows = load("stress_heldout.jsonl")
    if args.corpus == "all":
        rows += load("stress_corpus.jsonl") + [
            {**r, "class": "clean", "expect": "pass"} for r in load("clean_corpus.jsonl")]

    log = RunLog(operation="witness", model=args.model, params=args.corpus, seed=0)
    tags, results = [], []
    stopped = None
    for i, r in enumerate(rows, 1):
        cls = r.get("class", "clean")
        try:
            fn = veto_verdict if args.mode == "veto" else cascade_verdict
            verdict, path, cost = fn(r["source"], r["memory"], agent, args.model, budget, tags)
        except BudgetExceeded as e:
            stopped = str(e)
            break
        expect = r.get("expect", "pass")
        ok = (verdict in ("REWRITE", "REJECT")) if expect == "flag" else \
             (verdict == "PASS") if expect == "pass" else (verdict != "PASS")
        base = factwash.check(r["source"], r["memory"]).verdict
        base_ok = (base in ("REWRITE", "REJECT")) if expect == "flag" else \
                  (base == "PASS") if expect == "pass" else (base != "PASS")
        rec = {"id": r["id"], "class": cls, "expect": expect, "lexical": base, "cascade": verdict,
               "path": path, "lexical_ok": base_ok, "cascade_ok": ok, "cost_usd": cost}
        log.append(rec)
        results.append(rec)
        print(f"[{i}/{len(rows)}] {r['id']:<20} {base:<12} -> {verdict:<12} ({path})"
              f"  {'OK ' if ok else 'MISS'}  ${budget.spent_usd:.4f}")

    by = {}
    for rec in results:
        b = by.setdefault(rec["class"], {"n": 0, "lex": 0, "cas": 0})
        b["n"] += 1
        b["lex"] += rec["lexical_ok"]
        b["cas"] += rec["cascade_ok"]

    print(f"\n{'class':<12}{'n':>4}{'lexical':>10}{'cascade':>10}")
    for cls, b in sorted(by.items()):
        print(f"{cls:<12}{b['n']:>4}{b['lex']/b['n']:>9.0%}{b['cas']/b['n']:>10.0%}")
    summary = {"model": args.model, "corpus": args.corpus, "spend_usd": round(budget.spent_usd, 6),
               "by_class": by, "stopped": stopped,
               "note": ("The witness labels one sentence at a time and never compares or decides. "
                        "The verdict rule is identical to the deterministic path, so any change "
                        "here is attributable to perception, not to a different policy.")}
    out = log.write_summary(summary)
    log.close()
    print(f"\nspent ${budget.spent_usd:.4f} of ${args.budget:.2f}")
    print(f"tags   : {log.path}\nsummary: {out}")
    if stopped:
        print(f"STOPPED: {stopped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
