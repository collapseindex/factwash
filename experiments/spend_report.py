"""What the two-cell experiments actually cost.

Reads measured spend from each run's summary. Two runs predate the fix that made a
capped run still write its summary, so their spend is recovered from the run log instead
and labelled as such rather than quietly omitted, which would understate the total by
more than half.

All figures are NOMINAL: spend is computed from measured token counts at rates passed
into the harness, and models with no rate on file are priced at a deliberately expensive
fallback so the cap fails safe. Nominal >= real by construction.
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    rows, total = [], 0.0
    for f in sorted(glob.glob(str(ROOT / "data/results/*twocellpress*_summary.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        usd = (d.get("telemetry") or {}).get("usd") or 0.0
        if usd:
            name = Path(f).stem.split("twocellpress_")[1].rsplit("_summary", 1)[0]
            rows.append((name, usd, "summary", d.get("stopped_early")))
            total += usd

    # A log is counted only if score() never ran for it, i.e. it has no "summary:" line.
    # An earlier version deduped by fuzzy name match and silently swallowed the second
    # Sonnet 5 run, understating the total by four dollars. Exact rule, not a heuristic.
    no_rate = 0
    for log in sorted(glob.glob(str(ROOT / "data/raw/_run_*.log"))):
        txt = Path(log).read_text(encoding="utf-8", errors="ignore")
        stem = Path(log).stem.replace("_run_", "")
        if "summary:" in txt:
            continue
        hits = (re.findall(r"measured spend \$([0-9.]+)", txt)
                or re.findall(r"\$([0-9.]+) of \$", txt))
        if hits:
            v = float(hits[-1])
            rows.append((stem, v, "from log (capped, pre-fix)", "yes"))
            total += v
        else:
            no_rate += 1
    if no_rate:
        print(f"note: {no_rate} run log(s) carry no spend figure and are NOT in the "
              f"total\n")

    for name, usd, src, stopped in rows:
        flag = "  [stopped early]" if stopped else ""
        print(f"{name[:44]:<46} ${usd:7.4f}  {src}{flag}")
    print("-" * 78)
    print(f"{'NOMINAL TOTAL':<46} ${total:7.2f}")
    print("\nnominal >= real: unknown-rate models are priced at the expensive fallback")
    print("EXCLUDES the first pressure sweep (seeds 0 and 200), which ran before the "
          "harness\nmetered spend at all; that spend is unrecoverable, estimated at "
          "roughly $1.5 from\nits token counts, and is not included above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
