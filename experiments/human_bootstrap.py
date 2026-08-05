"""Bootstrap the human-versus-judge comparison, on the quantity that matters.

Three questions, only one of which the fifty items can actually answer well.

1. What is the human-labelled effect? Poorly determined. Twenty-six field items and
   twenty-four prose items give a very wide interval, and this sample was never meant to
   re-measure the effect.

2. Does scoring by human rather than judge SHIFT the effect? Well determined, because it
   is paired: the same fifty items are scored twice, so the two deltas move together
   under resampling and their difference is far better behaved than either alone. This is
   the question the annotation exists to answer.

3. Is the disagreement asymmetry between arms real? One of twenty-six field items and six
   of twenty-four prose items disagree. A judge that errs evenly cannot manufacture a
   difference between arms; a judge that errs asymmetrically can, so the asymmetry gets
   its own exact test regardless of which way it points.

Resampling is clustered on the CLAIM, matching the rest of the paper, since forty claims
supply the fifty items and six claims contribute more than one.
"""
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "data" / "annotation" / "human_key.json"
SHEET = ROOT / "data" / "annotation" / "human_sheet.md"
OUT = ROOT / "data" / "results" / "human_bootstrap.json"
N_BOOT = 10000
SEED = 20260805


def load():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    answers, item = {}, None
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            item = int(line[3:].strip())
        elif line.startswith("ANSWER:") and item is not None:
            v = line.split(":", 1)[1].strip().lower()
            if v:
                answers[item] = v
    rows = [{"claim": k["pair"], "arm": k["arm"],
             "judge": k["judge"], "human": answers[k["item"]]}
            for k in key["items"]]
    return rows


def delta(rows, who):
    f = [r for r in rows if r["arm"] == "field"]
    p = [r for r in rows if r["arm"] == "paren"]
    if not f or not p:
        return None
    return (sum(r[who] == "qualified" for r in f) / len(f)
            - sum(r[who] == "qualified" for r in p) / len(p))


def ci(draws, lo=0.025, hi=0.975):
    d = sorted(draws)
    return round(d[int(lo * len(d))], 4), round(d[int(hi * len(d)) - 1], 4)


def fisher_two_tailed(a, b, c, d):
    """Exact test on the 2x2 [[a,b],[c,d]]; sums tables no likelier than observed."""
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def p_of(x):
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)

    obs = p_of(a)
    lo = max(0, c1 - r2)
    return min(1.0, sum(p_of(x) for x in range(lo, min(r1, c1) + 1)
                        if p_of(x) <= obs * (1 + 1e-9)))


def main() -> int:
    rows = load()
    by_claim = defaultdict(list)
    for r in rows:
        by_claim[r["claim"]].append(r)
    claims = sorted(by_claim)

    d_j, d_h = delta(rows, "judge"), delta(rows, "human")
    rng = random.Random(SEED)
    hb, shift = [], []
    for _ in range(N_BOOT):
        samp = [r for c in (claims[rng.randrange(len(claims))] for _ in claims)
                for r in by_claim[c]]
        dj, dh = delta(samp, "judge"), delta(samp, "human")
        if dj is None or dh is None:
            continue
        hb.append(dh)
        shift.append(dh - dj)

    h_lo, h_hi = ci(hb)
    s_lo, s_hi = ci(shift)
    crosses = s_lo <= 0 <= s_hi

    print(f"n = {len(rows)} items from {len(claims)} claims, "
          f"{N_BOOT} claim-clustered resamples\n")
    print(f"  judge-scored effect            {d_j:+.3f}")
    print(f"  human-scored effect            {d_h:+.3f}   95% CI [{h_lo:+.3f}, {h_hi:+.3f}]")
    print(f"  shift from scoring by human    {d_h - d_j:+.3f}   95% CI [{s_lo:+.3f}, {s_hi:+.3f}]")
    print()
    if crosses:
        widest = max(abs(s_lo), abs(s_hi))
        print("  The shift interval contains zero, so no shift was detected. But state")
        print("  the width too: it does not EXCLUDE a shift of "
              f"{widest:.2f}, which is about")
        print("  the size of the whole effect. Fifty items can show the direction of")
        print("  scorer disagreement; they cannot bound its magnitude below the thing")
        print("  being measured. Absence of a detected shift is not absence of a shift.")
    else:
        print("  The shift interval EXCLUDES zero: the choice of scorer moves the effect,")
        print("  and the paper must report the human-scored number, not the judge's.")
    print(f"\n  The human-scored effect's own interval is wide ({h_hi - h_lo:.2f} across),")
    print("  which is expected and is why this is a direction check rather than a")
    print("  re-measurement.")

    fd = sum(1 for r in rows if r["arm"] == "field" and r["human"] != r["judge"])
    fn = sum(1 for r in rows if r["arm"] == "field")
    pd_ = sum(1 for r in rows if r["arm"] == "paren" and r["human"] != r["judge"])
    pn = sum(1 for r in rows if r["arm"] == "paren")
    p_fisher = fisher_two_tailed(fd, fn - fd, pd_, pn - pd_)
    print(f"\n  disagreement asymmetry  field {fd}/{fn}, prose {pd_}/{pn}, "
          f"Fisher exact p = {p_fisher:.4f}")
    if p_fisher < 0.05:
        print("  Real asymmetry. It is benign only because of its DIRECTION: the judge")
        print("  over-detects claim presence on prose, and most of that lands on")
        print("  established_fact, which does not count as retained.")
    else:
        print("  Not distinguishable from even error at this n.")

    out = {"n_items": len(rows), "n_claims": len(claims), "n_boot": N_BOOT, "seed": SEED,
           "judge_delta": round(d_j, 4), "human_delta": round(d_h, 4),
           "human_delta_ci95": [h_lo, h_hi],
           "shift_human_minus_judge": round(d_h - d_j, 4),
           "shift_ci95": [s_lo, s_hi], "shift_ci_contains_zero": bool(crosses),
           "disagree_field": [fd, fn], "disagree_prose": [pd_, pn],
           "asymmetry_fisher_p": round(p_fisher, 4),
           "note": "One rater, the paper's author, blind to condition but not to "
                   "hypothesis. Fifty items check the DIRECTION of scorer disagreement; "
                   "they do not re-measure the effect."}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
