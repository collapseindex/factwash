"""CLI: `factwash check` (the real gate) and `factwash audit` (labeled surface scan)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import check
from .report import EXIT_CODES
from .surface import DISCLAIMER, surface_scan

MAX_FILE_BYTES = 10 * 1024 * 1024


def _read(path: str) -> str:
    p = Path(path).resolve()
    if not p.is_file():
        raise SystemExit(f"factwash: not a file: {p}")
    if p.stat().st_size > MAX_FILE_BYTES:
        raise SystemExit(f"factwash: {p.name} exceeds the {MAX_FILE_BYTES // (1024 * 1024)}MB cap")
    return p.read_text(encoding="utf-8", errors="replace")


def _cmd_check(args) -> int:
    report = check(_read(args.source), _read(args.memory))
    if args.fix and report.verdict in ("REWRITE", "REJECT"):
        from .fixer import fix  # imports anthropic lazily; clear error if missing
        result = fix(_read(args.source), _read(args.memory))
        payload = {"verdict": result.verdict, "rewrite": result.text,
                   "prompt_used": result.prompt_used, "report": result.report.to_dict()}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(result.report.render())
            print(f"\nrewrite ({result.prompt_used}):\n{result.text}")
        return EXIT_CODES.get(result.verdict, 2)
    print(json.dumps(report.to_dict(), indent=2) if args.json else report.render())
    return EXIT_CODES[report.verdict]


def _iter_memories(path: Path):
    """Yield (label, memory_text) from a .jsonl store dump, a single text file, or a directory."""
    if path.is_dir():
        for f in sorted(path.glob("*.txt")) + sorted(path.glob("*.md")):
            yield f.name, f.read_text(encoding="utf-8", errors="replace")
        return
    if path.suffix == ".jsonl":
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                yield f"line {i + 1}", line
                continue
            yield f"line {i + 1}", obj.get("memory") or obj.get("text") or ""
        return
    yield path.name, path.read_text(encoding="utf-8", errors="replace")


def _cmd_audit(args) -> int:
    p = Path(args.path).resolve()
    if not p.exists():
        raise SystemExit(f"factwash: no such path: {p}")
    findings = []
    for label, text in _iter_memories(p):
        if not text or len(text.encode("utf-8", "ignore")) > MAX_FILE_BYTES:
            continue
        for flag in surface_scan(text):
            findings.append((label, flag))
    if args.json:
        print(json.dumps({"surface_scan": True,
                          "findings": [{"where": label, "name": f.name, "evidence": f.evidence,
                                        "citation": f.citation} for label, f in findings]}, indent=2))
        return 0
    print(DISCLAIMER)
    print()
    if not findings:
        print("no surface findings")
        return 0
    for label, f in findings:
        print(f"  {label:<24} {f.name}: {f.evidence}")
    print(f"\n{len(findings)} surface finding(s). To run the real gate, re-check writes "
          f"against their sources: factwash check --source ... --memory ...")
    return 0


def _cmd_bench(args) -> int:
    from .bench import load_pairs, mem0_adapter, run_adapter, score_pairs
    if bool(args.pairs) == bool(args.adapter):
        raise SystemExit("factwash bench: give a pairs JSONL, or --adapter with --sources (not both)")
    if args.adapter:
        if not args.sources:
            raise SystemExit("factwash bench: --adapter needs --sources")
        src_path = Path(args.sources).resolve()
        if not src_path.is_file():
            raise SystemExit(f"factwash: not a file: {src_path}")
        if src_path.suffix == ".jsonl":
            sources = [json.loads(l)["source"] for l in
                       src_path.read_text(encoding="utf-8", errors="replace").splitlines()
                       if l.strip()]
        else:
            sources = [l for l in
                       src_path.read_text(encoding="utf-8", errors="replace").splitlines()
                       if l.strip()]
        pairs, errors = run_adapter(mem0_adapter(), sources)
        result = score_pairs(pairs, stimuli_id=args.stimuli_id, adapter_errors=errors)
    else:
        p = Path(args.pairs).resolve()
        if not p.is_file():
            raise SystemExit(f"factwash: not a file: {p}")
        if p.stat().st_size > MAX_FILE_BYTES:
            raise SystemExit(f"factwash: {p.name} exceeds the {MAX_FILE_BYTES // (1024 * 1024)}MB cap")
        result = score_pairs(load_pairs(p), stimuli_id=args.stimuli_id)
    print(json.dumps(result.to_dict(), indent=2) if args.json else result.render())
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="factwash",
                                     description="A write-time linter for AI memory. Deterministic, judge-free.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="gate one candidate memory against its source")
    c.add_argument("--source", required=True, help="file with the session/source context")
    c.add_argument("--memory", required=True, help="file with the candidate memory")
    c.add_argument("--json", action="store_true")
    c.add_argument("--fix", action="store_true",
                   help="rewrite failing memories with the paper prompts (needs anthropic + API key)")
    c.set_defaults(fn=_cmd_check)

    a = sub.add_parser("audit", help="SURFACE SCAN of stored memories (weaker than the gate; labeled)")
    a.add_argument("path", help="directory of .txt/.md files, a .jsonl dump, or a single file")
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=_cmd_audit)

    b = sub.add_parser("bench",
                       help="score a memory system's writes: laundering rate (lower bound)")
    b.add_argument("pairs", nargs="?",
                   help="JSONL of {source, memory} pairs the system produced")
    b.add_argument("--adapter", choices=["mem0"],
                   help="drive a live system instead (network + cost; mem0 needs its own config)")
    b.add_argument("--sources",
                   help="with --adapter: JSONL of {source} rows or a plain text file, one source per line")
    b.add_argument("--stimuli-id", default=None,
                   help="name of the stimulus set, stamped on the report (scores are only comparable within one)")
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=_cmd_bench)

    args = parser.parse_args(argv)
    return args.fn(args)


def console():  # console_scripts entry point
    sys.exit(main())


if __name__ == "__main__":
    console()
