import threading

import pytest

from agentguard.checkpoint import Checkpoint
from agentguard.tools import counters
from agentguard.tools._db_tools import query_db, reset_db
from agentguard.tools.counters import wrap_raw_tool


def test_reset_db_is_thread_safe():
    reset_db()
    seen = {}

    def worker():
        try:
            reset_db()
            seen["rows"] = query_db("SELECT 1")
        except Exception as exc:  # pragma: no cover - assertion path for thread regression
            seen["error"] = repr(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert "error" not in seen
    assert seen["rows"] == [(1,)]


def test_review_request_is_pending_until_approved(tmp_path):
    counters.reset_all()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_review"), audit_log_path=str(tmp_path / "agentguard_review.jsonl"))
    result = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-1",
    }, mode="protected")

    assert result["decision"] == "REVIEW"
    assert result["outcome"] == "pending"
    assert counters.get_count("email.send") == 0

    approval = checkpoint.approve("review-1", "teacher")
    assert approval["status"] == "approved"
    assert counters.get_count("email.send") == 1

    second = checkpoint.approve("review-1", "teacher")
    assert second["status"] == "approved"
    assert counters.get_count("email.send") == 1


def test_deny_and_timeout_never_execute(tmp_path):
    counters.reset_all()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_review_2"), audit_log_path=str(tmp_path / "agentguard_review_2.jsonl"))
    result = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-2",
    }, mode="protected")
    assert result["decision"] == "REVIEW"

    deny_result = checkpoint.deny("review-2")
    assert deny_result["status"] == "denied"
    assert counters.get_count("email.send") == 0

    result2 = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:01:00Z",
        "id": "review-3",
    }, mode="protected")
    item = checkpoint.review_queue.get(result2["request_id"])
    item.created_at = 0
    item.timed_out()
    assert item.status == "timed_out"
    assert counters.get_count("email.send") == 0


def test_double_approve_runs_once(tmp_path):
    counters.reset_all()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_double_approve"), audit_log_path=str(tmp_path / "agentguard_double_approve.jsonl"))
    result = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-double-1",
    }, mode="protected")
    first = checkpoint.approve(result["request_id"], "teacher")
    second = checkpoint.approve(result["request_id"], "teacher")
    assert first["status"] == "approved"
    assert second["status"] == "approved"
    assert counters.get_count("email.send") == 1


def test_raw_tool_counter_counts_calls_even_when_the_tool_raises():
    counters.reset_all()

    def boom(path: str):
        raise RuntimeError(f"hit {path}")

    wrapped = wrap_raw_tool("file.delete", boom)
    with pytest.raises(RuntimeError):
        wrapped("finance/payroll.xlsx")
    assert counters.get_count("file.delete") == 1
