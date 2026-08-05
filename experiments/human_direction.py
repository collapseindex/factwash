"""Does the judge's disagreement with a human inflate or deflate the measured effect?

Overall agreement is not the question. A judge that errs evenly cannot manufacture a
difference between arms. A judge that errs ASYMMETRICALLY can, and this sample disagrees
on 1 of 26 field items and 6 of 24 prose items.

So recompute the headline quantity, field-minus-prose retention, twice on the same fifty
items: once with the judge's labels and once with the human's. If the human-labelled
effect is LARGER, the judge is understating and the paper's number is conservative. If it
is SMALLER, the judge is manufacturing part of the effect and the paper has a problem.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "data" / "annotation" / "human_key.json"
SHEET = ROOT / "data" / "annotation" / "human_sheet.md"
OUT = ROOT / "data" / "results" / "human_direction.json"


def main() -> int:
    key = json.loads(KEY.read_text(encoding="utf-8"))
    answers, item = {}, None
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            item = int(line[3:].strip())
        elif line.startswith("ANSWER:") and item is not None:
            v = line.split(":", 1)[1].strip().lower()
            if v:
                answers[item] = v

    rows = []
    for k in key["items"]:
        rows.append({"arm": k["arm"], "model": k["model"],
                     "judge": k["judge"], "human": answers[k["item"]]})

    def rate(rs, who):
        return sum(1 for r in rs if r[who] == "qualified") / len(rs) if rs else None

    print(f"n = {len(rows)}   the headline quantity, scored both ways\n")
    print(f"{'scored by':<12} {'field':>8} {'prose':>8} {'difference':>12}")
    print("-" * 44)
    res = {}
    for who in ("judge", "human"):
        f = [r for r in rows if r["arm"] == "field"]
        p = [r for r in rows if r["arm"] == "paren"]
        fr, pr = rate(f, who), rate(p, who)
        res[who] = {"field": round(fr, 6), "paren": round(pr, 6),
                    "delta": round(fr - pr, 6), "n_field": len(f), "n_paren": len(p)}
        print(f"{who:<12} {fr:>8.3f} {pr:>8.3f} {fr - pr:>+12.3f}")

    d_j, d_h = res["judge"]["delta"], res["human"]["delta"]
    print()
    if d_h >= d_j:
        print(f"The human-labelled effect is LARGER ({d_h:+.3f} vs {d_j:+.3f}).")
        print("The judge UNDERSTATES the difference, so the paper's number is")
        print("conservative with respect to this sample.")
        verdict = "judge understates; paper conservative"
    else:
        print(f"The human-labelled effect is SMALLER ({d_h:+.3f} vs {d_j:+.3f}).")
        print("Part of the measured effect is coming from the judge rather than from")
        print("the memories. This has to go in the paper as a threat to the result.")
        verdict = "judge overstates; threat to the result"

    print("\nwhere the disagreements are, by arm and direction")
    for arm in ("field", "paren"):
        rs = [r for r in rows if r["arm"] == arm]
        dis = [r for r in rs if r["human"] != r["judge"]]
        c = Counter(f"human {r['human']} / judge {r['judge']}" for r in dis)
        print(f"  {arm} ({len(dis)}/{len(rs)} disagree)")
        for k, v in c.most_common():
            print(f"      {v} x  {k}")

    res["verdict"] = verdict
    res["note"] = ("One rater, the paper's author, blind to condition but not to "
                   "hypothesis. Fifty items is a check on direction, not a "
                   "re-measurement of the effect.")
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
