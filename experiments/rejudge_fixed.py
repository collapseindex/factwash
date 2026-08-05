"""Re-score every stored memory with ONE fixed judge.

In the two-cell runs the compressor and the blind reader are the same model. That is a
confound sitting directly under the paper's most interesting claim: if Sonnet compresses
differently AND reads differently, a null on Sonnet could be a fact about Sonnet's
reading rather than about Sonnet's compression. Each model, in effect, graded its own
homework.

This fixes it without paying for compression again. The stored memories are already on
disk in the run ledgers, so re-scoring is one judge call each. One model judges all of
them, so whatever bias that judge has is applied equally to every arm, every pressure
level and every compressor. A judge that is uniformly wrong cannot manufacture a
difference BETWEEN models; only a judge that varies with the thing being measured can,
and a fixed judge does not vary.

The judge still never sees the source note, the arm, or which model produced the memory.

Output is a new ledger keyed to the original row, so the two scorings can be compared
per item rather than only in aggregate: the interesting quantity is not just whether the
verdicts differ, but whether they differ ASYMMETRICALLY by arm, which is what would have
biased the original result.
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

from claims_corpus import CORPORA  # noqa: E402
from two_cell_pressure import BLIND_SYS, RATES, RATE_FALLBACK, read_verdict  # noqa: E402

CLAIM_TEXT = {c[0]: c[1] for c in CORPORA["all"]}


def load_env():
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def source_rows():
    """Every scored trial from the current-instrument runs, in a stable order."""
    out = []
    for p in sorted(RAW.glob("*twocellpress_claude-*.jsonl")):
        model = p.stem.split("_twocellpress_")[1].rsplit("_n", 1)[0]
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("stored"):
                continue
            r["src_model"], r["src_run"] = model, p.stem
            out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="claude-haiku-4-5",
                    help="the one model that scores everything")
    ap.add_argument("--max-usd", type=float, default=1.20)
    ap.add_argument("--max-calls", type=int, default=2200)
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = source_rows()
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} stored memories to re-score with {args.judge}")

    rate_in, rate_out = RATES.get(args.judge, RATE_FALLBACK)
    tel, calls = [], {"n": 0}

    def spent():
        return (sum(t["tokens_in"] for t in tel) * rate_in
                + sum(t["tokens_out"] for t in tel) * rate_out) / 1_000_000

    if args.dry_run:
        def ask(user):
            out = '{"presented_as": "qualified", "cue": "may have", "unconfirmed"}'
            tel.append({"tokens_in": len(user) // 4, "tokens_out": 20,
                        "latency_ms": 0.0})
            return out
    else:
        load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("no ANTHROPIC_API_KEY; aborting before any call")
        import anthropic
        client = anthropic.Anthropic()

        def ask(user):
            if calls["n"] >= args.max_calls:
                raise SystemExit(f"hard stop at --max-calls {args.max_calls}")
            if spent() >= args.max_usd:
                raise SystemExit(f"hard stop at --max-usd {args.max_usd} "
                                 f"(measured ${spent():.4f}); all done rows are on disk")
            calls["n"] += 1
            t0 = time.perf_counter()
            r = client.messages.create(
                model=args.judge, max_tokens=300, system=BLIND_SYS, temperature=0.0,
                messages=[{"role": "user", "content": user}])
            tel.append({"tokens_in": r.usage.input_tokens,
                        "tokens_out": r.usage.output_tokens,
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
            return "".join(b.text for b in r.content
                           if getattr(b, "type", "") == "text").strip()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tag = "dryrun" if args.dry_run else args.judge
    out_path = RAW / f"{stamp}_rejudge_{tag}_n{len(rows)}_s0.jsonl"
    done = set()
    for prev in sorted(RAW.glob(f"*_rejudge_{tag}_*.jsonl")):
        for line in prev.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["uid"])
    if done:
        print(f"resuming: {len(done)} already scored in earlier ledgers")

    stopped = None
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            for i, r in enumerate(rows):
                uid = f"{r['src_run']}|{r['key']}"
                if uid in done:
                    continue
                claim = CLAIM_TEXT.get(r["pair"])
                if not claim:
                    continue
                reply = ask(f"STORED MEMORY:\n{r['stored']}\n\n"
                            f"CLAIM TO LOOK UP:\n{claim}")
                pa, cue, how = read_verdict(reply)
                fh.write(json.dumps({
                    "uid": uid, "src_run": r["src_run"], "src_model": r["src_model"],
                    "pair": r["pair"], "pressure": r["pressure"], "arm": r["arm"],
                    "rep": r["rep"], "judge": args.judge,
                    "orig_verdict": r.get("blind_presented_as"),
                    "new_verdict": pa, "new_cue": cue, "parsed_how": how,
                    "agree": int(pa == r.get("blind_presented_as")),
                }) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                if (i + 1) % 200 == 0:
                    print(f"  {i + 1}/{len(rows)}  ${spent():.4f} of ${args.max_usd}")
    except SystemExit as e:
        stopped = str(e)
        print(stopped)

    score(out_path, tel, spent() if not args.dry_run else 0.0, stopped, args.judge)
    return 0


def score(path, tel, usd, stopped, judge):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    if not rows:
        print("no rows scored")
        return
    s = {"judge": judge, "n": len(rows), "stopped_early": stopped,
         "agreement_with_original": round(sum(r["agree"] for r in rows) / len(rows), 4)}

    # The number that matters: does the re-scoring move the two arms DIFFERENTLY?
    # A judge that is uniformly harsher changes both arms and no conclusion; a judge
    # that is harsher on one arm is the thing that could have faked the original result.
    for arm in ("field", "paren"):
        a = [r for r in rows if r["arm"] == arm]
        if not a:
            continue
        s[arm] = {
            "n": len(a),
            "orig_qualified": sum(r["orig_verdict"] == "qualified" for r in a),
            "new_qualified": sum(r["new_verdict"] == "qualified" for r in a),
            "agreement": round(sum(r["agree"] for r in a) / len(a), 4),
        }
    if "field" in s and "paren" in s:
        of = s["field"]["orig_qualified"] / s["field"]["n"]
        op = s["paren"]["orig_qualified"] / s["paren"]["n"]
        nf = s["field"]["new_qualified"] / s["field"]["n"]
        np_ = s["paren"]["new_qualified"] / s["paren"]["n"]
        s["delta_original_judge"] = round(of - op, 4)
        s["delta_fixed_judge"] = round(nf - np_, 4)

    by_model = {}
    for m in sorted({r["src_model"] for r in rows}):
        sub = [r for r in rows if r["src_model"] == m]
        f = [r for r in sub if r["arm"] == "field"]
        p = [r for r in sub if r["arm"] == "paren"]
        if not f or not p:
            continue
        by_model[m] = {
            "n_pairs_rows": len(sub),
            "delta_original_judge": round(
                sum(r["orig_verdict"] == "qualified" for r in f) / len(f)
                - sum(r["orig_verdict"] == "qualified" for r in p) / len(p), 4),
            "delta_fixed_judge": round(
                sum(r["new_verdict"] == "qualified" for r in f) / len(f)
                - sum(r["new_verdict"] == "qualified" for r in p) / len(p), 4),
            "agreement": round(sum(r["agree"] for r in sub) / len(sub), 4),
        }
    s["by_source_model"] = by_model
    if tel:
        s["telemetry"] = {"calls": len(tel), "usd": round(usd, 4),
                          "tokens_in": sum(t["tokens_in"] for t in tel),
                          "tokens_out": sum(t["tokens_out"] for t in tel),
                          "latency_ms_p50": round(
                              statistics.median(t["latency_ms"] for t in tel), 1)}
    print("\n" + json.dumps(s, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / (Path(path).stem + "_summary.json")).write_text(
        json.dumps(s, indent=2), encoding="utf-8")
    print("summary:", RESULTS / (Path(path).stem + "_summary.json"))


if __name__ == "__main__":
    sys.exit(main())
