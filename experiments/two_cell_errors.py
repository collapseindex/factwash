"""Error analysis and robustness checks on the sixty-claim runs. No API calls.

Five questions the headline number does not answer:

1. Does the effect hold across REGISTERS, or is it carried by one or two of the seven?
   The corpus was widened precisely because ten claims of one register lied to us; it
   would be careless not to check whether sixty claims of seven registers are doing a
   smaller version of the same thing.

2. WHERE DOES IT FAIL? Ten claims across the two models go the other way. If those have
   something in common, that is a finding about when a write schema is the wrong tool,
   and it is more useful to a practitioner than another decimal place on the mean.

3. What are the TIES? A third of claims tie. If ties are concentrated at the tightest
   budget where everything is evicted, then the effect is really a fact about the
   survivable middle, and the sign test is being diluted by cells that could not have
   shown anything.

4. Does a PERMUTATION test agree? The sign test throws away effect size and the cluster
   bootstrap assumes the resampling distribution is well behaved with sixty clusters.
   Shuffling the arm label within each claim makes no distributional assumption at all,
   and it is the cleanest null available for a paired design.

5. Is it LENGTH? The field form is three lines where the parenthetical is one. If the
   advantage were really "longer notes survive", the per-claim effect should grow with
   how much longer the field form is. That is a confound we can measure without
   spending anything, and it is the first thing a reviewer will ask.
"""
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

from claims_corpus import V1, V2  # noqa: E402

ALL_CLAIMS = {c[0]: c for c in V1 + V2}
REGISTER = {}
for cid, *_ in V1:
    REGISTER[cid] = "project"
for cid, *_ in V2:
    REGISTER[cid] = cid.split("_")[0] if "_" in cid else "project"
RENAME = {"med": "medicine", "proj": "project", "news": "news", "pers": "personal",
          "sched": "scheduling", "est": "estimate", "conf": "conflict"}
REGISTER = {k: RENAME.get(v, v) for k, v in REGISTER.items()}


def kept(r):
    return A.outcome(r) == "kept_qualified"


def per_claim(rows):
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if A.outcome(r) != "unparsed":
            by[r["pair"]][r["arm"]].append(kept(r))
    out = {}
    for c, arms in by.items():
        if arms["field"] and arms["paren"]:
            out[c] = (sum(arms["field"]) / len(arms["field"])
                      - sum(arms["paren"]) / len(arms["paren"]))
    return out


def sign_p(pos, neg):
    n = pos + neg
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) / 2 ** n)


def permutation_test(rows, n_perm=20000, seed=7):
    """Shuffle the arm label WITHIN each claim, recompute the mean per-claim delta.

    Makes no distributional assumption. The null is "the label carries no information",
    which is exactly the hypothesis the experiment was built to test.
    """
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if A.outcome(r) != "unparsed":
            by[r["pair"]][r["arm"]].append(kept(r))
    claims = [c for c, a in by.items() if a["field"] and a["paren"]]
    if len(claims) < 3:
        return None

    def mean_delta(flip):
        tot = 0.0
        for i, c in enumerate(claims):
            f, p = by[c]["field"], by[c]["paren"]
            if flip[i]:
                f, p = p, f
            tot += sum(f) / len(f) - sum(p) / len(p)
        return tot / len(claims)

    obs = mean_delta([0] * len(claims))
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        if abs(mean_delta([rng.getrandbits(1) for _ in claims])) >= abs(obs):
            hits += 1
    return {"observed_mean_delta": round(obs, 4), "n_claims": len(claims),
            "p_permutation": round((hits + 1) / (n_perm + 1), 5), "n_perm": n_perm}


def main() -> int:
    rows, _ = A.balance(A.load())
    runs = {"Haiku 4.5": [r for r in rows if "haiku-4-5_call" in r["run"]],
            "Sonnet 4.5": [r for r in rows if "sonnet-4-5_call" in r["run"]]}
    report = {}

    # --- 1. by register ------------------------------------------------------
    print("=" * 78)
    print("1. BY REGISTER  (is the effect carried by one or two of the seven?)")
    print("=" * 78)
    print(f"{'register':<12} {'n':>3}  " + "  ".join(f"{m:>22}" for m in runs))
    reg_rows = defaultdict(dict)
    for model, sub in runs.items():
        deltas = per_claim(sub)
        by_reg = defaultdict(list)
        for c, d in deltas.items():
            by_reg[REGISTER.get(c, "?")].append(d)
        for reg, ds in by_reg.items():
            pos = sum(1 for d in ds if d > 0)
            neg = sum(1 for d in ds if d < 0)
            reg_rows[reg][model] = (sum(ds) / len(ds), pos, neg, len(ds))
    for reg in sorted(reg_rows, key=lambda r: -len(reg_rows[r])):
        cells = []
        n = 0
        for model in runs:
            if model in reg_rows[reg]:
                mean, pos, neg, n = reg_rows[reg][model]
                cells.append(f"{mean:+.3f} ({pos}+/{neg}-)".rjust(22))
            else:
                cells.append(" " * 22)
        print(f"{reg:<12} {n:>3}  " + "  ".join(cells))
    report["by_register"] = {r: {m: v[0] for m, v in d.items()}
                             for r, d in reg_rows.items()}

    # --- 2. where it fails ---------------------------------------------------
    print()
    print("=" * 78)
    print("2. WHERE IT FAILS  (claims where the parenthetical won)")
    print("=" * 78)
    losers = {}
    for model, sub in runs.items():
        for c, d in per_claim(sub).items():
            if d < 0:
                losers.setdefault(c, {})[model] = d
    for c, per in sorted(losers.items(), key=lambda kv: min(kv[1].values())):
        claim = ALL_CLAIMS.get(c)
        where = ", ".join(f"{m} {v:+.2f}" for m, v in per.items())
        print(f"  {c:<14} [{REGISTER.get(c, '?'):<10}] {where}")
        if claim:
            print(f"      claim: {claim[1][:66]}")
            print(f"      source/certainty: {claim[2][:32]} / {claim[3][:34]}")
    report["failing_claims"] = {c: v for c, v in losers.items()}

    # --- 3. ties -------------------------------------------------------------
    print()
    print("=" * 78)
    print("3. TIES  (are they concentrated where nothing survives?)")
    print("=" * 78)
    for model, sub in runs.items():
        d_all = per_claim(sub)
        tied = {c for c, d in d_all.items() if d == 0}
        both_zero = 0
        for c in tied:
            cr = [r for r in sub if r["pair"] == c]
            if not any(kept(r) for r in cr):
                both_zero += 1
        print(f"  {model:<12} {len(tied)} tied, of which {both_zero} are ties at ZERO "
              f"(neither arm retained standing on any replicate)")
        for lv in ("brutal", "severe"):
            lv_rows = [r for r in sub if r["pressure"] == lv]
            dl = per_claim(lv_rows)
            pos = sum(1 for d in dl.values() if d > 0)
            neg = sum(1 for d in dl.values() if d < 0)
            tie = sum(1 for d in dl.values() if d == 0)
            print(f"      {lv:<8} {pos}+/{neg}-/{tie} tied   mean "
                  f"{sum(dl.values()) / len(dl):+.3f}   sign p={sign_p(pos, neg):.4f}")

    # --- 4. permutation ------------------------------------------------------
    print()
    print("=" * 78)
    print("4. PERMUTATION TEST  (shuffle the arm label within each claim)")
    print("=" * 78)
    report["permutation"] = {}
    for model, sub in runs.items():
        pt = permutation_test(sub)
        report["permutation"][model] = pt
        print(f"  {model:<12} observed {pt['observed_mean_delta']:+.4f}  "
              f"p={pt['p_permutation']:.5f}  ({pt['n_perm']} permutations, "
              f"{pt['n_claims']} claims)")

    # --- 5. length confound --------------------------------------------------
    print()
    print("=" * 78)
    print("5. LENGTH CONFOUND  (does the advantage grow with how much longer the")
    print("   field form is? if so, 'labelled' may be doing less work than 'longer')")
    print("=" * 78)
    report["length"] = {}
    for model, sub in runs.items():
        deltas = per_claim(sub)
        xs, ys = [], []
        for c, d in deltas.items():
            cl = ALL_CLAIMS.get(c)
            if not cl:
                continue
            _, claim, source, certainty = cl
            field_len = len(f"{claim}\nSOURCE: {source}\nCERTAINTY: {certainty}")
            paren_len = len(f"{claim} (per {source}; {certainty})")
            xs.append(field_len - paren_len)
            ys.append(d)
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx == 0:
            # This test cannot work, and saying so is the whole point of running it.
            # Both templates wrap the same claim, source and certainty strings, so the
            # length difference is a CONSTANT: "\nSOURCE: " + "\nCERTAINTY: " minus
            # " (per " + "; " + ")" is the same 12 characters for every claim. With no
            # variance in the predictor there is nothing to correlate, and a reported
            # r of zero would look like evidence of no confound when it is evidence of
            # no experiment. Ruling length out needs a token-matched prose arm.
            report["length"][model] = {
                "pearson_r": None, "n": n, "extra_chars": round(mx, 1),
                "verdict": "UNINFORMATIVE: the length difference is constant by "
                           "construction, so this correlation has no variance to work "
                           "with. Needs a token-matched arm, not a re-analysis."}
            print(f"  {model:<12} UNINFORMATIVE. The field form is exactly "
                  f"{mx:+.0f} characters longer for EVERY claim,")
            print(f"               so there is no variance to correlate against. "
                  f"A length confound cannot be")
            print(f"               ruled out from this data; it needs a "
                  f"token-matched prose arm.")
            continue
        syy = sum((y - my) ** 2 for y in ys)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        r = sxy / math.sqrt(sxx * syy) if syy else 0.0
        report["length"][model] = {"pearson_r": round(r, 4), "n": n,
                                   "mean_extra_chars": round(mx, 1)}
        print(f"  {model:<12} r = {r:+.3f} between (field chars - prose chars) and the "
              f"per-claim effect")
        print(f"               field form averages {mx:+.1f} characters longer")

    out = ROOT / "data" / "results" / "twocell_error_analysis.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
