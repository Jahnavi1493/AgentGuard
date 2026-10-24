import os

from agentguard.checkpoint import Checkpoint
from agentguard.tools import counters


def reset_env(tmp_path):
    counters.reset_all()
    sandbox = tmp_path / "agentguard_phase2"
    if sandbox.exists():
        import shutil
        shutil.rmtree(sandbox)
    return sandbox


def test_blocked_call_is_not_executed_and_file_stays_present(tmp_path):
    sandbox = reset_env(tmp_path)
    checkpoint = Checkpoint(sandbox_root=str(sandbox))
    file_path = sandbox / "finance" / "payroll.xlsx"
    result = checkpoint.run_tool({
        "tool": "file.delete",
        "params": {"path": str(file_path)},
        "task": "Delete payroll",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "req-1",
    }, mode="protected")

    assert result["decision"] == "BLOCK"
    assert counters.get_count("file.delete") == 0
    assert os.path.exists(file_path)


def test_allowed_call_executes_once(tmp_path):
    sandbox = reset_env(tmp_path)
    checkpoint = Checkpoint(sandbox_root=str(sandbox))
    file_path = sandbox / "notes" / "q3.txt"
    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(file_path)},
        "task": "Read notes",
        "timestamp": "2024-01-01T00:00:01Z",
        "id": "req-2",
    }, mode="protected")

    assert result["decision"] == "ALLOW"
    assert counters.get_count("file.read") == 1


def test_symlink_escape_is_blocked(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    real_file = sandbox / "safe.txt"
    real_file.write_text("safe", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link_path = sandbox / "escape.txt"
    try:
        os.symlink(outside, link_path)
    except OSError:
        return

    checkpoint = Checkpoint(sandbox_root=str(sandbox))
    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(link_path)},
        "task": "Read symlinked file",
        "timestamp": "2024-01-01T00:00:02Z",
        "id": "req-3",
    }, mode="protected")

    assert result["decision"] == "BLOCK"
    assert result["rule_id"] == "VALIDATION"
