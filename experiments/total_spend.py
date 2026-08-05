"""Total metered API spend across every experiment in this repository.

Sums the `usd` field of every run summary, plus runs that stopped at a spend cap before
their summary was written (those are recovered from the run log and labelled).

All figures are NOMINAL: computed from measured token counts at rates passed into the
harness, with models that have no rate on file priced at a deliberately expensive
fallback so the cap fails safe. Nominal >= real by construction.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    rows, total = [], 0.0

    for f in sorted(glob.glob(str(ROOT / "data/results/*_summary.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        usd = (d.get("telemetry") or {}).get("usd")
        if not usd:
            cost = d.get("cost") or {}
            usd = cost.get("arm_B_usd") or cost.get("usd")
        if isinstance(usd, (int, float)) and usd:
            rows.append((os.path.basename(f).replace("_summary.json", ""), usd, ""))
            total += usd

    # runs killed by the spend cap before the summary-on-exit fix
    for lg in sorted(glob.glob(str(ROOT / "data/raw/_run_*.log"))):
        txt = Path(lg).read_text(encoding="utf-8", errors="ignore")
        if "summary:" in txt:
            continue
        hits = (re.findall(r"measured spend \$([0-9.]+)", txt)
                or re.findall(r"\$([0-9.]+) of \$", txt))
        if hits:
            v = float(hits[-1])
            rows.append((os.path.basename(lg), v, " (capped, from log)"))
            total += v

    rows.sort(key=lambda r: -r[1])
    for name, usd, note in rows[:12]:
        print(f"  {name[:54]:<56} ${usd:7.4f}{note}")
    if len(rows) > 12:
        rest = sum(r[1] for r in rows[12:])
        print(f"  {'... ' + str(len(rows) - 12) + ' smaller runs':<56} ${rest:7.4f}")
    print("-" * 74)
    print(f"  {'TOTAL, metered':<56} ${total:7.2f}")
    print("\n  Excludes the first two-cell pressure sweeps, which ran before the harness")
    print("  metered spend at all; roughly $1.5 by their token counts, unrecoverable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
