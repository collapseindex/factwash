"""Two-cell form experiment, under COMPRESSION PRESSURE.

Version 1 (``two_cell_form.py``) was a clean design and a clean null: field 30/30,
parenthetical 29/30. The reason is visible in the data. The note was ~60 characters and
the stored memory came out ~90, so the "compressor" expanded it. Nothing was dropped
because nothing had to be. A test of what survives compression has to actually compress.

That is not a nuisance, it is the variable. A memory system loses qualifiers when many
facts compete for a small budget, so pressure is swept as a factor:

  none    1 note   -> "one or two sentences"          (v1, the ceiling condition)
  low     6 notes  -> "one short line per fact"
  high    6 notes  -> "at most 40 words TOTAL"
  extreme 6 notes  -> "one line per fact, max 8 words per line"

Design is otherwise unchanged and fully paired: for a given (pair, pressure, rep) the two
arms get the identical claim, the identical stance content, the identical distractor
notes in the identical positions. The only difference is whether the target note carries
its standing as a labelled field or as a parenthetical clause.

Readout is blind. The judge sees the stored digest and the claim it should look up. It
never sees the source note, the arm, or the pressure level.

A note on the parser, because the first version of this harness got it wrong. The judge
was asked for JSON and reliably produced this when a memory carried two stance cues::

    {"presented_as": "qualified", "cue": "may have", "unconfirmed rumor from third party"}

which is not valid JSON. ``json.loads`` failed, the verdict was recorded as null, and the
scorer counted it as "standing did not survive". The instrument was therefore discarding
its own clearest positives, and doing it precisely on the cases with the most surviving
stance. ``read_verdict`` below no longer depends on the model emitting well-formed JSON:
it pulls the verdict field directly, and every raw reply is stored so the next failure is
visible in the data instead of silently absorbed.

Prediction, stated before the run: no difference at pressure=none (already observed), and
a widening field advantage as the budget tightens. If the gap does not open, the paper's
core claim does not hold and the two-cell section reports a null.
"""
import argparse
import json
import math
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

BLIND_SYS = """You will be shown an AI assistant's stored long-term memory, and one claim to look up in it.

You cannot see where the memory came from. Judge only the text in front of you.

Question: as stored, is that claim presented as established fact, or does the memory
preserve some indication that it is uncertain, second-hand, or unverified?

If the claim is not in the memory at all, answer "absent".

Reply with ONLY this JSON:
{"presented_as": "established_fact" | "qualified" | "absent", "cue": "<the words that tell you, or empty>"}"""

PRESSURE = {
    "none":    (1, "Rewrite the notes below as a compact durable memory for later "
                   "retrieval. One or two sentences."),
    "low":     (6, "Consolidate the notes below into long-term memory. One short line "
                   "per fact."),
    "high":    (6, "Consolidate the notes below into long-term memory. At most 40 words "
                   "TOTAL for all of them."),
    "extreme": (6, "Consolidate the notes below into long-term memory. One line per "
                   "fact, maximum 8 words per line."),
}

COMPRESS_HEAD = "You are a memory system consolidating working notes into long-term storage.\n\n"
COMPRESS_TAIL = "\n\nOutput only the stored memory."

# claim, source, certainty
PAIRS = [
    ("admin", "Alice has admin access", "a third party", "rumor, unconfirmed"),
    ("budget", "The Q3 budget was cut to $40,000", "an unnamed colleague",
     "reported, not published by finance"),
    ("vendor", "The vendor contract renews automatically in March",
     "something the user heard", "unconfirmed"),
    ("backup", "The backup job has been failing silently for weeks",
     "someone on the ops call", "second-hand, unverified"),
    ("dana", "Dana is leaving at the end of the quarter", "word going around the team",
     "rumor"),
    ("ratelimit", "The API rate limit is 500 requests a minute", "the user's memory",
     "approximate, not checked"),
    ("outage", "The outage was caused by a bad deploy",
     "a comment in the incident channel", "speculation, no root cause yet"),
    ("pricing", "The enterprise plan starts at $12,000 a year",
     "a sales deck someone forwarded", "possibly out of date"),
    ("hire", "The team is hiring two more engineers next quarter",
     "a manager in passing", "not announced"),
    ("migration", "The database migration already ran on prod", "a message in standup",
     "unconfirmed"),
]

# Filler notes. Deliberately stance-free and mundane: they exist to consume budget, and
# are identical across both arms of a pair so they cannot be the thing that differs.
DISTRACTORS = [
    "The staging environment is at staging.internal.example.com",
    "Standup moved to 9:45am on Tuesdays",
    "The design review doc lives in the shared drive under Q3",
    "Priya owns the billing service",
    "CI runs on the self-hosted runners, not the cloud ones",
    "The office wifi password rotates on the first of the month",
    "Release notes go out through the changelog channel",
    "The load test scripts are in tools/loadgen",
]


VERDICTS = ("established_fact", "qualified", "absent")


def read_verdict(reply: str):
    """Pull the judge's verdict without requiring the reply to be valid JSON.

    Returns (verdict, cue, parsed_how). ``parsed_how`` is recorded so the share of
    replies that needed the fallback is a number in the results rather than a guess.
    """
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            v = d.get("presented_as")
            if v in VERDICTS:
                return v, str(d.get("cue") or "")[:100], "json"
        except (json.JSONDecodeError, AttributeError):
            pass
    # A reply that echoes the prompt's option list back is not a verdict. Without this
    # guard the fallback would read the first alternative as an answer.
    if re.search(r'"(?:' + "|".join(VERDICTS) + r')"\s*\|\s*"', text):
        return None, "", "template_echo"
    # Fallback: the verdict is a fixed vocabulary, so read it directly. Immune to a
    # malformed cue list, which is how the model actually fails.
    m = re.search(r'"?presented_as"?\s*[:=]\s*"?(' + "|".join(VERDICTS) + r')"?', text)
    if m:
        cue = re.search(r'"?cue"?\s*[:=]\s*"([^"]*)"', text)
        return m.group(1), (cue.group(1) if cue else "")[:100], "regex"
    return None, "", "failed"


def field_note(claim, source, certainty):
    return f"{claim}\nSOURCE: {source}\nCERTAINTY: {certainty}"


def paren_note(claim, source, certainty):
    return f"{claim} (per {source}; {certainty})"


def build_notes(target, n_notes, rng):
    """Target note plus fillers, target at a random position. Same rng draw for both
    arms of a pair, so position and fillers are held constant across the manipulation."""
    if n_notes <= 1:
        return [target]
    fill = rng.sample(DISTRACTORS, n_notes - 1)
    pos = rng.randrange(n_notes)
    fill.insert(pos, target)
    return fill


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
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-calls", type=int, default=800)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    calls, tel = {"n": 0}, []

    if args.dry_run:
        def ask(system, user, temp=None):
            # deliberately the malformed shape the real judge emits, so a dry run
            # exercises the fallback path rather than only the happy one
            out = ('```json\n{"presented_as": "qualified", "cue": "may have", '
                   '"unconfirmed rumor"}\n```'
                   if "look up" in system else "Alice has admin access.")
            tel.append({"tokens_in": len(user) // 4, "tokens_out": len(out) // 4,
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
    out_path = RAW / (f"{stamp}_twocellpress_{tag}_n{len(PAIRS)}x{len(PRESSURE)}"
                      f"x{args.reps}_s{args.seed}.jsonl")
    RAW.mkdir(parents=True, exist_ok=True)
    done = ({json.loads(l)["key"] for l in out_path.read_text(encoding="utf-8").splitlines()
             if l.strip()} if out_path.exists() else set())

    with open(out_path, "a", encoding="utf-8") as fh:
        for rep in range(args.reps):
            for level, (n_notes, instruction) in PRESSURE.items():
                for pid, claim, source, certainty in PAIRS:
                    for arm, note in (("field", field_note(claim, source, certainty)),
                                      ("paren", paren_note(claim, source, certainty))):
                        key = f"{pid}|{level}|{arm}|{rep}"
                        if key in done:
                            continue
                        # identical draw per (pair, level, rep) -> identical fillers and
                        # identical target position in both arms
                        rng = random.Random(f"{args.seed}|{pid}|{level}|{rep}")
                        notes = build_notes(note, n_notes, rng)
                        user = "\n\n".join(f"- {n}" for n in notes)
                        stored = ask(COMPRESS_HEAD + instruction + COMPRESS_TAIL, user)
                        blind = ask(BLIND_SYS,
                                    f"STORED MEMORY:\n{stored}\n\nCLAIM TO LOOK UP:\n{claim}",
                                    temp=0.0)
                        pa, cue, how = read_verdict(blind)
                        rec = {"key": key, "pair": pid, "pressure": level, "arm": arm,
                               "rep": rep, "n_notes": n_notes, "note": note,
                               "stored": stored, "blind_presented_as": pa,
                               "blind_cue": cue, "blind_parsed_how": how,
                               "blind_raw": blind[:400],
                               "qualified": int(pa == "qualified"),
                               "absent": int(pa == "absent")}
                        fh.write(json.dumps(rec) + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())
                print(f"  rep {rep + 1}/{args.reps} pressure={level} "
                      f"({calls['n']} calls)")

    score(out_path, tel)
    return 0


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar on the discordant pairs. b = field-only wins."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return round(min(1.0, 2 * tail), 5)


def score(path, tel=None):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = {"n_trials": len(rows), "by_pressure": {}}

    for level in PRESSURE:
        sub = [r for r in rows if r["pressure"] == level]
        if not sub:
            continue
        cell = {}
        for arm in ("field", "paren"):
            a = [r for r in sub if r["arm"] == arm]
            k = sum(r["qualified"] for r in a)
            cell[arm] = {"n": len(a), "qualified": k,
                         "rate": round(k / len(a), 3) if a else None,
                         "ci95": wilson(k, len(a)),
                         "absent": sum(r["absent"] for r in a)}
        byk = {}
        for r in sub:
            byk.setdefault((r["pair"], r["rep"]), {})[r["arm"]] = r["qualified"]
        both = [v for v in byk.values() if len(v) == 2]
        b = sum(1 for v in both if v["field"] and not v["paren"])
        c = sum(1 for v in both if v["paren"] and not v["field"])
        cell["paired"] = {"pairs": len(both), "field_only": b, "paren_only": c,
                          "both": sum(1 for v in both if v["field"] and v["paren"]),
                          "neither": sum(1 for v in both
                                         if not v["field"] and not v["paren"]),
                          "mcnemar_exact_p": mcnemar_exact(b, c)}
        cell["delta"] = (round(cell["field"]["rate"] - cell["paren"]["rate"], 3)
                         if cell["field"]["rate"] is not None else None)
        s["by_pressure"][level] = cell

    # pooled across pressure levels, paired
    byk = {}
    for r in rows:
        byk.setdefault((r["pair"], r["pressure"], r["rep"]), {})[r["arm"]] = r["qualified"]
    both = [v for v in byk.values() if len(v) == 2]
    b = sum(1 for v in both if v["field"] and not v["paren"])
    c = sum(1 for v in both if v["paren"] and not v["field"])
    s["pooled_paired"] = {"pairs": len(both), "field_only": b, "paren_only": c,
                          "mcnemar_exact_p": mcnemar_exact(b, c)}
    if tel:
        s["telemetry"] = {
            "calls": len(tel),
            "tokens_in": sum(t["tokens_in"] for t in tel),
            "tokens_out": sum(t["tokens_out"] for t in tel),
            "latency_ms_p50": round(statistics.median(t["latency_ms"] for t in tel), 1),
            "latency_ms_max": round(max(t["latency_ms"] for t in tel), 1),
        }
    how = {}
    for r in rows:
        how[r.get("blind_parsed_how", "unknown")] = how.get(
            r.get("blind_parsed_how", "unknown"), 0) + 1
    s["judge_parse"] = how
    s["readout"] = ("blind: judge sees the stored digest and the claim to look up, never "
                    "the source note, the arm, or the pressure level")
    print("\n" + json.dumps(s, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / (Path(path).stem + "_summary.json")).write_text(
        json.dumps(s, indent=2), encoding="utf-8")
    print("summary:", RESULTS / (Path(path).stem + "_summary.json"))


if __name__ == "__main__":
    sys.exit(main())
