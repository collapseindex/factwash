"""The first real leaderboard row: mem0 (haiku extraction) on the hearsay-v1 stimuli.

Drives a REAL mem0.Memory (its own extraction LLM, local embeddings, local vector
store) over the shipped 15-source corpus from experiments/live_run.py: ten hedged-
hearsay injections and five genuinely-confident legit controls. The two kinds are
scored as SEPARATE bench runs on purpose: a laundering rate on hearsay stimuli and a
flag rate on legit stimuli are different measurements, and averaging them would bury
the base-rate lesson the paper spends a section on.

Stimulus set id: hearsay-v1 (single-sourced from live_run.CORPUS; if that list changes,
this id must change with it). Pairs are streamed to a raw ledger per source before
scoring, so the run is auditable and rescorable offline for $0.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "data" / "results"
MODEL = "claude-haiku-4-5"
EMBED_MODEL, EMBED_DIMS = "BAAI/bge-small-en-v1.5", 384
STIMULI_ID = "hearsay-v1"


def _load_env():
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _corpus():
    spec = importlib.util.spec_from_file_location("live_run", ROOT / "experiments" / "live_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_run"] = mod        # @dataclass resolves types via sys.modules
    spec.loader.exec_module(mod)
    return mod.CORPUS


def main() -> int:
    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("no ANTHROPIC_API_KEY; aborting before any call")
    os.environ.setdefault("MEM0_TELEMETRY", "false")

    from factwash.bench import run_adapter, score_pairs
    from mem0 import Memory

    stamp = time.strftime("%Y%m%d_%H%M%S")
    store = Memory.from_config({
        "llm": {"provider": "anthropic", "config": {"model": MODEL, "max_tokens": 2000}},
        "embedder": {"provider": "fastembed",
                     "config": {"model": EMBED_MODEL, "embedding_dims": EMBED_DIMS}},
        "vector_store": {"provider": "qdrant",
                         "config": {"collection_name": f"bench_{stamp}",
                                    "embedding_model_dims": EMBED_DIMS,
                                    "path": str(ROOT / "data" / f"bench_qdrant_{stamp}")}},
    })

    ledger = RAW / f"{stamp}_mem0bench_{MODEL}_{STIMULI_ID}_s0.jsonl"
    RAW.mkdir(parents=True, exist_ok=True)
    fh = open(ledger, "a", encoding="utf-8")

    def adapter(source: str) -> list[str]:
        result = store.add(source, user_id="bench") or {}
        written = [(r.get("id"), r.get("memory", "")) for r in result.get("results", [])
                   if r.get("event") == "ADD"]
        for mem_id, _ in written:
            if mem_id:
                store.delete(mem_id)
        texts = [t for _, t in written if t]
        for t in texts:
            fh.write(json.dumps({"source": source, "memory": t}) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
        print(f"  mem0 wrote {len(texts)} memor{'y' if len(texts) == 1 else 'ies'} "
              f"for: {source[:60]!r}")
        return texts

    corpus = _corpus()
    RESULTS.mkdir(parents=True, exist_ok=True)
    for kind in ("injection", "legit"):
        sources = [text for _, k, text in corpus if k == kind]
        print(f"\n== {kind}: {len(sources)} sources ==")
        pairs, errors = run_adapter(adapter, sources)
        result = score_pairs(pairs, stimuli_id=f"{STIMULI_ID}/{kind}",
                             adapter_errors=errors)
        print()
        print(result.render())
        out = RESULTS / f"{stamp}_mem0bench_{MODEL}_{STIMULI_ID}-{kind}_s0_summary.json"
        out.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        print(f"summary: {out}")
    fh.close()
    print(f"\npairs ledger: {ledger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
