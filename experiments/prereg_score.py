"""Score the held-out replication against the prediction registered before it ran.

Decision rule, from writeup2/PREREGISTRATION.md, committed at 1d4db35 before any call:

  sign test p >= 0.05                    -> DOES NOT REPLICATE, headline becomes NOT SHOWN
  sign test p in [0.01, 0.05)            -> qualified replication, prediction missed
  sign test p < 0.01                     -> replicates
  claim-clustered mean outside [.08,.25] -> size prediction FAILED, said so regardless

This script applies that rule mechanically and prints the verdict it produces, so the
verdict is not a judgement call made after seeing the number.
"""
import importlib.util
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, RESULTS = ROOT / "data" / "raw", ROOT / "data" / "results"

spec = importlib.util.spec_from_file_location(
    "a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

PREREG = {"commit": "1d4db35", "sign_p_replicates": 0.01, "sign_p_fails": 0.05,
          "size_lo": 0.08, "size_hi": 0.25}


def main() -> int:
    rows = []
    for p in sorted(RAW.glob("*_cv3_*_s900.jsonl")):
        rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    if not rows:
        print("no v3 rows found")
        return 1

    by = defaultdict(lambda: defaultdict(list))
    unparsed = 0
    for r in rows:
        if A.outcome(r) == "unparsed":
            unparsed += 1
            continue
        by[r["pair"]][r["arm"]].append(A.outcome(r) == "kept_qualified")

    deltas, f_all, p_all = {}, [], []
    for c, arms in by.items():
        if arms["field"] and arms["paren"]:
            deltas[c] = (sum(arms["field"]) / len(arms["field"])
                         - sum(arms["paren"]) / len(arms["paren"]))
            f_all += arms["field"]
            p_all += arms["paren"]

    pos = sum(1 for d in deltas.values() if d > 0)
    neg = sum(1 for d in deltas.values() if d < 0)
    tied = len(deltas) - pos - neg
    n = pos + neg
    sign_p = (min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1))
                  / 2 ** n) if n else 1.0)

    claims = sorted(deltas)
    rng = random.Random(4242)
    draws = sorted(sum(deltas[claims[rng.randrange(len(claims))]]
                       for _ in claims) / len(claims) for _ in range(8000))
    lo, hi = draws[200], draws[7799]
    mean = sum(deltas.values()) / len(deltas)

    replicates = sign_p < PREREG["sign_p_replicates"]
    qualified = PREREG["sign_p_replicates"] <= sign_p < PREREG["sign_p_fails"]
    size_ok = PREREG["size_lo"] <= mean <= PREREG["size_hi"]

    print("HELD-OUT REPLICATION, pre-registered at commit "
          f"{PREREG['commit']} before any API call")
    print("=" * 74)
    print(f"  claims                 {len(deltas)}")
    print(f"  field retention        {sum(f_all) / len(f_all):.3f}")
    print(f"  paren retention        {sum(p_all) / len(p_all):.3f}")
    print(f"  mean per-claim delta   {mean:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]")
    print(f"  sign test              {pos}+ / {neg}- / {tied} tied   p={sign_p:.6f}")
    print(f"  unparsable judge       {unparsed}")
    print()
    print("VERDICT BY THE REGISTERED RULE")
    if replicates:
        print("  primary: REPLICATES (sign test p < 0.01)")
    elif qualified:
        print("  primary: QUALIFIED replication (0.01 <= p < 0.05); prediction missed")
    else:
        print("  primary: DOES NOT REPLICATE (p >= 0.05). The headline claim becomes "
              "NOT SHOWN.")
    if size_ok:
        print(f"  size:    within the predicted [{PREREG['size_lo']:+.2f}, "
              f"{PREREG['size_hi']:+.2f}]")
    else:
        print(f"  size:    OUTSIDE the predicted [{PREREG['size_lo']:+.2f}, "
              f"{PREREG['size_hi']:+.2f}] -- the size prediction FAILED")

    out = {"prereg": PREREG, "claims": len(deltas), "mean_per_claim_delta": round(mean, 4),
           "ci95": [round(lo, 4), round(hi, 4)], "positive": pos, "negative": neg,
           "tied": tied, "sign_p": round(sign_p, 6), "unparsed": unparsed,
           "field_rate": round(sum(f_all) / len(f_all), 4),
           "paren_rate": round(sum(p_all) / len(p_all), 4),
           "replicates": bool(replicates), "qualified": bool(qualified),
           "size_prediction_held": bool(size_ok),
           "per_claim_deltas": {k: round(v, 3) for k, v in sorted(deltas.items())}}
    dest = RESULTS / "prereg_replication.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
