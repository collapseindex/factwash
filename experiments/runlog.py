"""Run ledger for paid experiments: stream to disk, resume, cap the spend.

Built to the rule that came out of losing ~$8 to an interrupted grok run: a paid
run must flush every item to disk as it completes, must be resumable from that
file, and must refuse to start a call that would blow the budget. Nothing here
buffers results in memory until the end.

Layout follows the data-control convention:

    data/raw/YYYYMMDD_HHMMSS_<operation>_<model>_<params>_s<seed>.jsonl   per-item records
    data/raw/YYYYMMDD_HHMMSS_..._manifest.json                            run metadata
    data/results/YYYYMMDD_HHMMSS_..._summary.json                         aggregates
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

# Anthropic list prices, USD per million tokens (skill-sourced, 2026-08-02).
# Sonnet 5 carries an introductory rate through 2026-08-31; both are recorded so
# a run's cost can be re-derived later from the rate actually applied.
SONNET_5_INTRO_ENDS = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)

PRICES_USD_PER_MTOK = {
    "claude-opus-5": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-5-intro": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


class BudgetExceeded(RuntimeError):
    """Raised before a call that would exceed the cap. The run stops; nothing is lost."""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def slug(text: str) -> str:
    """Filename-safe token: keeps the convention parseable by splitting on '_'."""
    return re.sub(r"[^A-Za-z0-9.-]+", "-", str(text)).strip("-") or "na"


def rates_for(model: str, when: datetime | None = None) -> tuple[float, float, str]:
    """Return (input_rate, output_rate, rate_label) per million tokens.

    Unknown models (OpenRouter, self-hosted) return (0, 0, 'unpriced'); their raw
    usage is still recorded verbatim so cost can be computed after the fact.
    """
    when = when or datetime.now(timezone.utc)
    if model == "claude-sonnet-5" and when <= SONNET_5_INTRO_ENDS:
        return (*PRICES_USD_PER_MTOK["claude-sonnet-5-intro"], "claude-sonnet-5-intro")
    if model in PRICES_USD_PER_MTOK:
        return (*PRICES_USD_PER_MTOK[model], model)
    return (0.0, 0.0, "unpriced")


@dataclass
class Budget:
    """A hard ceiling in USD. Checked before each call, updated from real usage."""

    cap_usd: float
    spent_usd: float = 0.0
    calls: int = 0

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def check(self, estimate_usd: float) -> None:
        """Refuse a call whose worst-case cost would breach the cap."""
        if self.spent_usd + estimate_usd > self.cap_usd:
            raise BudgetExceeded(
                f"next call (est ${estimate_usd:.4f}) would exceed the ${self.cap_usd:.2f} cap; "
                f"spent ${self.spent_usd:.4f} over {self.calls} call(s)"
            )

    def record(self, actual_usd: float) -> None:
        self.spent_usd += actual_usd
        self.calls += 1


@dataclass
class Cost:
    """Cost of one API call, with the raw usage payload kept verbatim.

    `raw` is preserved because provider usage fields differ and some hide tokens
    from the obvious counter (grok bills reasoning tokens that never appear in
    completion_tokens). Storing the payload means a wrong price table today is
    still recoverable arithmetic tomorrow.
    """

    input_tokens: int
    output_tokens: int
    usd: float
    rate_label: str
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "usd": round(self.usd, 6), "rate_label": self.rate_label, "raw": self.raw}


# Cache multipliers on the input rate (Anthropic): a write costs more than a fresh
# token, a read costs a fraction of one. Ignoring these would understate spend, and the
# budget cap is only as honest as the number it is checked against.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def price_call(model: str, input_tokens: int, output_tokens: int, raw: dict | None = None) -> Cost:
    """Price one call. `input_tokens` is the UNCACHED remainder when caching is on;
    cache creation and read tokens are billed separately and are read from `raw`."""
    rate_in, rate_out, label = rates_for(model)
    raw = raw or {}
    cache_write = int(raw.get("cache_creation_input_tokens") or 0)
    cache_read = int(raw.get("cache_read_input_tokens") or 0)
    usd = (
        input_tokens * rate_in
        + cache_write * rate_in * CACHE_WRITE_MULTIPLIER
        + cache_read * rate_in * CACHE_READ_MULTIPLIER
        + output_tokens * rate_out
    ) / 1_000_000
    # Report the full prompt size, not just the uncached slice, so token counts in the
    # ledger stay comparable between cached and uncached runs.
    return Cost(input_tokens + cache_write + cache_read, output_tokens, usd, label, raw)


class RunLog:
    """Append-only JSONL ledger. Every record is flushed and fsynced on write.

    Resumability is by item id: reopening an existing run reads the ids already on
    disk, and `is_done()` lets the driver skip them without re-paying.
    """

    def __init__(self, operation: str, model: str, params: str, seed: int,
                 data_dir: Path | None = None, resume_path: Path | None = None):
        base = Path(data_dir) if data_dir else DATA_DIR
        (base / "raw").mkdir(parents=True, exist_ok=True)
        (base / "results").mkdir(parents=True, exist_ok=True)
        self.base = base
        self.resumed = resume_path is not None

        if resume_path is not None:
            self.path = Path(resume_path).resolve()
            if not self.path.is_file():
                raise SystemExit(f"cannot resume: no such run file: {self.path}")
        else:
            name = (f"{utc_stamp()}_{slug(operation)}_{slug(model)}_{slug(params)}"
                    f"_s{int(seed)}.jsonl")
            self.path = base / "raw" / name

        self.manifest_path = self.path.with_name(self.path.stem + "_manifest.json")
        self._done: set[str] = set()
        self.prior_spend_usd = 0.0
        if self.path.exists():
            self._load_existing()
        self._fh = self.path.open("a", encoding="utf-8")

    def _load_existing(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn final line from a hard kill: skip, don't crash the resume
            if rec.get("id"):
                self._done.add(rec["id"])
            self.prior_spend_usd += float(rec.get("cost_usd") or 0.0)

    def is_done(self, item_id: str) -> bool:
        return item_id in self._done

    @property
    def done_count(self) -> int:
        return len(self._done)

    def append(self, record: dict) -> None:
        """Write one record durably. Costs a syscall per item; that is the point."""
        record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        if record.get("id"):
            self._done.add(record["id"])

    def write_manifest(self, meta: dict) -> None:
        meta = {**meta, "run_file": self.path.name, "written_at": datetime.now(timezone.utc).isoformat()}
        self.manifest_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def write_summary(self, summary: dict) -> Path:
        out = self.base / "results" / (self.path.stem + "_summary.json")
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return out

    def records(self) -> list[dict]:
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()

    def __enter__(self) -> "RunLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
