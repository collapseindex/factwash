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
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"
LEVELS = ("none", "low", "high", "extreme", "brutal", "severe")


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


def cluster_bootstrap(rows, n_boot=4000, seed=12345):
    """Claim-clustered CI on the field-minus-prose difference.

    The exact McNemar above treats every matched pair as an independent unit. They are
    not: 950 pairs are ten claims resampled across pressure levels and replicates, so
    the same wording recurs dozens of times and its idiosyncrasies are counted dozens of
    times. The unit that generalises is the CLAIM, and there are ten of them.

    This resamples claims with replacement and recomputes the paired difference, which
    is the honest interval to quote for "would this hold on a new claim". It will be
    much wider than the pair-level p-value, and that is the point.
    """
    by_claim = defaultdict(list)
    for r in rows:
        if outcome(r) != "unparsed":
            by_claim[r["pair"]].append(r)
    claims = sorted(by_claim)
    if len(claims) < 3:
        return None

    def diff(sample):
        f = [r for c in sample for r in by_claim[c] if r["arm"] == "field"]
        p = [r for c in sample for r in by_claim[c] if r["arm"] == "paren"]
        if not f or not p:
            return None
        fr = sum(outcome(r) == "kept_qualified" for r in f) / len(f)
        pr = sum(outcome(r) == "kept_qualified" for r in p) / len(p)
        return fr - pr

    point = diff(claims)
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        d = diff([claims[rng.randrange(len(claims))] for _ in claims])
        if d is not None:
            draws.append(d)
    draws.sort()
    lo = draws[int(0.025 * len(draws))]
    hi = draws[int(0.975 * len(draws)) - 1]
    # share of resamples where the sign flips: a crude two-sided cluster p-value
    p = 2 * min(sum(d <= 0 for d in draws), sum(d >= 0 for d in draws)) / len(draws)
    return {"n_claims": len(claims), "point": round(point, 4),
            "ci95_claim_clustered": [round(lo, 4), round(hi, 4)],
            "p_cluster_bootstrap": round(min(1.0, p), 4)}


def sign_test_by_claim(rows):
    """Per-claim field-minus-prose deltas, then an exact sign test across claims.

    This is the diagnostic that matters most. If the effect is real it should point the
    same way on most claims. If it is carried by two or three wordings, the pooled
    number is describing those wordings and not the mechanism.
    """
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if outcome(r) != "unparsed":
            by[r["pair"]][r["arm"]].append(outcome(r) == "kept_qualified")
    deltas = {}
    for claim, arms in by.items():
        if arms["field"] and arms["paren"]:
            deltas[claim] = (sum(arms["field"]) / len(arms["field"])
                             - sum(arms["paren"]) / len(arms["paren"]))
    if len(deltas) < 3:
        return None
    pos = sum(1 for v in deltas.values() if v > 0)
    neg = sum(1 for v in deltas.values() if v < 0)
    n = pos + neg
    p = (min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) / 2 ** n)
         if n else 1.0)
    return {"claims": len(deltas), "positive": pos, "negative": neg,
            "tied": len(deltas) - n, "p": round(p, 4),
            "deltas": {k: round(v, 3) for k, v in sorted(deltas.items())}}


def load():
    rows = []
    for p in sorted(RAW.glob("*twocellpress_claude-*.jsonl")):
        model = p.stem.split("_twocellpress_")[1].rsplit("_n", 1)[0]
        # runs carry a corpus tag in the filename; it belongs to the run, not the model
        for tag in ("_call", "_cv1", "_cv2", "_cv3", "_call_"):
            if model.endswith(tag):
                model = model[: -len(tag)]
        run = p.stem
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["model"], r["run"] = model, run
                # Corpus is part of a run's identity, not a detail. Merging the ten-
                # claim and sixty-claim runs under one model key is exactly the mistake
                # this project already made once: it pools two different populations of
                # stimuli and reports the average as if it described either.
                # v3 is sixty claims too, but a DIFFERENT sixty. Merging it into c60 would
                # pool the main experiment with its own held-out replication.
                r["corpus"] = ("v3" if "_cv3_" in run
                               else "c60" if "_call_" in run else "c10")
                rows.append(r)
    return rows


def balance(rows):
    """Keep only (run, replicate, pressure) cells that ran to completion.

    The opus run stopped mid-way when the API credit ran out, leaving a cell with one
    arm populated and the other not. Averaging that in would silently weight a model
    toward whichever arm got further. Dropped cells are returned so the count is printed
    rather than hidden.

    Balancing is per PAIR, which is what a paired test actually requires: a claim at a
    given (run, replicate, pressure) counts only if BOTH arms are present. An earlier
    version balanced whole cells against a hardcoded ten claims per cell, which would
    have silently discarded every run of the sixty-claim corpus.
    """
    per = defaultdict(dict)
    for r in rows:
        per[(r["run"], r["rep"], r["pressure"], r["pair"])][r["arm"]] = r
    kept, dropped = [], []
    for key, arms in sorted(per.items()):
        (kept if len(arms) == 2 else dropped).append((key, arms))
    return ([r for _, arms in kept for r in arms.values()],
            [(k, len(a)) for k, a in dropped])


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
        # from the UNROUNDED rates. Subtracting two rounded rates gave +15.9 where the
        # true difference is 57/360 = 15.83, which a review caught: a difference of
        # rounded numbers is not a rounded difference.
        fk, fn = out["field"]["kept_qualified"], out["field"]["n"] - out["field"]["unparsed"]
        pk, pn = out["paren"]["kept_qualified"], out["paren"]["n"] - out["paren"]["unparsed"]
        out["delta"] = round(fk / fn - pk / pn, 4) if fn and pn else None

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
        print("incomplete pairs dropped (one arm missing; not silently averaged in):")
        for (run, rep, level, claim), n in dropped:
            print(f"  {run[:44]} rep={rep} {level} {claim}: {n} arm, expected 2")
        print()
    models = sorted({r["model"] for r in rows})
    report = {"n_trials_collected": len(raw), "n_trials_analysed": len(rows),
              "dropped_unpaired": [
                  {"run": k[0], "rep": k[1], "pressure": k[2], "claim": k[3],
                   "arms_present": n} for k, n in dropped],
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

    # --- the unit-of-analysis correction ------------------------------------
    # Everything above treats a matched pair as independent. It is not: the pairs are
    # ten claims resampled, so a claim's idiosyncrasies are counted dozens of times.
    # Cluster on the claim and report the sign test across claims, which is the
    # question "does this hold for a NEW claim" rather than "for another replicate of
    # these ten".
    print("\nclaim-clustered (the unit that generalises; n=10 claims, not 950 pairs)")
    print(f"{'':<22} {'point':>7}  {'95% CI (cluster boot)':<24} {'boot p':>7} "
          f"{'sign test across claims':>26}")
    report["claim_clustered"] = {}
    hard = ("brutal", "severe")
    combos = [(f"{c}/{m}", (lambda cc, mm: lambda r: r["corpus"] == cc
                            and r["model"] == mm and r["pressure"] in hard)(c, m))
              for c in ("c60", "c10") for m in models]
    for label, sel in (("ALL", lambda r: True), *combos):
        sub = [r for r in rows if sel(r)]
        cb = cluster_bootstrap(sub)
        st = sign_test_by_claim(sub)
        if not cb or not st:
            continue
        # pair count belongs with the clustered stats: the paper quotes historical
        # pair counts when describing what the small corpus said, and the gate has to
        # be able to check them
        blk = block(sub, label)
        report["claim_clustered"][label] = {
            **cb, "sign_test": st, "pairs": blk["paired"]["pairs"],
            "rate_delta": blk["delta"],
            "field_rate": blk["field"]["rate"], "paren_rate": blk["paren"]["rate"]}
        print(f"{label:<22} {cb['point']:+7.3f}  "
              f"[{cb['ci95_claim_clustered'][0]:+.3f}, {cb['ci95_claim_clustered'][1]:+.3f}]"
              f"{'':<7} {cb['p_cluster_bootstrap']:>7.3f} "
              f"{st['positive']:>10}+/{st['negative']}- p={st['p']:.3f}")

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
