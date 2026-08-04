"""Run the gate over real memory writes emitted by a different agent system.

Every memory write Factwash had ever been measured on was produced by this project's own
extractor. These are not: they come from MemGPT function-call traces, where an agent with
a completely different memory API (core_memory_append, archival_memory_insert) decided on
its own what was worth storing, and the conversation that preceded each write is in the
trace beside it.

READ THE COUNT BEFORE THE RESULT
--------------------------------
There are 18 of them. The dataset advertises ~2,750 function calls but is overwhelmingly
RETRIEVAL -- conversation_search, archival_memory_search, send_message. Actual writes:

    core_memory_append        17
    archival_memory_insert     1
    core_memory_replace        0     (despite being listed as a supported call)

So this is a SMOKE TEST, not a measurement. Eighteen items cannot support a precision
figure and none of them carry a label. What they can do is answer "does the gate behave
sanely on writes from an agent nobody here built", and that turned out to be worth asking:
one of the eighteen is a textbook instance of the failure this tool exists for, and
another exposed a limitation no local corpus had.

Run:  python experiments/external/eval_memgpt.py
"""
from __future__ import annotations

import collections
import json
from datetime import datetime
from pathlib import Path

import factwash

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "data" / "external"
RESULTS = ROOT / "data" / "results"

WRITE_CALLS = {"core_memory_append", "core_memory_replace", "archival_memory_insert"}
TRACE_FILES = ["memgpt_msc_full.jsonl", "memgpt_docqa_full.jsonl",
               "memgpt_msc_correct_only_full.jsonl"]


def extract_writes():
    """Yield (source, memory, call_name, trace) for every real memory write.

    The source is every user and assistant turn BEFORE the write, which is what the
    agent had in front of it. Deduplicated: msc_correct_only is a subset of msc_full,
    so a write present in both is one write, not two.
    """
    seen, out = set(), []
    for name in TRACE_FILES:
        path = EXTERNAL / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            turns = json.loads(line)
            for i, turn in enumerate(turns):
                call = turn.get("function_call") or {}
                if call.get("name") not in WRITE_CALLS:
                    continue
                try:
                    args = json.loads(call.get("arguments") or "{}")
                except json.JSONDecodeError:
                    continue
                memory = (args.get("content") or "").strip()
                if not memory:
                    continue
                # turns[:i + 1], NOT turns[:i]. The write turn's own content is the
                # agent's inner monologue -- the reasoning that produced the write, and
                # the single most relevant piece of source context there is. Dropping it
                # cost the Barnaby case its supersession evidence: the sentence that
                # retracts the earlier denial ("there seem to be some mentions of Barnaby
                # ... including one where I said he is a gray German Shepherd") lives in
                # the same turn as the function call.
                source = "\n".join(
                    f"{t.get('role')}: {t.get('content', '')}" for t in turns[:i + 1]
                    if t.get("role") in ("user", "assistant") and t.get("content"))
                key = (memory, source[:400])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"source": source, "memory": memory,
                            "call": call["name"], "trace": name})
    return out


def main() -> int:
    writes = extract_writes()
    if not writes:
        print("no MemGPT traces; see experiments/external/README.md for the URLs")
        return 1

    verdicts, flags, rows = collections.Counter(), collections.Counter(), []
    for w in writes:
        report = factwash.check(w["source"], w["memory"])
        named = sorted({f.name for f in report.flags if f.severity != "info"})
        verdicts[report.verdict] += 1
        flags.update(named)
        rows.append({**w, "verdict": report.verdict, "flags": named,
                     "evidence": [f.evidence for f in report.flags if f.severity != "info"]})

    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "corpus": "MemGPT/function-call-traces (HuggingFace), real agent memory writes",
        "n_writes": len(writes),
        "calls": dict(collections.Counter(w["call"] for w in writes)),
        "verdicts": dict(verdicts), "flags": dict(flags),
        "rows": rows,
        "interpretation_caveat": (
            "n=18 and UNLABELLED. This is a smoke test on externally-produced memory "
            "writes, not a measurement: no precision or recall figure may be quoted from "
            "it. The dataset is dominated by retrieval calls, not writes."),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = RESULTS / f"{stamp}_external_memgpt_writes_s0.json"
    dest.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{len(writes)} real memory writes from MemGPT traces "
          f"({dict(collections.Counter(w['call'] for w in writes))})")
    print(f"verdicts: {dict(verdicts)}")
    print(f"flags:    {dict(flags)}")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
