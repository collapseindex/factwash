"""Hand the seven disputed items to the reader, and ask a third instrument about them.

Fifty items were labelled by hand and the judge disagreed on seven. Reporting an
agreement statistic and stopping leaves the reader with nothing to check: they are told
two labellers differed and must take on trust that the difference is benign. So do two
things instead.

FIRST, print the disputed items verbatim, each with its claim, the human label and the
judge label, for the appendix. Five to ten short memories is nothing in an appendix, and
it turns an unresolved disagreement into raw material every reviewer can adjudicate
themselves. It does not replace a second annotator, but it is the part of a second
annotator that actually matters, and it does not depend on finding one.

SECOND, ask a question neither labeller can bias. Both are reading for stance, which is a
judgement. But "is any lexical trace of this claim in this memory at all" is not a
judgement, and `factwash.claims.content_words` already answers it: it is the same
containment the companion paper's gate uses to decide whether a stored claim is matched
to a source claim. So it is a third instrument on the disputed subset, not a new one
invented to settle a score.

That separates two very different reasons the two labellers could differ:

  NO TRACE     the memory contains little or none of the claim's content, and the judge
               said the claim was present anyway. That is the judge fuzzy-matching, and
               it is the failure mode that would actually threaten the result.

  REWORDED     the content is there and the two labellers disagree about what STANCE it
               is stored with. That is a hard call about hedging, not a hallucination,
               and it is the ordinary kind of annotation disagreement.

Seven items cannot support a statistic. This is descriptive, and the appendix says so.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "data" / "annotation" / "human_key.json"
SHEET = ROOT / "data" / "annotation" / "human_sheet.md"
OUT = ROOT / "data" / "results" / "human_disputed.json"
TEXOUT = ROOT / "writeup2" / "disputed_table.tex"

sys.path.insert(0, str(ROOT / "src"))
from factwash.claims import MIN_CONTAINMENT, content_words  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "a", ROOT / "experiments" / "two_cell_analyse.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def tex_escape(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")):
        s = s.replace(a, b)
    return s


def load_disputed():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    answers, item = {}, None
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            item = int(line[3:].strip())
        elif line.startswith("ANSWER:") and item is not None:
            v = line.split(":", 1)[1].strip().lower()
            if v:
                answers[item] = v

    rows, _ = A.balance(A.load())
    by_uid = {f"{r['run']}|{r['key']}": r for r in rows}

    sys.path.insert(0, str(ROOT / "experiments"))
    from claims_corpus import CORPORA
    from claims_corpus_v3 import V3
    claim_text = {c[0]: c[1] for c in CORPORA["all"] + V3}

    out = []
    for k in key["items"]:
        human = answers[k["item"]]
        if human == k["judge"]:
            continue
        src = by_uid.get(k["uid"])
        if src is None:
            print(f"  item {k['item']}: no stored memory found for {k['uid']}")
            continue
        claim = claim_text.get(k["pair"], k["pair"])
        cw = content_words(claim)
        mw = content_words(src["stored"])
        overlap = sorted(cw & mw)
        containment = len(overlap) / len(cw) if cw else 0.0
        out.append({
            "item": k["item"], "arm": k["arm"],
            "model": k["model"].replace("claude-", ""),
            "pressure": k["pressure"], "claim_id": k["pair"], "claim": claim,
            "stored": src["stored"].strip(),
            "human": human, "judge": k["judge"],
            "containment": round(containment, 3),
            "n_claim_words": len(cw), "n_overlap": len(overlap),
            "overlap": overlap,
            "reading": "no trace" if containment < MIN_CONTAINMENT else "reworded",
        })
    return sorted(out, key=lambda r: (r["arm"], r["item"]))


def main() -> int:
    d = load_disputed()
    if not d:
        print("no disagreements to show")
        return 1

    print(f"{len(d)} disputed items, containment threshold {MIN_CONTAINMENT}\n")
    hdr = f"{'#':>3} {'arm':<7} {'human':<17}{'judge':<17}{'cont':>6}  reading"
    print(hdr)
    print("-" * len(hdr))
    for r in d:
        print(f"{r['item']:>3} {r['arm']:<7} {r['human']:<17}{r['judge']:<17}"
              f"{r['containment']:>6.2f}  {r['reading']}")

    no_trace = [r for r in d if r["reading"] == "no trace"]
    print(f"\n  no trace  {len(no_trace):>2} / {len(d)}   the judge read a claim into a "
          f"memory that barely contains it")
    print(f"  reworded  {len(d) - len(no_trace):>2} / {len(d)}   the content survived and "
          f"the two labellers differ on its stance")
    print()
    if len(no_trace) > len(d) / 2:
        print("  Most disagreements are the judge matching text that is not there.")
        print("  That is fuzzy matching, it is the failure mode that would threaten")
        print("  the result, and it belongs in the paper as one.")
    else:
        print("  Most disagreements are about STANCE on content that did survive, not")
        print("  about whether the claim is present. That is the ordinary hard case in")
        print("  this task rather than a judge inventing text. Seven items cannot")
        print("  support a statistic; this is descriptive and the paper says so.")

    OUT.write_text(json.dumps(
        {"n_disputed": len(d), "min_containment": MIN_CONTAINMENT,
         "n_no_trace": len(no_trace), "n_reworded": len(d) - len(no_trace),
         "items": d,
         "note": "Descriptive, not inferential: seven items. Containment is the same "
                 "measure the companion paper's gate uses to decide whether a stored "
                 "claim is matched at all, so it is a third instrument on this subset "
                 "rather than one invented for it."},
        indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")

    # the appendix table: every disputed item verbatim, so a reader can adjudicate
    lines = [
        "% GENERATED by experiments/human_disputed.py -- do not edit by hand.",
        r"\begin{longtable}{@{}p{0.30\linewidth}p{0.62\linewidth}@{}}",
        r"\toprule",
        r"\endhead",
    ]
    for r in d:
        lines += [
            r"\textbf{Claim " + tex_escape(r["claim_id"]) + "} \\newline "
            + r"\footnotesize " + tex_escape(r["claim"]) + r" \newline\newline "
            + r"\textsc{" + tex_escape(r["arm"]) + r"} arm, " + tex_escape(r["model"])
            + r", \texttt{" + tex_escape(r["pressure"]) + r"} \newline "
            + r"human: \textbf{" + tex_escape(r["human"]) + r"} \newline "
            + r"judge: \textbf{" + tex_escape(r["judge"]) + r"} \newline "
            + f"content overlap: {r['n_overlap']}/{r['n_claim_words']} "
            + f"({r['containment']:.2f})"
            + " &",
            r"\footnotesize\ttfamily " + tex_escape(r["stored"]) + r" \\",
            r"\midrule",
        ]
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{longtable}")
    TEXOUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {TEXOUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
