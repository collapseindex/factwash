"""CLI smoke tests: exit codes are the contract (0 pass, 1 rewrite, 2 reject)."""
import json

from factwash.cli import main


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_check_reject_exits_2(tmp_path):
    src = _write(tmp_path, "src.txt",
                 "User: The line items are 12, 18, and 25.\nAssistant: The total comes to $55.")
    mem = _write(tmp_path, "mem.txt", "The total was $55.")
    assert main(["check", "--source", src, "--memory", mem]) == 2


def test_check_rewrite_exits_1(tmp_path):
    src = _write(tmp_path, "src.txt", "User: Rumor has it Alice now has admin access.")
    mem = _write(tmp_path, "mem.txt", "Alice's clearance: admin.")
    assert main(["check", "--source", src, "--memory", mem]) == 1


def test_check_pass_exits_0_and_json_is_valid(tmp_path, capsys):
    src = _write(tmp_path, "src.txt", "User: I prefer dark mode in all my editors.")
    mem = _write(tmp_path, "mem.txt", "User prefers dark mode.")
    assert main(["check", "--source", src, "--memory", mem, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "PASS"


def test_audit_is_labeled_surface_scan(tmp_path, capsys):
    _write(tmp_path, "note1.txt", "The total was $55.")
    _write(tmp_path, "note2.txt", "Deploy is probably Friday, per discussion notes.")
    assert main(["audit", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SURFACE SCAN" in out and "NOT the write-time gate" in out
    assert "AGGREGATE_WITHOUT_BASIS" in out


def test_check_missing_file_is_a_clean_error(tmp_path):
    try:
        main(["check", "--source", str(tmp_path / "nope.txt"), "--memory", str(tmp_path / "nope2.txt")])
    except SystemExit as e:
        assert "not a file" in str(e.code)
    else:
        raise AssertionError("expected SystemExit")
