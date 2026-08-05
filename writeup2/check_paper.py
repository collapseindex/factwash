"""Consistency gate for paper 2.

Same discipline as paper 1: every load-bearing number in main.tex is re-derived from
``data/results/twocell_pooled_summary.json`` and compared. A number that drifts from the
run that produced it fails here rather than in review.

Also fails on leftover \\needsdata placeholders and on an empty claims ledger.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "main.tex"
SUMMARY = HERE.parent / "data" / "results" / "twocell_pooled_summary.json"

MODELS = {"Haiku": "claude-haiku-4-5", "Sonnet": "claude-sonnet-4-5",
          "Opus": "claude-opus-4-5"}


def pct(x):
    return f"{100 * x:.1f}"


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    rep = json.loads(SUMMARY.read_text(encoding="utf-8"))
    blocks = rep["blocks"]
    fails, checks = [], 0

    def want(literal, why):
        nonlocal checks
        checks += 1
        if literal not in tex:
            fails.append(f"{why}: main.tex does not contain {literal!r}")

    # --- the results table, parsed and compared field by field ---------------
    # An earlier version accepted EITHER the percentage OR the raw count, which meant
    # corrupting the percentage was masked by the count still being present. Negative
    # testing caught it. Parse the row and check every cell.
    for nice, key in MODELS.items():
        b = blocks[f"model={key}"]
        checks += 1
        row = re.search(rf"^{nice} 4\.5\s*&(.+?)\\\\", tex, re.MULTILINE)
        if not row:
            fails.append(f"{nice}: no results-table row found in main.tex")
            continue
        cells = [c.strip() for c in row.group(1).split("&")]
        if len(cells) != 4:
            fails.append(f"{nice}: results row has {len(cells)} cells, expected 4")
            continue
        got_n, got_f, got_p, _ = cells
        for label, got, exp in (
                ("pairs", got_n, str(b["paired"]["pairs"])),
                ("field rate", got_f, pct(b["field"]["rate"])),
                ("paren rate", got_p, pct(b["paren"]["rate"]))):
            checks += 1
            nums = re.findall(r"\d+(?:\.\d+)?", got)
            if not nums:
                fails.append(f"{nice} {label}: no number in table cell {got!r}")
            elif abs(float(nums[0]) - float(exp)) > 0.051:
                fails.append(f"{nice} {label}: table says {nums[0]}, data says {exp}")

    # --- raw counts must also appear in the prose ----------------------------
    h = blocks["model=claude-haiku-4-5"]
    s = blocks["model=claude-sonnet-4-5"]
    for nice, b in (("Haiku", h), ("Sonnet", s)):
        for arm in ("field", "paren"):
            want(f"{b[arm]['kept_qualified']}/{b[arm]['n']}", f"{nice} {arm} raw counts")

    # --- the two significant McNemar results --------------------------------
    checks += 1
    if f"{h['paired']['field_only']}" not in tex or f"{h['paired']['paren_only']}" not in tex:
        fails.append("Haiku discordant counts missing from tex")
    for label, val, lit in (
            ("Haiku survival p", h["paired"]["mcnemar_exact_p"], "0.004"),
            ("Haiku eviction p", h["eviction_paired"]["mcnemar_exact_p"], "0.031"),
            ("Sonnet eviction p", s["eviction_paired"]["mcnemar_exact_p"], "0.039")):
        checks += 1
        if abs(round(val, 3) - float(lit)) > 0.0005:
            fails.append(f"{label}: tex says {lit}, data says {round(val, 5)}")
        if lit not in tex:
            fails.append(f"{label}: {lit!r} not present in tex")

    # eviction counts
    checks += 1
    if not (str(h["field"]["evicted"]) in tex and str(h["paren"]["evicted"]) in tex):
        fails.append("Haiku eviction counts missing")
    checks += 1
    if not (str(s["field"]["evicted"]) in tex and str(s["paren"]["evicted"]) in tex):
        fails.append("Sonnet eviction counts missing")

    # --- total analysed pairs ------------------------------------------------
    total_pairs = blocks["ALL"]["paired"]["pairs"]
    want(f"${total_pairs}$", "total matched pairs")

    # --- Opus must be reported as ceiling, not as a null ---------------------
    o = blocks["model=claude-opus-4-5"]
    checks += 1
    if not (o["field"]["rate"] == o["paren"]["rate"] == 1.0):
        fails.append("Opus is no longer at ceiling; the 'nothing to prevent' framing "
                     "in the abstract and conclusion is now wrong")

    # --- judge parse health --------------------------------------------------
    parse = rep["judge_parse"]
    bad = sum(v for k, v in parse.items() if k in ("failed", "template_echo", "unknown"))
    checks += 1
    if bad:
        fails.append(f"{bad} unusable judge replies; tex claims none")
    want(f"{parse.get('regex', 0)}/{rep['n_trials_analysed']}", "fallback parse rate")

    # --- the prediction must still be reported as falsified ------------------
    checks += 1
    if rep["prediction_check"]["held"]:
        fails.append("the pre-registered prediction now holds; the tex still calls it "
                     "contradicted")
    checks += 1
    if "retracted" not in tex.lower():
        fails.append("claims ledger has no RETRACTED row for the pressure prediction")

    # --- no placeholders, ledger present -------------------------------------
    checks += 1
    n_ph = len(re.findall(r"\\needsdata\{", tex))
    if n_ph:
        fails.append(f"{n_ph} \\needsdata placeholders remain")
    checks += 1
    if tex.count(r"\textsc{not shown}") + tex.count(r"\textsc{not claimed}") < 2:
        fails.append("claims ledger has fewer than two NOT SHOWN / NOT CLAIMED rows; "
                     "that is usually a sign it stopped being honest")

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
