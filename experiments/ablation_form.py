"""Structure ablation: is it the LABELS, the LAYOUT, or just the LENGTH?

The two-cell experiment compares a labelled multi-line field record against a one-line
parenthetical. Those differ in three ways at once, and the paper currently attributes the
whole effect to the first:

    labels      SOURCE: / CERTAINTY: naming what each part is
    layout      the stance on its own lines rather than inside the sentence
    length      the field form is twelve characters longer

The length check in ``two_cell_errors.py`` could not settle this: both templates wrap the
same three strings, so the difference is a constant and there is no variance to correlate
against. Only new arms can separate them. Four forms, chosen so each adjacent pair moves
exactly one thing:

    field       labels + multi-line             ~76 chars
    unlabelled  no labels + multi-line          ~60 chars
    sentences   no labels + single line, verbose ~79 chars
    paren       no labels + single line, short   ~62 chars

    field  vs unlabelled   isolates LABELS   (layout held constant)
    unlabelled vs paren    isolates LAYOUT   (length roughly held)
    sentences  vs paren    isolates LENGTH   (layout and labels held)
    field  vs sentences    labels + layout, at MATCHED length

Only the two new arms are run. The filler notes and the target's position are drawn from
``Random(f"{seed}|{pid}|{level}|{rep}")``, which does not depend on the arm, so passing
the same seed, levels and replicate count as the existing sixty-claim run gives these
arms byte-identical surroundings to the field and paren data already collected. That is
worth two hundred dollars of nothing: the comparison is exact without re-running the
arms we already paid for.
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

from claims_corpus import get as get_corpus  # noqa: E402
from two_cell_pressure import (BLIND_SYS, COMPRESS_HEAD, COMPRESS_TAIL,  # noqa: E402
                               PRESSURE, RATES, RATE_FALLBACK, build_notes,
                               read_verdict)
import random  # noqa: E402


def field_note(claim, source, certainty):
    return f"{claim}\nSOURCE: {source}\nCERTAINTY: {certainty}"


def paren_note(claim, source, certainty):
    return f"{claim} (per {source}; {certainty})"


def unlabelled_note(claim, source, certainty):
    """Same layout as the field record, same words, no labels naming the parts."""
    return f"{claim}\nfrom {source}\n{certainty}"


def sentences_note(claim, source, certainty):
    """Same information as prose sentences: no labels, no line breaks, but long.

    Length-matched to the field record rather than to the parenthetical, so that if the
    field record's advantage is really an advantage of having more text, this arm gets
    it too.
    """
    return f"{claim}. This came from {source}. It is {certainty}."


def padded_note(claim, source, certainty):
    """The parenthetical, padded to roughly the length of ``sentences_note``.

    The padding is a full sentence, so this arm matches ``sentences`` in token count and
    in having more than one sentence, and it carries NO epistemic content: no source, no
    certainty, no date, nothing that implies the claim was checked. The stance stays
    exactly where ``paren`` puts it, subordinate inside the clause.

    This is the control that separates the two explanations the first ablation left
    tangled. If padding alone recovers the advantage, more tokens survive and the
    mechanism is dull. If padding does nothing, then what matters is that the stance is
    stated as its own proposition rather than tucked into a parenthetical, which is a
    claim about syntax rather than about length.
    """
    return f"{claim} (per {source}; {certainty}). Filed with the rest."


ARMS = {"field": field_note, "paren": paren_note,
        "unlabelled": unlabelled_note, "sentences": sentences_note,
        "padded": padded_note}


def load_env():
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--corpus", default="all")
    ap.add_argument("--arms", default="unlabelled,sentences")
    ap.add_argument("--levels", default="brutal,severe")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--seed", type=int, default=700)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--max-calls", type=int, default=2000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pairs = get_corpus(args.corpus)
    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    arms = [x.strip() for x in args.arms.split(",") if x.strip()]
    bad = [a for a in arms if a not in ARMS]
    if bad:
        raise SystemExit(f"unknown arm(s) {bad}; known: {sorted(ARMS)}")
    print(f"{len(pairs)} claims x {len(levels)} levels x {args.reps} reps x "
          f"{len(arms)} arms = {len(pairs) * len(levels) * args.reps * len(arms)} trials")

    # show the length profile so a reader can see the design is what it claims
    ex = pairs[0]
    print("length profile on the first claim:")
    for a in sorted(ARMS):
        print(f"  {a:<11} {len(ARMS[a](ex[1], ex[2], ex[3])):>4} chars")

    rate_in, rate_out = RATES.get(args.model, RATE_FALLBACK)
    tel, calls = [], {"n": 0}

    def spent():
        return (sum(t["tokens_in"] for t in tel) * rate_in
                + sum(t["tokens_out"] for t in tel) * rate_out) / 1_000_000

    if args.dry_run:
        def ask(system, user, temp=None):
            out = ('{"presented_as": "qualified", "cue": "rumor"}'
                   if "look up" in system else "Alice may have admin access (rumor).")
            tel.append({"tokens_in": len(user) // 4, "tokens_out": 12,
                        "latency_ms": 0.0})
            return out
    else:
        load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("no ANTHROPIC_API_KEY; aborting before any call")
        import anthropic
        client = anthropic.Anthropic()

        def ask(system, user, temp=None):
            if calls["n"] >= args.max_calls:
                raise SystemExit(f"hard stop at --max-calls {args.max_calls}")
            if spent() >= args.max_usd:
                raise SystemExit(f"hard stop at --max-usd {args.max_usd} "
                                 f"(measured ${spent():.4f}); done rows are on disk")
            calls["n"] += 1
            t0 = time.perf_counter()
            r = client.messages.create(
                model=args.model, max_tokens=500, system=system,
                temperature=args.temperature if temp is None else temp,
                messages=[{"role": "user", "content": user}])
            tel.append({"tokens_in": r.usage.input_tokens,
                        "tokens_out": r.usage.output_tokens,
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
            return "".join(b.text for b in r.content
                           if getattr(b, "type", "") == "text").strip()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tag = "dryrun" if args.dry_run else args.model
    out_path = RAW / (f"{stamp}_ablation_{tag}_c{args.corpus}"
                      f"_n{len(pairs)}x{len(levels)}x{args.reps}_s{args.seed}.jsonl")
    done = set()
    if out_path.exists():
        done = {json.loads(l)["key"] for l in
                out_path.read_text(encoding="utf-8").splitlines() if l.strip()}

    stopped = None
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            for rep in range(args.reps):
                for level in levels:
                    n_notes, instruction = PRESSURE[level]
                    for pid, claim, source, certainty in pairs:
                        for arm in arms:
                            key = f"{pid}|{level}|{arm}|{rep}"
                            if key in done:
                                continue
                            # seed does NOT depend on the arm, which is what makes this
                            # comparable to the already-collected field/paren data
                            rng = random.Random(f"{args.seed}|{pid}|{level}|{rep}")
                            note = ARMS[arm](claim, source, certainty)
                            notes = build_notes(note, n_notes, rng)
                            user = "\n\n".join(f"- {n}" for n in notes)
                            stored = ask(COMPRESS_HEAD + instruction + COMPRESS_TAIL,
                                         user)
                            blind = ask(BLIND_SYS,
                                        f"STORED MEMORY:\n{stored}\n\n"
                                        f"CLAIM TO LOOK UP:\n{claim}", temp=0.0)
                            pa, cue, how = read_verdict(blind)
                            fh.write(json.dumps({
                                "key": key, "pair": pid, "pressure": level, "arm": arm,
                                "rep": rep, "note": note, "stored": stored,
                                "blind_presented_as": pa, "blind_cue": cue,
                                "blind_parsed_how": how, "blind_raw": blind[:400],
                                "qualified": int(pa == "qualified"),
                                "absent": int(pa == "absent"),
                            }) + "\n")
                            fh.flush()
                            os.fsync(fh.fileno())
                    print(f"  rep {rep + 1}/{args.reps} {level} "
                          f"({calls['n']} calls, ${spent():.4f} of ${args.max_usd})")
    except SystemExit as e:
        stopped = str(e)
        print(stopped)

    score(out_path, tel, spent() if not args.dry_run else 0.0, stopped, args.model)
    return 0


def score(path, tel, usd, stopped, model):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    if not rows:
        print("no rows")
        return
    s = {"model": model, "n": len(rows), "stopped_early": stopped, "by_arm": {}}
    for arm in sorted({r["arm"] for r in rows}):
        a = [r for r in rows if r["arm"] == arm]
        k = sum(r["qualified"] for r in a)
        s["by_arm"][arm] = {"n": len(a), "qualified": k, "rate": round(k / len(a), 4)}
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
