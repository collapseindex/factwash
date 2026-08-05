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

# Row label in the results table -> block key in the summary. "pooled" is included
# deliberately: an earlier version checked only the model rows, and negative testing
# showed the pooled row could be corrupted freely.
MODELS = {"Haiku 4.5": "claude-haiku-4-5", "Sonnet 4.5": "claude-sonnet-4-5",
          "Opus 4.5": "claude-opus-4-5", "Sonnet 5": "claude-sonnet-5",
          "pooled": "ALL"}


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
        b = blocks[key] if key == "ALL" else blocks[f"model={key}"]
        checks += 1
        row = re.search(rf"^{re.escape(nice)}\s*&(.+?)\\\\", tex, re.MULTILINE)
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

    # --- raw counts and discordant pairs in the prose ------------------------
    h = blocks["model=claude-haiku-4-5"]
    s = blocks["model=claude-sonnet-4-5"]
    o = blocks["model=claude-opus-4-5"]
    allb = blocks["ALL"]
    sev = blocks.get("claude-opus-4-5 / severe")

    for nice, b in (("Haiku", h), ("Sonnet 4.5", s), ("Opus", o), ("pooled", allb)):
        for arm in ("field", "paren"):
            want(f"{b[arm]['kept_qualified']}/{b[arm]['n']}", f"{nice} {arm} raw counts")

    for nice, b in (("Haiku", h), ("Sonnet 4.5", s), ("Opus", o), ("pooled", allb)):
        checks += 1
        if (str(b["paired"]["field_only"]) not in tex
                or str(b["paired"]["paren_only"]) not in tex):
            fails.append(f"{nice} discordant counts missing from tex")

    # --- p-values quoted in the prose must match the data --------------------
    for label, val, lit in (
            ("Haiku survival p", h["paired"]["mcnemar_exact_p"], "0.004"),
            ("Opus survival p", o["paired"]["mcnemar_exact_p"], "0.0003"),
            ("Sonnet eviction p", s["eviction_paired"]["mcnemar_exact_p"], "0.29"),
            ("Opus severe survival p", sev["paired"]["mcnemar_exact_p"], "0.0009")):
        checks += 1
        if abs(float(f"{val:.4g}") - float(lit)) > float(lit) * 0.12:
            fails.append(f"{label}: tex says {lit}, data says {val}")
        if lit not in tex:
            fails.append(f"{label}: {lit!r} not present in tex")

    # eviction counts, pooled and per-model
    for nice, b in (("pooled", allb), ("Haiku", h), ("Sonnet 4.5", s), ("Opus", o)):
        checks += 1
        if not (str(b["field"]["evicted"]) in tex and str(b["paren"]["evicted"]) in tex):
            fails.append(f"{nice} eviction counts missing")

    # --- total analysed pairs ------------------------------------------------
    want(f"${allb['paired']['pairs']}$", "total matched pairs")

    # --- the direction claims the prose makes --------------------------------
    checks += 1
    if allb["paren"]["evicted"] <= allb["field"]["evicted"]:
        fails.append("pooled eviction no longer runs against the parenthetical; the "
                     "'schema helps twice over' framing is now wrong")
    checks += 1
    if o["delta"] <= h["delta"]:
        fails.append("Opus no longer shows a larger effect than Haiku; the retraction "
                     "of 'helps where the compressor is weakest' no longer follows")
    checks += 1
    for lv in ("none", "low", "high", "extreme"):
        k = f"claude-opus-4-5 / {lv}"
        if k in blocks and blocks[k]["field"]["rate"] != 1.0:
            fails.append(f"Opus is no longer at ceiling at {lv}; the 'a ceiling is a "
                         f"statement about the test' argument needs rechecking")
            break

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
