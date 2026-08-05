"""Negative tests for check_paper.py.

A gate that has only ever passed is decorating, not checking. Each case below breaks
exactly one thing and asserts the gate notices. Run it whenever check_paper.py changes.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "main.tex"
SUMMARY = HERE.parent / "data" / "results" / "twocell_pooled_summary.json"
CHECK = HERE / "check_paper.py"


def run():
    r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True)
    return r.returncode


def main() -> int:
    orig_tex = TEX.read_text(encoding="utf-8")
    orig_sum = SUMMARY.read_text(encoding="utf-8")

    cases = []

    def case(name, mutate):
        cases.append((name, mutate))

    # Derived from the data, never hardcoded: an earlier version of this test pinned a
    # literal percentage, the numbers moved, and the mutation silently became a no-op
    # that "passed". A negative test that stops mutating anything is worse than none.
    rep = json.loads(orig_sum)
    pooled = rep["blocks"]["ALL"]
    live_pct = f"{100 * pooled['field']['rate']:.1f}\\%"
    assert live_pct in orig_tex, f"{live_pct} not in main.tex; test target is stale"
    case(f"headline percentage changed ({live_pct})",
         lambda: TEX.write_text(orig_tex.replace(live_pct, "99.9\\%"),
                                encoding="utf-8"))

    live_cnt = f"{pooled['field']['kept_qualified']}/{pooled['field']['n']}"
    assert live_cnt in orig_tex, f"{live_cnt} not in main.tex; test target is stale"
    case(f"pooled raw counts changed ({live_cnt})",
         lambda: TEX.write_text(orig_tex.replace(live_cnt, "999/999"),
                                encoding="utf-8"))
    case("a needsdata placeholder reinstated",
         lambda: TEX.write_text(orig_tex.replace(r"\section{Conclusion}",
                                                 "\\needsdata{x}\n\\section{Conclusion}"),
                                encoding="utf-8"))
    case("RETRACTED row deleted from the ledger",
         lambda: TEX.write_text(orig_tex.replace(r"\textsc{retracted}", r"\textsc{shown}"),
                                encoding="utf-8"))
    case("NOT SHOWN rows deleted from the ledger",
         lambda: TEX.write_text(orig_tex.replace(r"\textsc{not shown}", r"\textsc{shown}")
                                .replace(r"\textsc{not claimed}", r"\textsc{shown}"),
                                encoding="utf-8"))
    case("Opus no longer at ceiling",
         lambda: _patch_summary(orig_sum, "claude-opus-4-5 / high", "field", "rate", 0.9))
    case("pooled eviction flips direction",
         lambda: _patch_summary(orig_sum, "ALL", "paren", "evicted", 1))
    case("Opus effect no longer exceeds Haiku's",
         lambda: _patch_delta(orig_sum, "model=claude-opus-4-5", 0.001))
    # The class of bug this gate was blind to until it was added: a stale figure
    # surviving alongside the correct one, so "the right number is present" passes.
    case("a stale pair count reappears in the prose",
         lambda: TEX.write_text(
             orig_tex.replace("across $950$ matched pairs", "across $860$ matched pairs",
                              1), encoding="utf-8"))
    case("a grouped total stops being a real sum",
         lambda: TEX.write_text(orig_tex.replace("$370$ paired trials",
                                                 "$371$ paired trials"),
                                encoding="utf-8"))
    case("a Sonnet model stops being null",
         lambda: _patch_p(orig_sum, "model=claude-sonnet-5", 0.001))
    case("Haiku stops being significant",
         lambda: _patch_p(orig_sum, "model=claude-haiku-4-5", 0.4))
    case("a judge reply became unusable",
         lambda: _patch_parse(orig_sum, 3))

    baseline = run()
    if baseline != 0:
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
        ok = rc != 0
        bad += not ok
        print(("CAUGHT " if ok else "MISSED ") + name)

    print()
    if bad:
        print(f"{bad}/{len(cases)} mutations went undetected -- the gate has holes")
        return 1
    print(f"all {len(cases)} mutations caught; baseline still passes ({run() == 0})")
    return 0


def _patch_summary(orig, block, arm, key, val):
    d = json.loads(orig)
    d["blocks"][block][arm][key] = val
    SUMMARY.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_p(orig, block, val):
    d = json.loads(orig)
    d["blocks"][block]["paired"]["mcnemar_exact_p"] = val
    SUMMARY.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_delta(orig, block, val):
    d = json.loads(orig)
    d["blocks"][block]["delta"] = val
    SUMMARY.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _patch_parse(orig, n):
    d = json.loads(orig)
    d["judge_parse"]["failed"] = n
    SUMMARY.write_text(json.dumps(d, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
