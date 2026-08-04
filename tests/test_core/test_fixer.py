"""Fix mode with an injected chat callable (no API, no network)."""
import pytest

from factwash.fixer import fix

SRC_55 = "User: The line items are 12, 18, and 25.\nAssistant: The total comes to $55."


def test_passing_memory_is_returned_unchanged():
    result = fix("I prefer dark mode in all my editors.", "User prefers dark mode.",
                 _chat=lambda s, u: pytest.fail("must not call the LLM on a passing memory"))
    assert result.prompt_used is None
    assert result.verdict == "PASS"


def test_brittle_uses_source_first_and_regates():
    result = fix(SRC_55, "The total was $55.",
                 _chat=lambda s, u: "Total $55 from line items 12, 18, and 25.")
    assert result.prompt_used == "source_first"
    assert result.verdict == "PASS"


def test_dehedged_uses_hedgekeep():
    result = fix("Rumor has it Alice now has admin access.", "Alice's clearance: admin.",
                 _chat=lambda s, u: "Rumor (unconfirmed): Alice may have been promoted to admin.")
    assert result.prompt_used == "hedgekeep"
    assert result.verdict in ("PASS", "PASS_WITH_FLAGS")


def test_failing_rewrite_is_rejected():
    result = fix(SRC_55, "The total was $55.", _chat=lambda s, u: "The grand total was $55.")
    assert result.verdict == "REJECT"


def test_missing_anthropic_gives_actionable_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def block_anthropic(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_anthropic)
    with pytest.raises(RuntimeError, match="factwash\\[fix\\]"):
        fix(SRC_55, "The total was $55.")
