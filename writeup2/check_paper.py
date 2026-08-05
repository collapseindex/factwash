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
        ("asserted prose", "collides with CERTAINTY: asserted, which means the "
                           "opposite; the sentences arm is EXPLICIT prose"),
        ("about as well as the schema", "an equivalence claim the TOST does not support"),
    ]
    # comments are not the paper; the title-history block names every withdrawn
    # claim on purpose
    prose = re.sub(r"(?m)^\s*%.*$", "", tex)
    for phrase, why in RETRACTED_PHRASES:
        for m in re.finditer(re.escape(phrase), prose, re.I):
            checks += 1
            # a phrase named as a TERM, in LaTeX quotes, is being discussed rather
            # than asserted. "rather than" was tried as a context keyword and is far
            # too common: it exempted a mutation that reasserted a retracted claim.
            quoted = (prose[max(0, m.start() - 2):m.start()] == "``"
                      and prose[m.end():m.end() + 2] == "''")
            if quoted:
                continue
            ctx = prose[max(0, m.start() - 220):m.end() + 220].lower()
            if not any(w in ctx for w in ("retract", "earlier draft", "previous draft",
                                          "title history", "not shown", "not claimed",
                                          "wrong", "it does not",
                                          "does not support")):
                fails.append(f"retracted claim asserted as current: {phrase!r} ({why})")

    # (a2) EVERY point-value in the prose must be a number the run data produces.
    # A stale "+5.5 headline" survived a rewrite and no check saw it, because a number
    # that no longer exists anywhere cannot fail a comparison against the summary. So
    # instead of checking that the right numbers are present, enumerate every "+N.N"
    # the prose asserts and require each to be a real quantity.
    legal_pts = set()
    for blk in list(cc.values()):
        for key in ("point", "rate_delta"):
            if isinstance(blk.get(key), (int, float)):
                legal_pts.add(round(100 * blk[key], 1))
        for b in blk.get("ci95_claim_clustered", []) or []:
            legal_pts.add(round(100 * b, 1))
    for src in (SUMMARY.parent / "ablation_summary.json",
                SUMMARY.parent / "ablation_summary_sonnet-4-5.json",
                SUMMARY.parent / "ablation_intervals.json",
                SUMMARY.parent / "ablation_intervals_sonnet-4-5.json",
                SUMMARY.parent / "prereg_replication.json"):
        if not src.is_file():
            continue
        d = json.loads(src.read_text(encoding="utf-8"))
        for c2 in (d.get("contrasts") or {}).values():
            for key in ("mean_per_claim_delta", "point"):
                if isinstance(c2.get(key), (int, float)):
                    legal_pts.add(round(100 * c2[key], 1))
            for b in (c2.get("ci95") or []) + (c2.get("ci90") or []):
                legal_pts.add(round(100 * b, 1))
        for key in ("mean_per_claim_delta",):
            if isinstance(d.get(key), (int, float)):
                legal_pts.add(round(100 * d[key], 1))
        for b in (d.get("ci95") or []):
            legal_pts.add(round(100 * b, 1))
    # the human-annotation figures come from a different measurement, so they are sourced
    # from their own result files rather than exempted. An exemption would wave through
    # any typo in that paragraph; this way a mistyped one still fails.
    for src in (SUMMARY.parent / "human_direction.json",
                SUMMARY.parent / "human_bootstrap.json"):
        if not src.is_file():
            continue
        d = json.loads(src.read_text(encoding="utf-8"))
        for who in ("judge", "human"):
            if isinstance(d.get(who), dict):
                for key in ("delta", "field", "paren"):
                    if isinstance(d[who].get(key), (int, float)):
                        legal_pts.add(round(100 * d[who][key], 1))
        for key in ("judge_delta", "human_delta", "shift_human_minus_judge"):
            if isinstance(d.get(key), (int, float)):
                legal_pts.add(round(100 * d[key], 1))
        for key in ("human_delta_ci95", "shift_ci95"):
            for b in d.get(key) or []:
                legal_pts.add(round(100 * b, 1))
    # historical figures the paper quotes on purpose when describing what it withdrew
    legal_pts |= {4.0, 9.3, 3.7, 0.4, 18.3, 15.9}
    for m in re.finditer(r"\$([+-]\d+\.\d)\$", tex):
        checks += 1
        v = float(m.group(1))
        if round(v, 1) not in legal_pts and round(-v, 1) not in legal_pts:
            ctx = re.sub(r"\s+", " ", tex[max(0, m.start() - 60):m.end() + 60])
            fails.append(f"stated effect {m.group(1)} is not a value the run data "
                         f"produces: ...{ctx}...")

    # (b) counts written as words must match the ledger
    WORDS = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    checks += 1
    word = WORDS.get(tex.lower().count(r"	extsc{retracted}"))
    if word and f"{word} withdrawn claims" not in tex.lower():
        fails.append(f"the ledger holds {word} RETRACTED rows but the prose does "
                     f"not say '{word} withdrawn claims'")
    # the same number must be used everywhere it is stated
    stated = set(re.findall(r"(\w+) withdrawn claims", tex.lower()))
    checks += 1
    if len(stated) > 1:
        fails.append(f"the prose states the withdrawn-claim count inconsistently: "
                     f"{stated}")
    stated_h = set(re.findall(r"(\w+) of them former title claims", tex.lower()))
    checks += 1
    if len(stated_h) > 1:
        fails.append(f"'N of them our own headline claims' disagrees with itself: "
                     f"{stated_h}")

    checks += 1
    n_tagged = tex.count("\\textsc{(headline)}") - 1  # one mention is the legend
    if stated_h and n_tagged != {"two": 2, "three": 3, "four": 4}.get(
            next(iter(stated_h)), -1):
        fails.append(f"the prose says {stated_h} former title claims but {n_tagged} "
                     f"ledger rows carry the (headline) tag")

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
    if word and f"{word} withdrawn claims" not in tex.lower():
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

    # (d) the human annotation. The paragraph's whole load-bearing content is a
    # DIRECTION ("the judge understates") plus three caveats. A rerun or a relabel
    # could flip the direction while every number in the prose still parses as a real
    # value somewhere, so the direction gets asserted against the data, and the three
    # caveats get asserted against the prose.
    hd = SUMMARY.parent / "human_direction.json"
    hb = SUMMARY.parent / "human_bootstrap.json"
    ha = SUMMARY.parent / "human_agreement.json"
    if hd.is_file() and hb.is_file() and ha.is_file():
        d, b, a = (json.loads(f.read_text(encoding="utf-8")) for f in (hd, hb, ha))

        checks += 1
        if d["human"]["delta"] < d["judge"]["delta"]:
            fails.append(
                f"the paper says the judge UNDERSTATES the effect, but the data now "
                f"says human {d['human']['delta']:+.4f} < judge "
                f"{d['judge']['delta']:+.4f}. That is a threat to the result, not a "
                f"footnote: rewrite the paragraph before touching this check")
        want(r"\emph{understates}", "the direction of the human/judge disagreement")

        # Every figure here is stated in more than one place: the section, the abstract
        # and the ledger. `want` only asks whether a number appears SOMEWHERE, so
        # editing one of two copies left the gate green. Negative testing caught five
        # of these at once. So match every occurrence and require them all to agree
        # with the data, which is the property the paper actually needs.
        # Match against a whitespace-normalised copy. Anchored patterns like
        # "Fisher exact $p=" silently missed the occurrence where LaTeX had wrapped
        # the line between the two words, so the gate was checking one of two copies
        # and reporting itself satisfied.
        flat_tex = re.sub(r"\s+", " ", tex)

        def all_equal(pattern, expected, label, groups=1):
            nonlocal checks
            checks += 1
            got = re.findall(pattern, flat_tex)
            if not got:
                fails.append(f"{label}: not stated anywhere in main.tex")
                return
            exp = expected if groups > 1 else (expected,)
            for g in got:
                vals = g if isinstance(g, tuple) else (g,)
                if any(abs(float(v) - float(e)) > 5e-9 for v, e in zip(vals, exp)):
                    fails.append(f"{label}: main.tex states {vals}, data says {exp} "
                                 f"({len(got)} occurrences, all must agree)")
                    return

        all_equal(r"\\kappa\s*=\s*([\d.]+)", round(a["cohens_kappa"], 2),
                  "Cohen's kappa")
        all_equal(r"[Aa]greement (?:is )?\$([\d.]+)\\%\$", 100 * a["raw_agreement"],
                  "raw human/judge agreement")
        all_equal(r"\$(\d+)\$ (?:stored memories|hand[- ]labelled items|hand labels)",
                  a["n"], "annotated sample size")
        all_equal(r"\$(\d+)\$ distinct claims", b["n_claims"],
                  "number of claims the sample was drawn from")

        # the asymmetry: both fractions and the p-value, everywhere each is stated
        all_equal(r"\$(\d+)/(\d+)\$ on field", b["disagree_field"],
                  "field disagreement fraction", groups=2)
        all_equal(r"\$(\d+)/(\d+)\$ on (?:bracketed|prose)", b["disagree_prose"],
                  "prose disagreement fraction", groups=2)
        all_equal(r"Fisher exact \$p=([\d.]+)\$", round(b["asymmetry_fisher_p"], 3),
                  "Fisher exact p for the disagreement asymmetry")
        checks += 1
        if b["asymmetry_fisher_p"] < 0.05 and "asymmetry" not in tex.lower():
            fails.append("the disagreement asymmetry is significant and the prose does "
                         "not name it")

        # the shift interval must be reported WITH its width, not just as a null
        lo, hi = (round(100 * v, 1) for v in b["shift_ci95"])
        all_equal(r"scorer[\s\S]{0,160}?\$\[([-+][\d.]+),\s*([-+][\d.]+)\]\$", (lo, hi),
                  "the scorer-swap interval", groups=2)

        # paragraph-scoped checks. Asking whether "author" appears ANYWHERE in a paper
        # that has an \author command is not a check; it passed while the caveat was
        # being deleted. Pull the two paragraphs out and ask of them specifically.
        def para(marker):
            i = tex.find(marker)
            if i == -1:
                return ""
            ends = [x for x in (tex.find(r"\paragraph{", i + len(marker)),
                                tex.find("\n\\section", i)) if x != -1]
            return tex[i:min(ends)] if ends else tex[i:]

        s5 = re.sub(r"\s+", " ", para(r"\paragraph{And fifty items a human read.}").lower())
        lim = re.sub(r"\s+", " ", para(r"\paragraph{One human read fifty of these").lower())
        checks += 1
        if not s5 or not lim:
            fails.append("the human-annotation paragraph or its limitation is gone; "
                         "every check below it is now vacuous")

        for where, name, phrase, why in (
            (s5, "S5", "one rater", "that there is a single annotator"),
            (s5, "S5", "author", "that the annotator is the paper's author"),
            (s5, "S5", "not blind to hypothesis",
             "that blind to condition is not blind to hypothesis"),
            (s5, "S5", "no inter-rater agreement",
             "that there is no inter-rater agreement"),
            (s5, "S5", "not validation of it",
             "that fifty author labels are a check on the instrument, not validation"),
            (lim, "limitations", "author",
             "that the annotator is the paper's author"),
            (lim, "limitations", "no inter-annotator", "that one rater yields no IAA"),
            (s5, "S5", f"$[{lo:+.1f}, {hi:+.1f}]$",
             "the scorer-swap interval itself, in the paragraph that reports the null"),
        ):
            checks += 1
            if where and phrase not in where:
                fails.append(f"the human-annotation caveat is missing from {name}: {why}")

        # the null must be reported with its width, in the paragraph that reports it
        checks += 1
        widest = max(abs(lo), abs(hi))
        # the effect the interval has to be compared against is the smaller of the two
        # per-model headline numbers. An earlier version keyed on "c60/pooled", which
        # does not exist in the summary, so this check was dead and passed everything.
        sizes = [abs(100 * cc[k]["rate_delta"]) for k in ROWS.values() if k in cc]
        headline = min(sizes) if sizes else None
        if (s5 and headline and widest >= headline
                and not re.search(r"fails? to exclude|does not exclude", s5)):
            fails.append(f"the scorer-swap interval spans {widest:.1f} points against a "
                         f"{headline:.1f}-point effect, and the paragraph reporting it "
                         f"does not say it fails to exclude a shift that size. A null "
                         f"stated without its width is the overclaim available here")

        # and the claim it must NOT make
        checks += 1
        for bad in ("human validation", "validated by a human", "human ground truth",
                    "is human validation"):
            for chunk, name in ((s5, "S5"), (lim, "limitations")):
                i = chunk.find(bad)
                while i != -1:
                    ctx = chunk[max(0, i - 90):i]
                    if not re.search(r"\b(not|no|missing|cannot|does not|do not)\s*$",
                                     ctx.strip() + " ") and not re.search(
                            r"\b(not|missing|cannot)\b", ctx[-40:]):
                        fails.append(f"{name} asserts {bad!r} for what is fifty labels "
                                     f"by the paper's own author")
                        break
                    i = chunk.find(bad, i + 1)

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
