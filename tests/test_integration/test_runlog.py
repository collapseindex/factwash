"""Tests for the paid-run ledger. These are the ones that protect real money.

Each test breaks something on purpose: kill the process mid-run, corrupt the last
line, blow the cap. A ledger that has only ever been observed succeeding is not
known to work.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments"))

from runlog import (Budget, BudgetExceeded, RunLog, price_call,  # noqa: E402
                    rates_for, PRICES_USD_PER_MTOK)
from datetime import datetime, timezone  # noqa: E402


# --- budget cap -----------------------------------------------------------------------
def test_budget_refuses_the_call_that_would_breach_the_cap():
    b = Budget(cap_usd=0.10)
    b.record(0.09)
    with pytest.raises(BudgetExceeded):
        b.check(0.02)          # 0.09 + 0.02 > 0.10 -> refused BEFORE spending
    b.check(0.005)             # still room for a smaller call
    assert b.calls == 1


def test_budget_counts_prior_spend_on_resume(tmp_path):
    log = RunLog("op", "m", "p", 0, data_dir=tmp_path)
    log.append({"id": "a", "cost_usd": 0.04})
    log.append({"id": "b", "cost_usd": 0.03})
    log.close()

    resumed = RunLog("op", "m", "p", 0, data_dir=tmp_path, resume_path=log.path)
    assert resumed.prior_spend_usd == pytest.approx(0.07)
    b = Budget(cap_usd=0.10, spent_usd=resumed.prior_spend_usd)
    with pytest.raises(BudgetExceeded):
        b.check(0.05)          # the cap spans the whole run, not just this session
    resumed.close()


# --- durability -----------------------------------------------------------------------
def test_every_record_is_on_disk_before_the_next_one_starts(tmp_path):
    """The anti-data-loss property: read the file from a *separate* handle mid-run."""
    log = RunLog("op", "m", "p", 0, data_dir=tmp_path)
    log.append({"id": "first", "cost_usd": 0.01})
    on_disk = [json.loads(l) for l in log.path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [r["id"] for r in on_disk] == ["first"]   # durable before item 2 is attempted
    log.append({"id": "second", "cost_usd": 0.01})
    log.close()
    assert len(log.records()) == 2


def test_resume_skips_completed_items_so_they_are_not_paid_for_twice(tmp_path):
    log = RunLog("op", "m", "p", 0, data_dir=tmp_path)
    for i in range(3):
        log.append({"id": f"item{i}", "cost_usd": 0.01})
    log.close()

    resumed = RunLog("op", "m", "p", 0, data_dir=tmp_path, resume_path=log.path)
    assert resumed.done_count == 3
    assert all(resumed.is_done(f"item{i}") for i in range(3))
    assert not resumed.is_done("item3")
    resumed.close()


def test_torn_final_line_from_a_hard_kill_does_not_break_resume(tmp_path):
    """SIGKILL mid-write leaves a partial line. Resume must salvage the rest."""
    log = RunLog("op", "m", "p", 0, data_dir=tmp_path)
    log.append({"id": "good1", "cost_usd": 0.02})
    log.append({"id": "good2", "cost_usd": 0.02})
    log.close()
    with log.path.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "torn", "cost_us')   # process died here

    resumed = RunLog("op", "m", "p", 0, data_dir=tmp_path, resume_path=log.path)
    assert resumed.done_count == 2
    assert resumed.prior_spend_usd == pytest.approx(0.04)
    assert not resumed.is_done("torn")        # unconfirmed item is retried, not skipped
    resumed.close()


def test_resume_on_a_missing_file_is_a_clean_error(tmp_path):
    with pytest.raises(SystemExit):
        RunLog("op", "m", "p", 0, data_dir=tmp_path, resume_path=tmp_path / "nope.jsonl")


# --- lineage & pricing ----------------------------------------------------------------
def test_filename_carries_the_full_lineage(tmp_path):
    log = RunLog("laundering", "claude-haiku-4-5", "mc-fix", 42, data_dir=tmp_path)
    name = log.path.name
    assert name.endswith("_s42.jsonl")
    assert "laundering" in name and "claude-haiku-4-5" in name and "mc-fix" in name
    assert name[:8].isdigit()                  # YYYYMMDD prefix sorts chronologically
    log.close()


def test_sonnet_intro_rate_applies_now_and_lapses_after_august(tmp_path):
    during = datetime(2026, 8, 2, tzinfo=timezone.utc)
    after = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert rates_for("claude-sonnet-5", during) == (2.00, 10.00, "claude-sonnet-5-intro")
    assert rates_for("claude-sonnet-5", after) == (3.00, 15.00, "claude-sonnet-5")


def test_unknown_model_is_unpriced_rather_than_silently_wrong():
    cost = price_call("some/openrouter-model", 1000, 500, {"usage": {"prompt_tokens": 1000}})
    assert cost.usd == 0.0
    assert cost.rate_label == "unpriced"
    assert cost.raw["usage"]["prompt_tokens"] == 1000   # recoverable later


def test_priced_call_matches_the_published_rate():
    cost = price_call("claude-haiku-4-5", 1_000_000, 1_000_000)
    rate_in, rate_out = PRICES_USD_PER_MTOK["claude-haiku-4-5"]
    assert cost.usd == pytest.approx(rate_in + rate_out)


def test_summary_and_manifest_land_in_the_right_folders(tmp_path):
    log = RunLog("op", "m", "p", 0, data_dir=tmp_path)
    log.write_manifest({"model": "m"})
    out = log.write_summary({"items_scored": 0})
    log.close()
    assert log.manifest_path.parent.name == "raw"
    assert out.parent.name == "results"
    assert json.loads(log.manifest_path.read_text())["run_file"] == log.path.name


# --- cache-aware pricing (added after a cached run understated spend) -----------------
def test_cache_read_is_cheaper_than_uncached_and_write_is_dearer():
    """With caching on, usage.input_tokens is only the uncached remainder.

    Pricing only that field would understate spend, and the budget cap is only as
    honest as the number it is checked against.
    """
    uncached = price_call("claude-sonnet-5", 12_100, 50)
    written = price_call("claude-sonnet-5", 100, 50,
                         {"cache_creation_input_tokens": 12_000})
    read = price_call("claude-sonnet-5", 100, 50,
                      {"cache_read_input_tokens": 12_000})
    assert written.usd > uncached.usd > read.usd
    assert read.usd < uncached.usd / 5          # reads are ~0.1x on the input rate


def test_full_prompt_size_is_reported_even_when_cached():
    """Token counts must stay comparable between cached and uncached runs."""
    cost = price_call("claude-sonnet-5", 100, 50, {"cache_read_input_tokens": 12_000})
    assert cost.input_tokens == 12_100
