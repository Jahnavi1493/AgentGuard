import os

from agentguard.checkpoint import Checkpoint
from agentguard.tools import counters
import agentguard.tools as tools_pkg


def test_guarded_tools_hide_raw_functions(tmp_path):
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_bypass"))
    guarded = checkpoint.get_guarded_tools()

    assert set(guarded) == {"file.read", "file.delete", "email.send", "db.query"}
    assert not hasattr(tools_pkg, "read_file")
    assert not hasattr(tools_pkg, "delete_file")
    assert not hasattr(tools_pkg, "query_db")
    assert not hasattr(tools_pkg, "send_email")
    assert all(name in {"file.read", "file.delete", "email.send", "db.query"} for name in guarded)


def test_mock_agent_cannot_reach_raw_tool_objects(tmp_path):
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_bypass"))
    guarded = checkpoint.get_guarded_tools()

    assert not any(callable(value) and getattr(value, "__module__", "").startswith("agentguard.tools._") for value in guarded.values())
    assert all(getattr(value, "__module__", "") != "agentguard.tools._file_tools" for value in guarded.values())


def test_counters_reset_and_blocked_calls_stay_zero(tmp_path):
    counters.reset_all()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_bypass"))
    future_tool = checkpoint.get_guarded_tools()["file.delete"]
    assert callable(future_tool)
    assert counters.get_count("file.delete") == 0
