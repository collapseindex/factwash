"""Normalise externally-annotated corpora into one sentence-level JSONL.

Nothing in this file is Factwash's data. BioScope and the Szeged Uncertainty Corpus were
annotated by linguists at HUN-REN-SZTE years before this project existed, which is the
entire point: every other number in this repo was measured on text the author wrote.

Both sources mark cue spans inside <xcope> scopes, but they disagree on the markup and
on how fine-grained the label is:

    BioScope            <cue type="speculation">    undifferentiated hedges
                        <cue type="negation">
    Szeged Uncertainty  <ccue type="speculation_modal_probable_">      and four more

The Szeged taxonomy is the more useful of the two, because its subtypes land on Factwash's
own distinctions rather than cutting across them -- ``_condition_`` is an external gold
standard for CONDITION_DROPPED, which until now had none.

Output rows (data/external/normalized/<corpus>.jsonl):

    corpus      short name, e.g. "wiki_weasel"
    doc, sid    document and sentence id from the corpus
    text        the sentence with all annotation markup stripped
    cues        [{"raw": corpus type, "cls": Factwash class, "text": surface form}]
    <cls>_cues  surface forms per class, for convenience: epistemic, doxastic,
                conditional, investigation, negation, speculation
    uncertain   bool, any speculation-family cue (the CoNLL-2010 Task 1 label)

Run:  python experiments/external/build_corpora.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "data" / "external"
OUT = EXTERNAL / "normalized"

# archive -> {member: corpus name}. The three uncertainty.zip members are separate
# DOMAINS, kept apart on purpose: a lexicon can look strong on biomedical abstracts and
# fall over on encyclopedic prose, and pooling them would hide exactly that.
SOURCES = {
    "bioscope.zip": {
        "abstracts.xml": "bioscope_abstracts",
        "full_papers.xml": "bioscope_papers",
        # clinical_merger/clinical_records_anon.xml is DELIBERATELY absent. The public
        # copy is redacted -- every token is "*", so a sentence reads "* * * * *." -- and
        # the real text has to be obtained separately and merged with the bundled
        # ScopeMerger.jar. Scoring it produced a clean-looking 0.00 precision and 0.00
        # recall across 6383 sentences, which is a property of the redaction and not of
        # Factwash. REDACTION_GUARD below keeps it out on evidence rather than on my
        # remembering to leave this line commented.
    },
    "uncertainty.zip": {
        "wiki.xml": "wiki_weasel",
        "factbank.xml": "factbank",
        "bio_bmc.xml": "bio_bmc",
        "bio_fly.xml": "bio_fly",
        "bio_hbc.xml": "bio_hbc",
    },
}

# Corpus cue type -> the Factwash component it is evidence about. Trailing spaces and
# case are stripped before lookup; the corpus writes "speculation_hypo_doxastic _".
#
# "investigation" is kept as its own class rather than folded into hedging. It marks
# research framing ("we examined whether X"), which is a genuine uncertainty cue in a
# paper and irrelevant to a memory write. Scoring Factwash against it would be scoring it
# on a task it does not claim to do.
CUE_CLASSES = {
    "speculation": "speculation",                     # BioScope, undifferentiated
    "negation": "negation",
    "speculation_modal_probable_": "epistemic",       # may, might, probably
    "speculation_modal_possible_": "epistemic",
    "speculation_hypo_doxastic_": "doxastic",         # believed, considered, thought to
    "speculation_hypo_condition_": "conditional",     # if, unless, provided that
    "speculation_hypo_investigation_": "investigation",
}
# Classes that mean "this sentence is not asserted as plain fact".
SPECULATION_FAMILY = {"speculation", "epistemic", "doxastic", "conditional", "investigation"}


# A corpus where this fraction of sentences is mostly redaction placeholders is not
# scorable text. Structural, so a redacted release can never quietly become a number.
REDACTION_GUARD = 0.25

# Fraction of DOCUMENTS held out for the test split. The split is by document and by a
# stable hash of the document id, so it does not move between runs and no sentence from
# a tuned-on document can leak into the reported score.
TEST_FRACTION = 0.5
SPLIT_SEED = "factwash-external-v1"


def _split_of(doc_id: str) -> str:
    digest = hashlib.sha256((SPLIT_SEED + "|" + doc_id).encode("utf-8")).digest()
    return "test" if (digest[0] / 256.0) < TEST_FRACTION else "dev"


def _redaction_rate(rows) -> float:
    if not rows:
        return 0.0
    redacted = sum(1 for r in rows
                   if r["text"].count("*") > max(len(r["text"].split()) // 2, 1))
    return redacted / len(rows)


def _norm_type(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "")


def _text_of(elem) -> str:
    return " ".join("".join(elem.itertext()).split())


def parse(xml_bytes: bytes, corpus: str):
    """Yield normalised rows. Handles <sentence>/<Sentence> and <cue>/<ccue>."""
    root = ET.fromstring(xml_bytes)
    unmapped: dict[str, int] = {}

    for doc in root.iter():
        if doc.tag != "Document":
            continue
        doc_id = ""
        for child in doc:
            if child.tag == "DocID":
                doc_id = (child.text or "").strip()
        for sent in doc.iter():
            if sent.tag.lower() != "sentence":
                continue
            text = _text_of(sent)
            if not text:
                continue
            cues = []
            for cue in sent.iter():
                if cue.tag not in ("cue", "ccue"):
                    continue
                raw = _norm_type(cue.get("type"))
                surface = _text_of(cue)
                if not surface:
                    continue
                cls = CUE_CLASSES.get(raw)
                if cls is None:
                    unmapped[raw] = unmapped.get(raw, 0) + 1
                    continue
                cues.append({"raw": raw, "cls": cls, "text": surface})
            row = {"corpus": corpus, "doc": doc_id, "sid": sent.get("id") or "",
                   "split": _split_of(doc_id), "text": text, "cues": cues}
            for cls in sorted(set(CUE_CLASSES.values())):
                row[f"{cls}_cues"] = [c["text"] for c in cues if c["cls"] == cls]
            row["uncertain"] = any(c["cls"] in SPECULATION_FAMILY for c in cues)
            yield row
    if unmapped:
        # Loud, not silent. An unmapped type is gold evidence being dropped on the floor,
        # and dropping it quietly would inflate every precision number computed downstream.
        print(f"  WARNING: {corpus} has UNMAPPED cue types {unmapped}; add them to "
              f"CUE_CLASSES or they are excluded from scoring", file=sys.stderr)


# --- PolNeAR ---------------------------------------------------------------------------
# A different corpus in a different format, for the one detector that had no external
# gold standard at all: LAUNDERED. PARC 3.0 is the usual reference for attribution, but it
# annotates Wall Street Journal text that needs a paid LDC licence. PolNeAR annotates
# 1,008 political news articles nobody has to pay for, token-level and univocal
# (source / cue / content, each token in at most one attribution), and ships its own
# train/dev/test split -- which is better than the hash split above, because someone else
# drew it.
#
# BRAT standoff format: a .ann file of character spans beside a .txt of the article. The
# offsets are UTF-8 character offsets and they line up exactly, verified before use.
POLNEAR_ZIP = "polnear.zip"
_ANN_LINE = re.compile(r"^T\d+\t(Source|Cue|Content|Attribution)\s+(\d+)\s+(\d+)\t(.*)$")
# Mirrors claims._SENTENCE_SPLIT, but offset-preserving: the detector sees one sentence at
# a time, so gold cues have to be attributed to the sentence they actually fall in.
_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences_with_offsets(text: str):
    out, start = [], 0
    for m in _SENT_BOUNDARY.finditer(text):
        if text[start:m.start()].strip():
            out.append((start, m.start(), text[start:m.start()]))
        start = m.end()
    if text[start:].strip():
        out.append((start, len(text), text[start:]))
    return out


def parse_polnear(zf: zipfile.ZipFile):
    """Yield rows for every PolNeAR sentence, carrying the corpus's own split."""
    names = zf.namelist()
    anns = [n for n in names
            if n.endswith(".ann") and "/attributions/" in n and "annotator-training" not in n]
    texts = {}
    for n in names:
        if n.endswith(".txt") and "/text/" in n:
            texts[Path(n).stem] = n

    for ann_name in sorted(anns):
        split = "test" if "/test/" in ann_name else "dev" if "/dev/" in ann_name else "train"
        # .ann filenames carry a 4-char disambiguating suffix the .txt does not.
        stem = Path(ann_name).stem
        txt_name = texts.get(stem) or texts.get(stem.rsplit("_", 1)[0])
        if txt_name is None:
            continue
        text = zf.read(txt_name).decode("utf-8")
        cues = []
        for line in zf.read(ann_name).decode("utf-8").splitlines():
            m = _ANN_LINE.match(line)
            # "Attribution" duplicates the Cue span as the relation anchor; counting both
            # would double every cue.
            if m and m.group(1) == "Cue":
                cues.append((int(m.group(2)), int(m.group(3)), m.group(4)))

        for lo, hi, sent in _sentences_with_offsets(text):
            sent = " ".join(sent.split())
            if not sent:
                continue
            here = [c for c in cues if lo <= c[0] < hi]
            row = {"corpus": "polnear", "doc": stem, "sid": f"{lo}",
                   "split": split, "text": sent,
                   "cues": [{"raw": "polnear_cue", "cls": "attribution", "text": c[2]}
                            for c in here]}
            for cls in sorted(set(CUE_CLASSES.values()) | {"attribution"}):
                row[f"{cls}_cues"] = [c["text"] for c in row["cues"] if c["cls"] == cls]
            row["uncertain"] = False   # PolNeAR does not annotate speculation
            yield row


def build_polnear() -> int:
    path = EXTERNAL / POLNEAR_ZIP
    if not path.is_file():
        print(f"  skip polnear: {path} absent", file=sys.stderr)
        return 0
    with zipfile.ZipFile(path) as z:
        rows = list(parse_polnear(z))
    if not rows:
        print("  WARNING: polnear parsed to zero rows", file=sys.stderr)
        return 0
    dest = OUT / "polnear.jsonl"
    with dest.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cued = sum(1 for r in rows if r["attribution_cues"])
    splits: dict[str, int] = {}
    for r in rows:
        splits[r["split"]] = splits.get(r["split"], 0) + 1
    print(f"{'polnear':22s} {len(rows):6d} sentences  {cued:5d} with an attribution cue "
          f"({100 * cued / len(rows):4.1f}%)  splits={splits}")
    return len(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for archive, members in SOURCES.items():
        path = EXTERNAL / archive
        if not path.is_file():
            print(f"missing {path}; see experiments/external/README.md for the URLs",
                  file=sys.stderr)
            continue
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            for member, corpus in members.items():
                if member not in names:
                    print(f"  skip {member}: not in {archive}", file=sys.stderr)
                    continue
                rows = list(parse(z.read(member), corpus))
                rate = _redaction_rate(rows)
                if rate > REDACTION_GUARD:
                    print(f"  REFUSING {corpus}: {100 * rate:.0f}% of sentences are "
                          f"redaction placeholders, not scorable text", file=sys.stderr)
                    continue
                dest = OUT / f"{corpus}.jsonl"
                with dest.open("w", encoding="utf-8") as fh:
                    for r in rows:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                unc = sum(r["uncertain"] for r in rows)
                by_cls = {}
                for r in rows:
                    for c in r["cues"]:
                        by_cls[c["cls"]] = by_cls.get(c["cls"], 0) + 1
                print(f"{corpus:22s} {len(rows):6d} sentences  "
                      f"{unc:5d} uncertain ({100 * unc / max(len(rows), 1):4.1f}%)  "
                      + "  ".join(f"{k}={v}" for k, v in sorted(by_cls.items())))
                total += len(rows)
    total += build_polnear()
    print(f"\n{total} sentences written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
