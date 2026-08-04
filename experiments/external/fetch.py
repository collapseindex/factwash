"""Download the external corpora. Run once; everything after this is offline.

Deliberately uses urllib rather than curl or requests: curl fails the TLS handshake
against rgai.inf.u-szeged.hu in some environments (exit 35), and requests is not a
dependency of this package. Nothing here needs an API key.

Run:  python experiments/external/fetch.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[2] / "data" / "external"

# name -> (url, approximate bytes, what it is). The BioScope mirror on rgai.sed.hu that
# the HuggingFace bigbio loader points at presents a certificate for the wrong host, so
# the u-szeged.hu original is used instead.
FILES = {
    "bioscope.zip": (
        "https://rgai.inf.u-szeged.hu/sites/rgai.inf.u-szeged.hu/files/bioscope.zip",
        1_078_189, "BioScope: speculation + negation cues, biomedical"),
    "uncertainty.zip": (
        "https://rgai.inf.u-szeged.hu/sites/rgai.inf.u-szeged.hu/files/uncertainty.zip",
        2_356_389, "Szeged Uncertainty Corpus: wiki, factbank, bio"),
    "human_annotations_sentence.json": (
        "https://raw.githubusercontent.com/artidoro/frank/main/data/"
        "human_annotations_sentence.json",
        9_943_311, "FRANK: human factuality annotations, sentence level"),
    "benchmark_data.json": (
        "https://raw.githubusercontent.com/artidoro/frank/main/data/benchmark_data.json",
        7_824_473, "FRANK: articles and summaries"),
    "polnear.zip": (
        "https://github.com/networkdynamics/PolNeAR/archive/refs/heads/master.zip",
        53_889_792, "PolNeAR: attribution source/cue/content, political news"),
    # The only external MEMORY WRITES available. Small -- see eval_memgpt.py for why.
    "memgpt_msc_full.jsonl": (
        "https://huggingface.co/datasets/MemGPT/function-call-traces/resolve/main/"
        "msc_full.jsonl", 5_450_626, "MemGPT traces: multi-session chat"),
    "memgpt_docqa_full.jsonl": (
        "https://huggingface.co/datasets/MemGPT/function-call-traces/resolve/main/"
        "docqa_full.jsonl", 2_000_000, "MemGPT traces: document QA"),
    "memgpt_msc_correct_only_full.jsonl": (
        "https://huggingface.co/datasets/MemGPT/function-call-traces/resolve/main/"
        "msc_correct_only_full.jsonl", 4_000_000, "MemGPT traces: MSC, correct only"),
}


# Not in FILES: 443 MB, and only the corpus builder needs it. Fetch with --enron.
ENRON = ("https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz", 443_254_787,
         "Enron email: real workplace relay, for experiments/corpus/make_pool.py")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    if "--enron" in sys.argv:
        FILES["enron_mail.tar.gz"] = ENRON
    failures = []
    for name, (url, approx, what) in FILES.items():
        path = DEST / name
        if path.is_file() and path.stat().st_size > 0:
            print(f"have {name:38s} {path.stat().st_size:>10,} bytes")
            continue
        print(f"get  {name:38s} ~{approx:>9,} bytes  ({what})")
        try:
            data = urllib.request.urlopen(url, timeout=300).read()
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            failures.append(name)
            continue
        path.write_bytes(data)
        print(f"  wrote {len(data):,} bytes")

    if failures:
        print(f"\n{len(failures)} download(s) failed: {', '.join(failures)}.\n"
              f"URLs are listed in this file; fetch by hand into {DEST} and re-run.",
              file=sys.stderr)
        return 1
    print(f"\nall corpora in {DEST}\nnext: python experiments/external/build_corpora.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
