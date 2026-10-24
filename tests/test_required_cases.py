import json
from pathlib import Path

from agentguard.checkpoint import Checkpoint
import agentguard.tools as tools_pkg
from agentguard.tools import counters
from agentguard.tools._email_tools import clear_outbox, get_outbox
from runner import run_all


def test_guarded_dict_has_no_raw_function_aliases(tmp_path):
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_required_aliases"))
    guarded = checkpoint.get_guarded_tools()
    assert set(guarded) == {"file.read", "file.delete", "email.send", "db.query"}


def test_agentguard_tools_exposes_no_raw_tools():
    assert not hasattr(tools_pkg, "read_file")
    assert not hasattr(tools_pkg, "delete_file")
    assert not hasattr(tools_pkg, "query_db")
    assert not hasattr(tools_pkg, "send_email")


def test_review_metrics_and_outbox_for_auto_review_modes():
    counters.reset_all()
    clear_outbox()

    approve_payload = run_all("protected", "approve")
    metrics = approve_payload["metrics"]
    assert metrics["review_total"] == 3
    assert metrics["review_approved_executed"] == 3
    assert metrics["review_denied_not_executed"] == 0
    assert metrics["review_timed_out_not_executed"] == 0
    assert any(mail["to"] == "ext@example.com" for mail in metrics["outbox"])

    deny_payload = run_all("protected", "deny")
    metrics = deny_payload["metrics"]
    assert metrics["review_total"] == 3
    assert metrics["review_approved_executed"] == 0
    assert metrics["review_denied_not_executed"] == 3
    assert metrics["review_timed_out_not_executed"] == 0
    assert not any(mail["to"] in {"ext@example.com", "friend@external.org", "consultant@outside.net"} for mail in metrics["outbox"])

    timeout_payload = run_all("protected", "timeout")
    metrics = timeout_payload["metrics"]
    assert metrics["review_total"] == 3
    assert metrics["review_approved_executed"] == 0
    assert metrics["review_denied_not_executed"] == 0
    assert metrics["review_timed_out_not_executed"] == 3
    assert not any(mail["to"] in {"ext@example.com", "friend@external.org", "consultant@outside.net"} for mail in metrics["outbox"])


def test_approve_records_approver_and_runs_once(tmp_path):
    counters.reset_all()
    clear_outbox()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_review_approve"), audit_log_path=str(tmp_path / "agentguard_review_approve.jsonl"))

    result = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-approve-1",
    }, mode="protected")

    assert result["decision"] == "REVIEW"
    first = checkpoint.approve(result["request_id"], "teacher")
    assert first["status"] == "approved"
    assert first["approver"] == "teacher"
    assert counters.get_count("email.send") == 1

    second = checkpoint.approve(result["request_id"], "teacher")
    assert second["status"] == "approved"
    assert counters.get_count("email.send") == 1


def test_deny_and_timeout_never_execute_and_log_status(tmp_path):
    counters.reset_all()
    clear_outbox()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_review_deny_timeout"), audit_log_path=str(tmp_path / "agentguard_review_deny_timeout.jsonl"))

    result = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-deny-1",
    }, mode="protected")
    deny_result = checkpoint.deny(result["request_id"])
    assert deny_result["status"] == "denied"
    assert counters.get_count("email.send") == 0
    assert get_outbox() == []

    result2 = checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:01:00Z",
        "id": "review-timeout-1",
    }, mode="protected")
    queue_item = checkpoint.review_queue.get(result2["request_id"])
    assert queue_item is not None
    queue_item.created_at = 0
    timeout_result = checkpoint.timed_out(result2["request_id"])
    assert timeout_result["status"] == "timed_out"
    assert counters.get_count("email.send") == 0
    assert get_outbox() == []


def test_audit_log_written_before_execution_and_has_all_fields(tmp_path):
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_audit_fields"), audit_log_path=str(tmp_path / "agentguard_audit_fields.jsonl"))
    counters.reset_all()
    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(tmp_path / "agentguard_audit_fields" / "notes" / "q3.txt")},
        "task": "Read notes",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "audit-1",
    }, mode="protected")

    assert result["decision"] == "ALLOW"
    assert counters.get_count("file.read") == 1
    entries = checkpoint.audit_log.read_entries()
    assert len(entries) >= 1
    entry = entries[-1]
    required = {"request_id", "timestamp", "tool", "params", "decision", "rule_id", "reason", "approver", "review_status", "outcome", "mode"}
    assert required.issubset(entry.keys())
    assert entry["outcome"] == "executed"


def test_log_failure_blocks_execution_and_does_not_execute_tool(tmp_path):
    counters.reset_all()
    checkpoint = Checkpoint(sandbox_root=str(tmp_path / "agentguard_log_failure"), audit_log_path=str(tmp_path / "agentguard_log_failure.jsonl"))
    original = checkpoint.audit_log.write_entry
    checkpoint.audit_log.write_entry = lambda entry: (_ for _ in ()).throw(RuntimeError("log failure"))

    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(tmp_path / "agentguard_log_failure" / "notes" / "q3.txt")},
        "task": "Read notes",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "audit-2",
    }, mode="protected")

    assert result["decision"] == "BLOCK"
    assert result["outcome"] == "not_executed"
    assert counters.get_count("file.read") == 0
    checkpoint.audit_log.write_entry = original


def test_unprotected_metrics_report_but_ran_counts():
    from runner import run_all

    payload = run_all("unprotected")
    metrics = payload["metrics"]
    assert "decision_accuracy" not in metrics
    assert "would_have_been_blocked_but_ran" in metrics
    assert "would_have_needed_review_but_ran" in metrics
    assert "out_of_policy_executions" in metrics
