"""The .env loader touches credentials, so it gets tests. No real secrets here."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments"))

from live_run import load_dotenv  # noqa: E402


def test_loads_names_and_values(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('FAKE_TOKEN=abc123\nQUOTED="q-value"\nSINGLE=\'s-value\'\n', encoding="utf-8")
    for k in ("FAKE_TOKEN", "QUOTED", "SINGLE"):
        monkeypatch.delenv(k, raising=False)

    loaded = load_dotenv(env)
    assert sorted(loaded) == ["FAKE_TOKEN", "QUOTED", "SINGLE"]
    assert os.environ["FAKE_TOKEN"] == "abc123"
    assert os.environ["QUOTED"] == "q-value"      # surrounding quotes stripped
    assert os.environ["SINGLE"] == "s-value"


def test_exported_env_wins_over_the_file(tmp_path, monkeypatch):
    """A shell export must override .env, so you can point a run elsewhere without editing it."""
    env = tmp_path / ".env"
    env.write_text("FAKE_TOKEN=from-file\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_TOKEN", "from-shell")

    assert load_dotenv(env) == []                  # nothing overwritten
    assert os.environ["FAKE_TOKEN"] == "from-shell"


def test_comments_blanks_and_junk_lines_are_skipped(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\nNOT_AN_ASSIGNMENT\n=novalue\nGOOD=yes\n", encoding="utf-8")
    monkeypatch.delenv("GOOD", raising=False)
    assert load_dotenv(env) == ["GOOD"]


def test_missing_file_is_not_an_error(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") == []


def test_value_containing_equals_is_preserved(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PADDED=abc==\n", encoding="utf-8")
    monkeypatch.delenv("PADDED", raising=False)
    load_dotenv(env)
    assert os.environ["PADDED"] == "abc=="        # split on the FIRST = only
