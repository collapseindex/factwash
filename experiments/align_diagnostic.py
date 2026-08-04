"""Alignment-vs-detector miss attribution. Gate item 1 of the release build-out.

The question that decides whether embedding alignment gets built: of the writes the
gate misses, how many does the ALIGNER lose (no source sentence matched, so no detector
ever ran) versus the DETECTORS (right sentence compared, lexicon does not know the
phrasing)? If the aligner's share is small, embedding alignment is architecture theater
and the recall ceiling is a lexicon fact, exactly as the paper claims.

Method per missed write (gate verdict not REWRITE/REJECT on an expect-flag item):
  - align every memory sentence against the source with the same matcher the checks use;
  - no sentence aligns          -> ALIGNMENT loss (detector never saw the evidence)
  - some sentence aligns        -> DETECTOR loss (the cue was in reach; the lexicon or
                                    window failed), because adversarial sources are
                                    single sentences: an alignment cannot be "wrong",
                                    only absent.
Also reports every UNCHECKABLE on the blind labelled corpus with its label, since an
UNCHECKABLE bad write is an alignment loss by definition and an UNCHECKABLE good write
is the aligner being honest.

Self-check: plants one known paraphrase pair (zero content-word overlap; must classify
ALIGNMENT) and one known lexicon-covered pair (must flag, i.e. not a miss at all). The
diagnostic refuses to report if either plant misbehaves.
"""
import json
import sys
from pathlib import Path

import factwash
from factwash.claims import match_source_window, sentences, strip_roles

ROOT = Path(__file__).resolve().parents[1]
BLOCKING = ("REWRITE", "REJECT")


def gate_misses(rows):
    out = []
    for r in rows:
        if r.get("class") != "evasion" or r.get("expect") != "flag":
            continue
        verdict = factwash.check(r["source"], r["memory"]).verdict
        if verdict not in BLOCKING:
            out.append((r, verdict))
    return out


def classify(source, memory):
    src_sents = sentences(strip_roles(source))
    aligned = [m for m in sentences(memory)
               if match_source_window(m, src_sents) is not None]
    return "DETECTOR" if aligned else "ALIGNMENT"


def main() -> int:
    # --- self-check: the classifier must be able to produce both answers -------------
    plant_para = classify("The felines appear ravenous this evening.",
                          "Our cats might be hungry.")
    plant_hit = factwash.check("Someone said the deploy is risky.",
                               "The deploy is risky.").verdict in BLOCKING
    if plant_para != "ALIGNMENT" or not plant_hit:
        print(f"SELF-CHECK FAILED: paraphrase->{plant_para} (want ALIGNMENT), "
              f"lexicon-covered flagged={plant_hit} (want True). Not reporting.")
        return 1
    print("self-check ok: paraphrase classifies ALIGNMENT, covered case still flags\n")

    # --- adversarial corpora ---------------------------------------------------------
    totals = {}
    for name in ("stress_corpus.jsonl", "stress_heldout.jsonl"):
        rows = [json.loads(l) for l in
                (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8").splitlines()
                if l.strip()]
        misses = gate_misses(rows)
        counts = {"ALIGNMENT": 0, "DETECTOR": 0}
        print(f"== {name}: {len(misses)} evasion misses ==")
        for r, verdict in misses:
            cls = classify(r["source"], r["memory"])
            counts[cls] += 1
            print(f"  {cls:9} [{verdict}] {r['id']:22} why: {r['why']}")
        totals[name] = counts
        print(f"  -> alignment {counts['ALIGNMENT']}, detector {counts['DETECTOR']}\n")

    # --- blind labelled corpus: where do UNCHECKABLEs fall? --------------------------
    d = ROOT / "data" / "corpus"
    sess = (d / "session_pool_enron_s0_s0.jsonl").read_text(encoding="utf-8").splitlines()
    items = {it["idx"]: it for it in (json.loads(l) for l in sess[1:] if l.strip())}
    labels = {r["idx"]: r["label"] for r in
              (json.loads(l) for l in
               (d / "session_pool_enron_s0_s0_labels.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip())}
    unch = []
    for idx, lab in labels.items():
        it = items[idx]
        if factwash.check(it["source"], it["memory"]).verdict == "UNCHECKABLE":
            unch.append((idx, lab, it))
    bad = sum(1 for _, lab, _ in unch if lab == "flag")
    print(f"== blind corpus: {len(unch)} UNCHECKABLE of {len(labels)} labelled "
          f"({bad} labelled bad = alignment losses that matter) ==")
    for idx, lab, it in unch:
        print(f"  [{lab:9}] idx {idx}: memory: {it['memory'][:80]!r}")

    a = sum(c["ALIGNMENT"] for c in totals.values()) + bad
    dt = sum(c["DETECTOR"] for c in totals.values())
    print(f"\nVERDICT INPUT: alignment-attributable losses {a}, "
          f"detector-attributable {dt} (adversarial) "
          f"+ {len(unch) - bad} honest uncheckables on good writes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
