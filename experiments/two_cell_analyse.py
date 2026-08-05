"""Pool and analyse the two-cell pressure runs.

Kept separate from the harness so the raw JSONL stays the record and the scoring can be
rerun, argued with, and corrected without touching the data.

Three things the harness's own summary hides:

1. ``qualified`` conflates two different failures. A claim can survive the digest with its
   standing washed off, or it can be evicted from the digest entirely. Reading the raw
   rows, eviction is not rare and it is not symmetric: the parenthetical note is the one
   that gets dropped. Both are losses for a memory system, but they are different losses
   and the paper should not report them as one number.

2. Judge replies that failed to parse are currently scored as "not qualified". That is
   noise on whichever arm it lands on rather than a bias, but it is not zero and it
   should be counted rather than absorbed.

3. The stated prediction was a widening advantage under pressure. It is reported here
   whether or not it held.

Only top-level ``data/raw`` is read. Runs collected before the judge-parser fix live in
``data/raw/superseded/`` and are deliberately out of reach: they were produced by a
different instrument and pooling them would mix two measurement regimes.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"
LEVELS = ("none", "low", "high", "extreme")


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return round(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), 6)


def load():
    rows = []
    for p in sorted(RAW.glob("*twocellpress_claude-*.jsonl")):
        model = p.stem.split("_twocellpress_")[1].rsplit("_n", 1)[0]
        run = p.stem
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["model"], r["run"] = model, run
                rows.append(r)
    return rows


def balance(rows):
    """Keep only replicates that ran to completion on every pressure level.

    The opus run stopped mid-way when the API credit ran out, leaving a replicate that
    covers the easy pressure levels and not the hard ones. Averaging that in would
    silently weight one model toward the conditions where nothing is lost. Dropped
    replicates are returned so the count can be printed rather than hidden.
    """
    want = len(LEVELS) * 2 * 10  # levels x arms x pairs
    per = defaultdict(list)
    for r in rows:
        per[(r["run"], r["rep"])].append(r)
    kept, dropped = [], []
    for key, group in sorted(per.items()):
        (kept if len(group) == want else dropped).append((key, group))
    return ([r for _, g in kept for r in g],
            [(k, len(g)) for k, g in dropped])


def outcome(r):
    pa = r.get("blind_presented_as")
    if pa == "qualified":
        return "kept_qualified"
    if pa == "established_fact":
        return "kept_washed"
    if pa == "absent":
        return "evicted"
    return "unparsed"


def block(rows, label):
    out = {"label": label, "n": len(rows)}
    for arm in ("field", "paren"):
        a = [r for r in rows if r["arm"] == arm]
        counts = defaultdict(int)
        for r in a:
            counts[outcome(r)] += 1
        k, n = counts["kept_qualified"], len(a)
        # denominator excludes unparsed judge replies; they are noise, not evidence
        n_eff = n - counts["unparsed"]
        out[arm] = {"n": n, "unparsed": counts["unparsed"],
                    "kept_qualified": counts["kept_qualified"],
                    "kept_washed": counts["kept_washed"],
                    "evicted": counts["evicted"],
                    "rate": round(k / n_eff, 3) if n_eff else None,
                    "ci95": wilson(k, n_eff)}
    if out["field"]["rate"] is not None and out["paren"]["rate"] is not None:
        out["delta"] = round(out["field"]["rate"] - out["paren"]["rate"], 3)

    byk = defaultdict(dict)
    for r in rows:
        byk[(r["run"], r["pair"], r["pressure"], r["rep"])][r["arm"]] = outcome(r)
    both = [v for v in byk.values()
            if len(v) == 2 and "unparsed" not in v.values()]
    b = sum(1 for v in both if v["field"] == "kept_qualified" != v["paren"])
    c = sum(1 for v in both if v["paren"] == "kept_qualified" != v["field"])
    out["paired"] = {"pairs": len(both), "field_only": b, "paren_only": c,
                     "both": sum(1 for v in both
                                 if v["field"] == v["paren"] == "kept_qualified"),
                     "mcnemar_exact_p": mcnemar(b, c)}
    # eviction, the second outcome
    eb = sum(1 for v in both if v["paren"] == "evicted" != v["field"])
    ec = sum(1 for v in both if v["field"] == "evicted" != v["paren"])
    out["eviction_paired"] = {"paren_evicted_only": eb, "field_evicted_only": ec,
                              "mcnemar_exact_p": mcnemar(eb, ec)}
    return out


def render(b):
    f, p = b["field"], b["paren"]
    ev = b["eviction_paired"]
    return (f"{b['label']:<26} {f['kept_qualified']:>3}/{f['n']:<4}{str(f['rate']):>6} "
            f"| {p['kept_qualified']:>3}/{p['n']:<4}{str(p['rate']):>6} "
            f"| {b.get('delta', 0):+.3f} | F{b['paired']['field_only']:>3} "
            f"P{b['paired']['paren_only']:<3} p={b['paired']['mcnemar_exact_p']:<9} "
            f"| evicted F{f['evicted']:>2} P{p['evicted']:<2} "
            f"p={ev['mcnemar_exact_p']}")


def main():
    raw = load()
    if not raw:
        print("no runs found")
        return 1
    rows, dropped = balance(raw)
    if dropped:
        print("incomplete replicates dropped (not silently averaged in):")
        for (run, rep), n in dropped:
            print(f"  {run} rep={rep}: {n} trials, expected {len(LEVELS) * 2 * 10}")
        print()
    models = sorted({r["model"] for r in rows})
    report = {"n_trials_collected": len(raw), "n_trials_analysed": len(rows),
              "dropped_incomplete_replicates": [
                  {"run": k[0], "rep": k[1], "trials": n} for k, n in dropped],
              "models": models,
              "runs": sorted({r["run"] for r in rows}), "blocks": {}}

    print(f"{'':<26} {'FIELD':>14} | {'PAREN':>14} | {'delta':>6} | "
          f"{'paired (McNemar)':<24} | eviction")
    print("-" * 118)
    report["blocks"]["ALL"] = block(rows, "ALL")
    print(render(report["blocks"]["ALL"]))
    print()
    for m in models:
        mr = [r for r in rows if r["model"] == m]
        key = f"model={m}"
        report["blocks"][key] = block(mr, key)
        print(render(report["blocks"][key]))
        for lv in LEVELS:
            sub = [r for r in mr if r["pressure"] == lv]
            if sub:
                k = f"{m} / {lv}"
                report["blocks"][k] = block(sub, f"  {lv}")
                print(render(report["blocks"][k]))
        print()
    for lv in LEVELS:
        sub = [r for r in rows if r["pressure"] == lv]
        if sub:
            k = f"pressure={lv}"
            report["blocks"][k] = block(sub, k)
            print(render(report["blocks"][k]))

    parse = defaultdict(int)
    for r in rows:
        parse[r.get("blind_parsed_how", "unknown")] += 1
    report["judge_parse"] = dict(parse)
    bad = sum(v for k, v in parse.items() if k in ("failed", "template_echo", "unknown"))
    print(f"\njudge parse: {dict(parse)}  "
          f"({bad}/{len(rows)} = {bad / len(rows):.1%} unusable, excluded)")

    deltas = [report["blocks"][f"pressure={lv}"]["delta"] for lv in LEVELS
              if f"pressure={lv}" in report["blocks"]]
    report["prediction_check"] = {
        "stated_before_run": "no difference at pressure=none, widening advantage as the "
                             "budget tightens",
        "deltas_by_pressure": dict(zip(LEVELS, deltas)),
        "held": bool(len(deltas) > 1 and deltas[0] < deltas[-1]
                     and deltas == sorted(deltas)),
    }
    print("\nprediction (stated before the run):",
          report["prediction_check"]["stated_before_run"])
    print("deltas by pressure:", report["prediction_check"]["deltas_by_pressure"])
    print("monotone widening held:", report["prediction_check"]["held"])

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "twocell_pooled_summary.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
