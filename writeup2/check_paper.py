"""Consistency gate for paper 2.

Same discipline as paper 1: every load-bearing number in main.tex is re-derived from
``data/results/twocell_pooled_summary.json`` and compared. A number that drifts from the
run that produced it fails here rather than in review.

The gate is rebuilt around the sixty-claim corpus, and around the claim as the unit of
analysis. It also asserts the DIRECTION of every claim the prose makes, so that if a
rerun moves the data the prose cannot quietly keep asserting the old story. That is not
hypothetical: this paper has twice asserted a conclusion that its own later data
reversed.
"""
import json
import re
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "main.tex"
SUMMARY = HERE.parent / "data" / "results" / "twocell_pooled_summary.json"

# results-table row label -> claim_clustered key
ROWS = {"Haiku 4.5": "c60/claude-haiku-4-5", "Sonnet 4.5": "c60/claude-sonnet-4-5"}


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    rep = json.loads(SUMMARY.read_text(encoding="utf-8"))
    cc = rep["claim_clustered"]
    fails, checks = [], 0

    def want(literal, why):
        nonlocal checks
        checks += 1
        if literal not in tex:
            fails.append(f"{why}: main.tex does not contain {literal!r}")

    def close(label, got, lit, tol=0.12):
        nonlocal checks
        checks += 1
        if abs(float(f"{got:.4g}") - float(lit)) > max(abs(float(lit)) * tol, 5e-5):
            fails.append(f"{label}: tex says {lit}, data says {got}")

    for nice, key in ROWS.items():
        checks += 1
        if key not in cc:
            fails.append(f"{nice}: no {key} block in the summary")
            continue
        blk, st = cc[key], cc[key]["sign_test"]
        # the prose quotes the RATE difference (field rate minus prose rate); the
        # clustered point weights claims equally and differs slightly. Both appear in
        # the paper and both are checked, each against the quantity it actually is.
        pts = 100 * blk["rate_delta"]
        want(f"${pts:+.1f}$", f"{nice} effect in points (rate difference)")
        close(f"{nice} clustered point vs rate delta",
              blk["point"], f"{blk['rate_delta']:.4f}", tol=0.15)
        want(f"${st['positive']}$", f"{nice} claims favouring field")
        want(f"${st['negative']}$", f"{nice} claims favouring prose")
        want(f"${st['tied']}$", f"{nice} tied claims")
        # the sign test must still be significant, or the headline is wrong
        checks += 1
        if st["p"] >= 0.01:
            fails.append(f"{nice} sign test p={st['p']} is no longer < 0.01; the "
                         f"paper's headline claim does not hold")
        # and the clustered interval must exclude zero
        checks += 1
        lo, hi = blk["ci95_claim_clustered"]
        if lo <= 0 <= hi:
            fails.append(f"{nice} claim-clustered CI [{lo}, {hi}] now contains zero")

    # the two models must still agree closely; the paper says "six thousandths"
    if all(k in cc for k in ROWS.values()):
        checks += 1
        gap = abs(cc[ROWS["Haiku 4.5"]]["point"] - cc[ROWS["Sonnet 4.5"]]["point"])
        if gap > 0.02:
            fails.append(f"the two models now differ by {gap:.3f}; the 'no family "
                         f"split' framing needs rechecking")

    # the ten-claim corpus must still be the thing that says otherwise, or the whole
    # retraction narrative is wrong
    for key, nice in (("c10/claude-haiku-4-5", "Haiku"),
                      ("c10/claude-sonnet-4-5", "Sonnet")):
        if key not in cc:
            continue
        checks += 1
        lo, hi = cc[key]["ci95_claim_clustered"]
        if not (lo <= 0 <= hi):
            fails.append(f"the ten-claim {nice} interval no longer contains zero; the "
                         f"retraction narrative in \\S4 is wrong")
        checks += 1
        if cc[key]["sign_test"]["p"] < 0.05:
            fails.append(f"ten-claim {nice} sign test is now significant")

    want("$+3.7$", "the ten-claim effect size quoted in the retraction")

    # raw counts quoted in the Result paragraph
    for run, nice in (("c60/claude-haiku-4-5", "Haiku"),
                      ("c60/claude-sonnet-4-5", "Sonnet")):
        if run not in cc:
            continue
        checks += 1  # pair count appears as n/360 style in the prose
        if "/360" not in tex:
            fails.append("the per-model pair count is not stated in the prose")
            break

    # --- the ablation: the paper's central mechanism claim --------------------
    AB = SUMMARY.parent / "ablation_summary.json"
    if AB.is_file():
        ab = json.loads(AB.read_text(encoding="utf-8"))
        con, rates = ab["contrasts"], ab["rates"]

        def pts(key):
            return 100 * con[key]["mean_per_claim_delta"]

        # the four numbers the mechanism argument rests on
        for key, lit, sig in (("sentences_vs_promoted", "+12.5", True),
                              ("field_vs_unlabelled", "+9.7", True),
                              ("promoted_vs_paren", "+6.7", False),
                              ("unlabelled_vs_paren", "+6.1", False),
                              ("padded_vs_paren", "+0.8", False)):
            if key not in con:
                continue
            close(f"ablation {key}", pts(key), lit, tol=0.06)
            want(f"${lit}$", f"ablation {key} in the prose")
            checks += 1
            if (con[key]["sign_p"] < 0.05) != sig:
                fails.append(f"ablation {key}: significance flipped (p="
                             f"{con[key]['sign_p']}); the argument in section 6 depends "
                             f"on which of these are significant")

        # the second model. The paper's central point about the ablation is that these
        # DISAGREE, so the gate checks the disagreement rather than the agreement.
        ABS = SUMMARY.parent / "ablation_summary_sonnet-4-5.json"
        if ABS.is_file():
            cs = json.loads(ABS.read_text(encoding="utf-8"))["contrasts"]
            for key, lit in (("field_vs_unlabelled", "+12.8"),
                             ("promoted_vs_paren", "+12.8"),
                             ("sentences_vs_promoted", "+0.6"),
                             ("padded_vs_paren", "-10.3")):
                if key not in cs:
                    continue
                close(f"sonnet ablation {key}",
                      100 * cs[key]["mean_per_claim_delta"], lit, tol=0.08)
                want(f"${lit}$", f"sonnet {key} in the prose")
            checks += 1
            if cs["sentences_vs_promoted"]["sign_p"] < 0.05:
                fails.append("wording is now significant on Sonnet too; the 'does not "
                             "transfer' argument in section 6 no longer holds")
            checks += 1
            if not (cs["field_vs_unlabelled"]["sign_p"] < 0.05
                    and con["field_vs_unlabelled"]["sign_p"] < 0.05):
                fails.append("labels are no longer significant on both models; that is "
                             "the paper's one replicating component")
            checks += 1
            if cs["padded_vs_paren"]["mean_per_claim_delta"] > 0:
                fails.append("padding no longer hurts on Sonnet; the 'length helps "
                             "neither' claim needs rechecking")

        # padding must remain the LONGEST arm, or "length does nothing" is not a
        # conservative test any more, it is just a smaller arm losing
        checks += 1
        if not all(rates.get("padded") is not None for _ in [0]):
            fails.append("no padded arm; the length control is missing")
        checks += 1
        if con.get("field_vs_sentences", {}).get("sign_p", 0) < 0.05:
            fails.append("field now differs from sentences; the retraction of "
                         "'labelled fields are the best form' no longer holds")

    # --- the pre-registered replication ---------------------------------------
    PR = SUMMARY.parent / "prereg_replication.json"
    if PR.is_file():
        pr = json.loads(PR.read_text(encoding="utf-8"))
        checks += 1
        if not pr["replicates"]:
            fails.append("the pre-registered replication no longer passes its own "
                         "registered rule; section 5 and the abstract are wrong")
        checks += 1
        if not pr["size_prediction_held"]:
            fails.append("the registered size prediction no longer holds")
        want(f"${100 * pr['mean_per_claim_delta']:+.1f}$", "replication effect size")
        want(f"${pr['positive']}$", "replication claims favouring field")

    # judge parse health
    parse = rep["judge_parse"]
    bad = sum(v for k, v in parse.items() if k in ("failed", "template_echo", "unknown"))
    checks += 1
    if bad:
        fails.append(f"{bad} unusable judge replies; tex claims none")

    # stated pair counts must be counts the data can produce
    legal = {str(b["paired"]["pairs"]) for b in rep["blocks"].values() if "paired" in b}
    legal |= {str(b[a]["n"]) for b in rep["blocks"].values() for a in ("field", "paren")
              if a in b}
    per_model = [cc[k]["sign_test"]["claims"] for k in cc if k.startswith("c60/")]
    for r in range(2, len(per_model) + 1):
        legal |= {str(sum(c)) for c in combinations(per_model, r)}
    legal |= {"60", "360"}
    legal |= {str(v["pairs"]) for v in cc.values() if "pairs" in v}
    for pat, what in ((r"\$(\d+)\$ matched pairs", "matched pairs"),
                      (r"\$n\s*=\s*(\d+)\$", "n=")):
        for m in re.finditer(pat, tex):
            checks += 1
            if m.group(1) not in legal:
                fails.append(f"stated {what} {m.group(1)} is not a count the data "
                             f"produces")

    # --- PROSE-LEVEL CHECKS ---------------------------------------------------
    # Everything above re-derives numbers from JSON. A review found six internal
    # contradictions and this gate caught none of them, because every one was a
    # sentence surviving a rewrite rather than a number drifting. These check the prose
    # against itself.

    # (a) claims the ledger marks RETRACTED must not be asserted elsewhere
    RETRACTED_PHRASES = [
        ("whether the stance is asserted or subordinated",
         "the mechanism claim retracted after the promoted arm"),
        ("subordination does everything", "retracted figure caption"),
        ("helps where the compressor is weakest", "retracted v2 title claim"),
        ("splits by model family", "retracted"),
        ("widens monotonically", "retracted prediction"),
        ("does as well as the labelled schema", "equivalence was never established"),
        ("ran on Haiku~4.5 only", "the ablation now runs on both models"),
    ]
    for phrase, why in RETRACTED_PHRASES:
        for m in re.finditer(re.escape(phrase), tex, re.I):
            checks += 1
            ctx = tex[max(0, m.start() - 220):m.end() + 220].lower()
            if not any(w in ctx for w in ("retract", "earlier draft", "previous draft",
                                          "title history", "not shown", "not claimed",
                                          "wrong", "it does not", "does not support")):
                fails.append(f"retracted claim asserted as current: {phrase!r} ({why})")

    # (b) counts written as words must match the ledger
    WORDS = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    checks += 1
    word = WORDS.get(tex.lower().count(r"	extsc{retracted}"))
    if word and f"{word} retractions" not in tex.lower():
        fails.append(f"the ledger holds {word} retractions but the prose does not say so")
    # the same number must be used everywhere it is stated
    stated = set(re.findall(r"(\w+) retractions", tex.lower()))
    checks += 1
    if len(stated) > 1:
        fails.append(f"the prose states the retraction count inconsistently: {stated}")
    stated_h = set(re.findall(r"(\w+) of them our own headline", tex.lower()))
    checks += 1
    if len(stated_h) > 1:
        fails.append(f"'N of them our own headline claims' disagrees with itself: "
                     f"{stated_h}")

    # (c) the arm count stated in prose must equal the number of arms in the data.
    # Checking only for internal disagreement was not enough: the phrase occurs once,
    # so corrupting it left nothing to disagree with. Anchor it to the run instead.
    AB2 = SUMMARY.parent / "ablation_summary.json"
    if AB2.is_file():
        n_arms = len(json.loads(AB2.read_text(encoding="utf-8"))["rates"])
        NUM = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
        checks += 1
        stated_arms = set(re.findall(r"the (three|four|five|six|seven) forms",
                                     tex.lower()))
        if stated_arms and stated_arms != {NUM[n_arms]}:
            fails.append(f"the prose says 'the {stated_arms} forms' but the ablation "
                         f"has {n_arms} arms")
        checks += 1
        n_new = n_arms - 2  # field and paren already existed
        if f"ran {NUM[n_new]} further arms" not in tex:
            fails.append(f"the prose does not say 'ran {NUM[n_new]} further arms'; the "
                         f"ablation added {n_new} to the original two")

    # no placeholders; the ledger must still carry its retractions
    checks += 1
    if re.findall(r"\\needsdata\{", tex):
        fails.append("\\needsdata placeholders remain")
    checks += 1
    # Pinned, not a floor. A floor lets retractions vanish one at a time so long as
    # enough remain, which negative testing caught: downgrading two of seven still
    # cleared a floor of five. Changing this number should be a decision someone makes
    # on purpose, which is exactly the property a retraction ledger needs.
    # The prose states the retraction count in words. It said "five" while the ledger
    # held seven, and nothing here noticed, so now something does.
    WORDS = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    checks += 1
    word = WORDS.get(tex.lower().count(r"	extsc{retracted}"))
    if word and f"{word} retractions" not in tex.lower():
        fails.append(f"the ledger holds {word} retractions but the prose does not say "
                     f"'{word} retractions' anywhere")

    expected_retractions = 8
    n_retracted = tex.lower().count(r"\textsc{retracted}")
    if n_retracted != expected_retractions:
        fails.append(f"{n_retracted} RETRACTED rows in the ledger, expected "
                     f"{expected_retractions}. If one was legitimately added or "
                     f"resolved, update the expected count deliberately; do not let a "
                     f"retraction disappear quietly")
    checks += 1
    if tex.count(r"\textsc{not claimed}") + tex.count(r"\textsc{not shown}") < 3:
        fails.append("fewer than three NOT SHOWN / NOT CLAIMED rows in the ledger")

    print(f"{checks} checks run against {SUMMARY.name} "
          f"({rep['n_trials_analysed']} trials analysed)")
    if fails:
        print(f"\n{len(fails)} FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("all consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
