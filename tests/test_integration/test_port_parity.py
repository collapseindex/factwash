"""The browser demo's JS gate must agree with the Python gate, or the page is a lookalike.

The demo claims it runs "the actual gate". That claim decays the moment a check changes in
Python and not in demo/gate.js, and the failure would be invisible on the page -- it would
just render a confident wrong verdict. This test re-derives the comparison every run.

Requires node; skipped cleanly when it is absent.
"""
from __future__ import annotations

import glob
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import factwash

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


# Behaviours the fixture corpora do not exercise, so parity on them would otherwise go
# untested and the port could diverge silently. Supersession is the live example: it
# shipped in Python first and this test stayed green, because not one of the 165 fixture
# pairs contains a retracted denial.
EDGE_CASES = [
    {"tag": "supersede:retracted",
     "src": "assistant: I don't recall Alice having admin on the prod cluster. "
            "assistant: Checking the audit log, Alice does have admin on the prod cluster.",
     "mem": "Alice has admin on the prod cluster."},
    {"tag": "supersede:repeated_denial",
     "src": "assistant: Alice does not have admin on the prod cluster. "
            "assistant: Confirmed again, Alice does not have admin on the prod cluster.",
     "mem": "Alice has admin on the prod cluster."},
    {"tag": "supersede:other_topic",
     "src": "assistant: Alice does not have admin on the prod cluster. "
            "assistant: Bob has admin on the staging cluster.",
     "mem": "Alice has admin on the prod cluster."},
    {"tag": "window:hedge_next_door",
     "src": "User: Alice has admin on the prod cluster. Not sure though, I should double-check.",
     "mem": "Alice has admin on the prod cluster."},
    {"tag": "cond:interrogative_if",
     "src": "User: We tested if the nightly job still runs, and it does.",
     "mem": "The nightly job still runs."},
]


def _pairs() -> list[dict]:
    """Every (source, memory) pair we have: fixtures, plus real extractions and rewrites."""
    cases = list(EDGE_CASES)
    for name in ("planted_corpus", "clean_corpus"):
        path = ROOT / "tests" / "fixtures" / f"{name}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                cases.append({"tag": rec["id"], "src": rec["source"], "mem": rec["memory"]})
    for path in glob.glob(str(ROOT / "data" / "raw" / "*laundering*.jsonl")):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("error"):
                continue
            if rec.get("memory"):
                cases.append({"tag": rec["id"] + ":ext", "src": rec["source"], "mem": rec["memory"]})
            if rec.get("rewrite"):
                cases.append({"tag": rec["id"] + ":fix", "src": rec["source"], "mem": rec["rewrite"]})
    return cases


def test_js_port_agrees_with_python_on_every_pair(tmp_path):
    cases = _pairs()
    assert len(cases) >= 25, "expected at least the shipped fixtures"

    for c in cases:
        report = factwash.check(c["src"], c["mem"])
        c["verdict"] = report.verdict
        c["flags"] = sorted({f.name for f in report.flags if f.severity in ("fail", "warn")})

    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    script = tmp_path / "verify.js"
    script.write_text(f"""
const gate = require({json.dumps(str(DEMO / "gate.js"))});
const cases = require({json.dumps(str(expected))});
const bad = [];
for (const c of cases) {{
  const r = gate.check(c.src, c.mem);
  const flags = [...new Set(r.flags
      .filter(f => f.severity === "fail" || f.severity === "warn")
      .map(f => f.name))].sort();
  if (r.verdict !== c.verdict || JSON.stringify(flags) !== JSON.stringify(c.flags))
    bad.push({{tag: c.tag, py: [c.verdict, c.flags], js: [r.verdict, flags]}});
}}
console.log(JSON.stringify({{compared: cases.length, disagreements: bad}}));
""", encoding="utf-8")

    proc = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    assert result["disagreements"] == [], (
        f"demo/gate.js has drifted from the Python gate on "
        f"{len(result['disagreements'])} of {result['compared']} pairs: "
        f"{result['disagreements'][:5]}"
    )
    assert result["compared"] == len(cases)


def test_shipped_page_contains_the_verified_gate_verbatim():
    """index.html is generated; a hand-edit there would escape the parity test above."""
    gate = (DEMO / "gate.js").read_text(encoding="utf-8")
    page = (DEMO / "index.html").read_text(encoding="utf-8")
    assert gate.strip() in page, "demo/index.html is stale -- re-run: python demo/build.py"
