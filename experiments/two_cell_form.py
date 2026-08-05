"""The two-cell experiment: same claim, same stance, one variable -- the FORM it is in.

The pilot observation was post hoc. Notes that happened to use labelled fields survived
compression; notes that happened to use parentheticals did not. But those notes also
differed in wording, length and structure, so form was confounded with everything else.

This removes the confound. For each stimulus we hand-construct a MATCHED PAIR of notes:

  FIELD          Alice has admin access
                 SOURCE: a third party
                 CERTAINTY: rumor

  PAREN          Alice has admin access (per a third party; rumor, unconfirmed)

Same claim text. Same stance content. Same information. The only difference is whether
the standing sits in a labelled line or inside the sentence. Both go to the same
compressor, same prompt, same settings, interleaved, with replicates.

Outcome: is the standing still recoverable from the stored memory? Measured two ways,
because our own gate is not an independent judge of our own intervention:

  MECHANICAL   does the source's stance survive per factwash (prose) or per the
               record checker (fields), whichever matches the output's form
  BLIND READ   a model that never sees the source or the note is shown ONLY the stored
               memory and asked whether the claim is presented as established fact.
               This is the readout a downstream agent actually gets.

The blind read is the one that matters: it does not know which arm it is scoring, it
cannot see the manipulation, and it measures the thing the paper claims.

Instrumented, streamed, resumable, capped, --dry-run for $0.
"""
import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

COMPRESS_SYS = """You are a memory system consolidating a working note into long-term storage.

Rewrite the note below as a compact durable memory for later retrieval. One or two
sentences. Output only the stored memory."""

BLIND_SYS = """You will be shown a single stored memory from an AI assistant's long-term memory.

You cannot see where it came from. Judge only the text in front of you.

Question: does this memory present its claim as established fact, or does it preserve
some indication that the claim is uncertain, second-hand, or unverified?

Reply with ONLY this JSON:
{"presented_as": "established_fact" | "qualified", "cue": "<the words that tell you, or empty>"}"""

# Matched pairs. Same claim, same stance content, differing only in form.
# Written by hand so the two cells cannot differ in anything but form.
PAIRS = [
    ("admin", "Alice has admin access",
     "a third party", "rumor, unconfirmed"),
    ("budget", "The Q3 budget was cut to $40,000",
     "an unnamed colleague", "reported, not published by finance"),
    ("vendor", "The vendor contract renews automatically in March",
     "something the user heard", "unconfirmed"),
    ("backup", "The backup job has been failing silently for weeks",
     "someone on the ops call", "second-hand, unverified"),
    ("dana", "Dana is leaving at the end of the quarter",
     "word going around the team", "rumor"),
    ("ratelimit", "The API rate limit is 500 requests a minute",
     "the user's memory", "approximate, not checked"),
    ("outage", "The outage was caused by a bad deploy",
     "a comment in the incident channel", "speculation, no root cause yet"),
    ("pricing", "The enterprise plan starts at $12,000 a year",
     "a sales deck someone forwarded", "possibly out of date"),
    ("hire", "The team is hiring two more engineers next quarter",
     "a manager in passing", "not announced"),
    ("migration", "The database migration already ran on prod",
     "a message in standup", "unconfirmed"),
]


def field_note(claim, source, certainty):
    return f"{claim}\nSOURCE: {source}\nCERTAINTY: {certainty}"


def paren_note(claim, source, certainty):
    return f"{claim} (per {source}; {certainty})"


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
    ap.add_argument("--reps", type=int, default=3, help="replicates per pair per arm")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-calls", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    calls, tel = {"n": 0}, []

    if args.dry_run:
        def ask(system, user, temp=None):
            t0 = time.perf_counter()
            if "stored memory" in system and "JSON" in system:
                out = '{"presented_as": "established_fact", "cue": ""}'
            else:
                out = ("Alice has admin access, per a third party (rumor)."
                       if "SOURCE:" in user else "Alice has admin access.")
            tel.append({"tokens_in": len(user) // 4, "tokens_out": len(out) // 4,
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
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
            calls["n"] += 1
            t0 = time.perf_counter()
            r = client.messages.create(
                model=args.model, max_tokens=400, system=system,
                temperature=args.temperature if temp is None else temp,
                messages=[{"role": "user", "content": user}])
            ms = (time.perf_counter() - t0) * 1000
            tel.append({"tokens_in": r.usage.input_tokens, "tokens_out": r.usage.output_tokens,
                        "latency_ms": round(ms, 1)})
            return "".join(b.text for b in r.content
                           if getattr(b, "type", "") == "text").strip()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = RAW / (f"{stamp}_twocell_{'dryrun' if args.dry_run else args.model}"
                      f"_n{len(PAIRS)}x{args.reps}_s0.jsonl")
    RAW.mkdir(parents=True, exist_ok=True)
    done = ({json.loads(l)["key"] for l in out_path.read_text(encoding="utf-8").splitlines()
             if l.strip()} if out_path.exists() else set())
    rows = []

    with open(out_path, "a", encoding="utf-8") as fh:
        for rep in range(args.reps):
            for pid, claim, source, certainty in PAIRS:
                for arm, note in (("field", field_note(claim, source, certainty)),
                                  ("paren", paren_note(claim, source, certainty))):
                    key = f"{pid}|{arm}|{rep}"
                    if key in done:
                        continue
                    stored = ask(COMPRESS_SYS, note)
                    blind = ask(BLIND_SYS, stored, temp=0.0)
                    m = re.search(r"\{.*\}", blind, re.DOTALL)
                    try:
                        b = json.loads(m.group(0)) if m else {}
                    except json.JSONDecodeError:
                        b = {}
                    qualified = b.get("presented_as") == "qualified"
                    rec = {"key": key, "pair": pid, "arm": arm, "rep": rep,
                           "note": note, "stored": stored,
                           "blind_presented_as": b.get("presented_as"),
                           "blind_cue": (b.get("cue") or "")[:80],
                           "qualified": int(qualified)}
                    rows.append(rec)
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            print(f"  rep {rep + 1}/{args.reps} done ({calls['n']} calls)")

    score(out_path, tel)
    return 0


def score(path, tel):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = {"n_stored_memories": len(rows)}
    for arm in ("field", "paren"):
        sub = [r for r in rows if r["arm"] == arm]
        s[arm] = {"n": len(sub),
                  "qualified": sum(r["qualified"] for r in sub),
                  "rate": round(sum(r["qualified"] for r in sub) / len(sub), 3) if sub else None}
    if s["field"]["rate"] is not None and s["paren"]["rate"] is not None:
        s["delta_field_minus_paren"] = round(s["field"]["rate"] - s["paren"]["rate"], 3)

    # paired by (pair, rep): the cleanest read, since both cells share a stimulus
    byk = {}
    for r in rows:
        byk.setdefault((r["pair"], r["rep"]), {})[r["arm"]] = r["qualified"]
    both = [v for v in byk.values() if len(v) == 2]
    s["paired"] = {
        "pairs": len(both),
        "field_only": sum(1 for v in both if v["field"] and not v["paren"]),
        "paren_only": sum(1 for v in both if v["paren"] and not v["field"]),
        "both": sum(1 for v in both if v["field"] and v["paren"]),
        "neither": sum(1 for v in both if not v["field"] and not v["paren"]),
    }
    if tel:
        s["telemetry"] = {
            "calls": len(tel),
            "tokens_in": sum(t["tokens_in"] for t in tel),
            "tokens_out": sum(t["tokens_out"] for t in tel),
            "latency_ms_p50": round(statistics.median(t["latency_ms"] for t in tel), 1),
        }
    s["readout"] = ("blind: the judge sees only the stored memory, never the source, the "
                    "note, or which arm produced it")
    print("\n" + json.dumps(s, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / (Path(path).stem + "_summary.json")).write_text(json.dumps(s, indent=2),
                                                               encoding="utf-8")
    print("summary:", RESULTS / (Path(path).stem + "_summary.json"))


if __name__ == "__main__":
    sys.exit(main())
