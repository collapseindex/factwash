"""Negative tests for check_paper.py.

A gate that has only ever passed is decorating, not checking. Each case breaks exactly
one thing and asserts the gate notices. Run it whenever check_paper.py changes.

Targets are DERIVED from the data, never hardcoded: an earlier version of this file
pinned a literal percentage, the numbers moved, and the mutation silently became a no-op
that "passed". A negative test that stops mutating anything is worse than none.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "main.tex"
SUMMARY = HERE.parent / "data" / "results" / "twocell_pooled_summary.json"
CHECK = HERE / "check_paper.py"

HAIKU = "c60/claude-haiku-4-5"
SONNET = "c60/claude-sonnet-4-5"


AB = SUMMARY.parent / "ablation_summary.json"
PR = SUMMARY.parent / "prereg_replication.json"
ABS = SUMMARY.parent / "ablation_summary_sonnet-4-5.json"
HD = SUMMARY.parent / "human_direction.json"
HB = SUMMARY.parent / "human_bootstrap.json"
HA = SUMMARY.parent / "human_agreement.json"
HDIS = SUMMARY.parent / "human_disputed.json"
TBL = HERE / "disputed_table.tex"


def _patch_abs(path, value):
    d = json.loads(ABS.read_text(encoding="utf-8"))
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    ABS.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_pr(path, value):
    d = json.loads(PR.read_text(encoding="utf-8"))
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    PR.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_ab(path, value):
    d = json.loads(AB.read_text(encoding="utf-8"))
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    AB.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_hd(path, value):
    d = json.loads(HD.read_text(encoding="utf-8"))
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    HD.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_hdis_counts(n_reworded, n_no_trace):
    """Make the disputed items look like the judge WAS matching absent text."""
    d = json.loads(HDIS.read_text(encoding="utf-8"))
    d["n_reworded"], d["n_no_trace"] = n_reworded, n_no_trace
    HDIS.write_text(json.dumps(d, indent=2), encoding="utf-8")


def run():
    return subprocess.run([sys.executable, str(CHECK)],
                          capture_output=True, text=True).returncode


def _patch(orig, path, value):
    d = json.loads(orig)
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    SUMMARY.write_text(json.dumps(d, indent=2), encoding="utf-8")


def main() -> int:
    orig_tex = TEX.read_text(encoding="utf-8")
    orig_sum = SUMMARY.read_text(encoding="utf-8")
    orig_ab = AB.read_text(encoding="utf-8")
    orig_pr = PR.read_text(encoding="utf-8")
    orig_abs = ABS.read_text(encoding="utf-8")
    orig_hd = HD.read_text(encoding="utf-8")
    orig_hdis = HDIS.read_text(encoding="utf-8")
    orig_tbl = TBL.read_text(encoding="utf-8")
    hdis = json.loads(orig_hdis)
    hd = json.loads(orig_hd)
    hb = json.loads(HB.read_text(encoding="utf-8"))
    ha = json.loads(HA.read_text(encoding="utf-8"))
    rep = json.loads(orig_sum)
    cc = rep["claim_clustered"]

    pts = f"${100 * cc[HAIKU]['rate_delta']:+.1f}$"
    assert pts in orig_tex, f"{pts} not in main.tex; the test target is stale"
    wins = f"${cc[HAIKU]['sign_test']['positive']}$"
    assert wins in orig_tex, f"{wins} not in main.tex; the test target is stale"

    _m = re.search(r"(\w+) withdrawn claims", orig_tex.lower())
    _count_word = _m.group(1) if _m else "eight"
    assert f"{_count_word} withdrawn claims" in orig_tex.lower(), "stale test target"

    cases = [
        (f"headline effect changed ({pts})",
         lambda: TEX.write_text(orig_tex.replace(pts, "$+99.9$"), encoding="utf-8")),
        (f"claims-favouring-field count changed ({wins})",
         lambda: TEX.write_text(orig_tex.replace(wins, "$999$"), encoding="utf-8")),
        ("a needsdata placeholder reinstated",
         lambda: TEX.write_text(
             orig_tex.replace(r"\section{Conclusion}",
                              "\\needsdata{x}\n\\section{Conclusion}"),
             encoding="utf-8")),
        ("a RETRACTED row downgraded",
         lambda: TEX.write_text(
             orig_tex.replace(r"\textsc{retracted}", r"\textsc{shown}", 2),
             encoding="utf-8")),
        ("NOT SHOWN / NOT CLAIMED rows deleted",
         lambda: TEX.write_text(
             orig_tex.replace(r"\textsc{not shown}", r"\textsc{shown}")
                     .replace(r"\textsc{not claimed}", r"\textsc{shown}"),
             encoding="utf-8")),
        ("a stale pair count reappears",
         lambda: TEX.write_text(
             orig_tex.replace("$60$ claims", "$950$ matched pairs", 1),
             encoding="utf-8")),
        ("the sign test stops being significant",
         lambda: _patch(orig_sum, ["claim_clustered", HAIKU, "sign_test", "p"], 0.4)),
        ("a claim-clustered interval starts containing zero",
         lambda: _patch(orig_sum, ["claim_clustered", SONNET,
                                   "ci95_claim_clustered"], [-0.05, 0.3])),
        ("the two models stop agreeing",
         lambda: _patch(orig_sum, ["claim_clustered", SONNET, "point"], 0.6)),
        ("the ten-claim corpus starts showing the effect",
         lambda: _patch(orig_sum, ["claim_clustered", "c10/claude-haiku-4-5",
                                   "ci95_claim_clustered"], [0.05, 0.3])),
        ("the padding control starts working",
         lambda: _patch_ab(["contrasts", "padded_vs_paren", "sign_p"], 0.001)),
        ("wording stops mattering",
         lambda: _patch_ab(["contrasts", "sentences_vs_promoted", "sign_p"], 0.6)),
        ("the pre-registered replication stops replicating",
         lambda: _patch_pr(["replicates"], False)),
        ("the registered size prediction stops holding",
         lambda: _patch_pr(["size_prediction_held"], False)),
        ("field starts beating plain sentences",
         lambda: _patch_ab(["contrasts", "field_vs_sentences", "sign_p"], 0.01)),
        ("wording starts working on Sonnet too",
         lambda: _patch_abs(["contrasts", "sentences_vs_promoted", "sign_p"], 0.001)),
        ("labels stop replicating on Sonnet",
         lambda: _patch_abs(["contrasts", "field_vs_unlabelled", "sign_p"], 0.4)),
        ("padding stops hurting on Sonnet",
         lambda: _patch_abs(["contrasts", "padded_vs_paren",
                             "mean_per_claim_delta"], 0.05)),
        ("a retracted claim reasserted in the intro",
         lambda: TEX.write_text(
             orig_tex.replace(r"\section{Related work}",
                              "What matters is whether the stance is asserted "
                              "or subordinated.\n\n" + r"\section{Related work}",
                              1),
             encoding="utf-8")),
        # target derived from the text, not pinned: the previous version mutated
        # "eight retractions" after the prose had changed to "withdrawn claims", so it
        # replaced nothing and passed. That is the third time a pinned literal has
        # quietly disabled a negative test in this project.
        (f"the stated withdrawn-claim count disagrees with itself ({_count_word})",
         lambda: TEX.write_text(
             orig_tex.replace(f"{_count_word} withdrawn claims",
                              "five withdrawn claims", 1), encoding="utf-8")),
        ("a headline tag goes missing",
         lambda: TEX.write_text(
             orig_tex.replace(" \\textsc{(headline)}", "", 1), encoding="utf-8")),
        ("the ablation arm count disagrees between sections",
         lambda: TEX.write_text(
             orig_tex.replace("the six forms", "the five forms", 1),
             encoding="utf-8")),
        ("a phantom effect size appears in the prose",
         lambda: TEX.write_text(
             orig_tex.replace("$+15.8$", "$+5.5$", 1), encoding="utf-8")),
        ("a judge reply became unusable",
         lambda: _patch(orig_sum, ["judge_parse", "failed"], 3)),

        # --- the human-annotation gate ---------------------------------------
        # Every case here is a way the paragraph could claim more than fifty labels
        # by the paper's own author can support. Targets are read out of the result
        # files so they cannot go stale into no-ops.
        # The paper once read the +0.4 margin as the judge being conservative. That was
        # withdrawn when the disputed items turned out to be annotator misses in one
        # arm, so the mutations that used to defend it now try to REINSTATE it.
        ("the withdrawn 'judge understates' reading is asserted again",
         lambda: TEX.write_text(
             orig_tex.replace(
                 "We drafted that margin as the judge understating the effect, which "
                 "would have made the\npaper's number conservative. Reading the disputed "
                 "items withdrew it.",
                 "The judge understates the effect, so the paper's number is "
                 "conservative."), encoding="utf-8")),
        ("the disputed-item table stops being included",
         lambda: TEX.write_text(
             orig_tex.replace(r"\input{disputed_table}", "", 1), encoding="utf-8")),
        (f"the disputed-item count drifts ({hdis['n_disputed']})",
         lambda: TEX.write_text(
             re.sub(r"\bseven\b", "five", orig_tex), encoding="utf-8")),
        (f"the content-overlap ratio drifts ({hdis['n_reworded']}/"
         f"{hdis['n_disputed']})",
         lambda: TEX.write_text(
             re.sub("six of the seven", "four of the seven", orig_tex,
                    flags=re.I), encoding="utf-8")),
        ("the prose-arm concentration of disputed items drifts",
         lambda: TEX.write_text(
             re.sub(r"six of the seven sit in the prose arm",
                    "two of the seven sit in the prose arm", orig_tex, flags=re.I),
             encoding="utf-8")),
        ("the containment range drifts",
         lambda: TEX.write_text(
             orig_tex.replace(r"containment $0.25$ to $0.83$",
                              r"containment $0.55$ to $0.83$", 1), encoding="utf-8")),
        ("the disputed memories stop containing the claim (data)",
         lambda: _patch_hdis_counts(1, 6)),
        ("disputed_table.tex loses a row",
         lambda: TBL.write_text(
             orig_tbl.replace("\\midrule", "", 1), encoding="utf-8")),
        (f"raw agreement drifts ({100 * ha['raw_agreement']:.1f}%)",
         lambda: TEX.write_text(
             orig_tex.replace(f"${100 * ha['raw_agreement']:.1f}" + r"\%$",
                              r"$91.0\%$", 1), encoding="utf-8")),
        (f"kappa drifts in S5 ({ha['cohens_kappa']:.2f})",
         lambda: TEX.write_text(
             orig_tex.replace(r"\kappa = " + f"{ha['cohens_kappa']:.2f}$",
                              r"\kappa = 0.93$", 1), encoding="utf-8")),
        (f"kappa drifts in the abstract ({ha['cohens_kappa']:.2f})",
         lambda: TEX.write_text(
             orig_tex.replace(r"\kappa=" + f"{ha['cohens_kappa']:.2f}$",
                              r"\kappa=0.93$", 1), encoding="utf-8")),
        (f"the annotated sample size drifts ({ha['n']})",
         lambda: TEX.write_text(
             orig_tex.replace(f"${ha['n']}$ stored memories",
                              "$80$ stored memories", 1), encoding="utf-8")),
        (f"the claim count drifts ({hb['n_claims']})",
         lambda: TEX.write_text(
             orig_tex.replace(f"${hb['n_claims']}$ distinct claims",
                              "$44$ distinct claims", 1), encoding="utf-8")),
        (f"the field disagreement fraction drifts ({hb['disagree_field']})",
         lambda: TEX.write_text(
             orig_tex.replace("${}/{}$".format(*hb["disagree_field"]),
                              "$0/26$", 1), encoding="utf-8")),
        (f"the prose disagreement fraction drifts ({hb['disagree_prose']})",
         lambda: TEX.write_text(
             orig_tex.replace("${}/{}$".format(*hb["disagree_prose"]),
                              "$2/24$", 1), encoding="utf-8")),
        (f"the Fisher p drifts ({hb['asymmetry_fisher_p']:.3f})",
         lambda: TEX.write_text(
             orig_tex.replace(f"$p={hb['asymmetry_fisher_p']:.3f}$",
                              "$p=0.245$", 1), encoding="utf-8")),
        ("the significant asymmetry stops being named",
         lambda: TEX.write_text(
             re.sub("asymmetry", "difference", orig_tex, flags=re.I),
             encoding="utf-8")),
        ("the scorer-swap interval is dropped",
         lambda: TEX.write_text(
             orig_tex.replace("$[{:+.1f}, {:+.1f}]$".format(
                 *[100 * b for b in hb["shift_ci95"]]), "a narrow interval", 1),
             encoding="utf-8")),
        ("the wide null is reported as if it were tight",
         lambda: TEX.write_text(
             re.sub(r"(?:it|which) also fails to exclude a\s+shift the size of "
                    r"the entire\s+effect\.", "The scorer makes no difference.",
                    orig_tex.replace("does not exclude a shift the size of the effect",
                                     "is tight")), encoding="utf-8")),
        ("the single-rater caveat is dropped",
         lambda: TEX.write_text(
             re.sub("one rater", "several raters", orig_tex, flags=re.I),
             encoding="utf-8")),
        ("the annotator stops being identified as the author",
         lambda: TEX.write_text(
             re.sub(r"\bauthor(?!s)", "annotator", orig_tex), encoding="utf-8")),
        ("the blind-to-hypothesis caveat is dropped",
         lambda: TEX.write_text(
             re.sub(r"not blind to\s+hypothesis", "blind throughout", orig_tex),
             encoding="utf-8")),
        ("the no-inter-rater caveat is dropped",
         lambda: TEX.write_text(
             orig_tex.replace("no inter-rater agreement",
                              "strong inter-rater agreement"), encoding="utf-8")),
        ("fifty author labels are upgraded to human validation",
         lambda: TEX.write_text(
             re.sub(r"It\s+is a check on the instrument, not validation of it\.",
                    "This is human validation of the effect.", orig_tex),
             encoding="utf-8")),
    ]

    if run() != 0:
        print("BASELINE FAILS -- fix the paper before negative-testing the gate")
        return 1

    bad = 0
    for name, mutate in cases:
        try:
            mutate()
            rc = run()
        finally:
            TEX.write_text(orig_tex, encoding="utf-8")
            SUMMARY.write_text(orig_sum, encoding="utf-8")
            AB.write_text(orig_ab, encoding="utf-8")
            PR.write_text(orig_pr, encoding="utf-8")
            ABS.write_text(orig_abs, encoding="utf-8")
            HD.write_text(orig_hd, encoding="utf-8")
            HDIS.write_text(orig_hdis, encoding="utf-8")
            TBL.write_text(orig_tbl, encoding="utf-8")
        ok = rc != 0
        bad += not ok
        print(("CAUGHT " if ok else "MISSED ") + name)

    print()
    if bad:
        print(f"{bad}/{len(cases)} mutations went undetected -- the gate has holes")
        return 1
    print(f"all {len(cases)} mutations caught; baseline still passes ({run() == 0})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

