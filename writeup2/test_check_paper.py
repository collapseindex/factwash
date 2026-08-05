"""Negative tests for check_paper.py.

A gate that has only ever passed is decorating, not checking. Each case breaks exactly
one thing and asserts the gate notices. Run it whenever check_paper.py changes.

Targets are DERIVED from the data, never hardcoded: an earlier version of this file
pinned a literal percentage, the numbers moved, and the mutation silently became a no-op
that "passed". A negative test that stops mutating anything is worse than none.
"""
import json
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
    rep = json.loads(orig_sum)
    cc = rep["claim_clustered"]

    pts = f"${100 * cc[HAIKU]['rate_delta']:+.1f}$"
    assert pts in orig_tex, f"{pts} not in main.tex; the test target is stale"
    wins = f"${cc[HAIKU]['sign_test']['positive']}$"
    assert wins in orig_tex, f"{wins} not in main.tex; the test target is stale"

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
        ("the stated retraction count disagrees with itself",
         lambda: TEX.write_text(
             orig_tex.replace("eight retractions", "five retractions", 1),
             encoding="utf-8")),
        ("the ablation arm count disagrees between sections",
         lambda: TEX.write_text(
             orig_tex.replace("the six forms", "the five forms", 1),
             encoding="utf-8")),
        ("a phantom effect size appears in the prose",
         lambda: TEX.write_text(
             orig_tex.replace("$+15.8$", "$+5.5$", 1), encoding="utf-8")),
        ("a judge reply became unusable",
         lambda: _patch(orig_sum, ["judge_parse", "failed"], 3)),
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
