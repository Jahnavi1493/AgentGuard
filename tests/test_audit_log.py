import json
import os

import pytest

from agentguard.audit_log import AuditLogger
from agentguard.checkpoint import Checkpoint


def test_audit_entry_written_and_has_fields(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(log_path))
    entry = {
        "request_id": "req-1",
        "timestamp": "2024-01-01T00:00:00Z",
        "tool": "file.read",
        "params": {"path": str(tmp_path / "notes" / "file.txt")},
        "decision": "ALLOW",
        "rule_id": "R1",
        "reason": "Read is allowed",
        "approver": None,
        "review_status": None,
        "outcome": "executed",
        "mode": "protected",
    }
    logger.write_entry(entry)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert set(data.keys()) >= {
        "request_id",
        "timestamp",
        "tool",
        "params",
        "decision",
        "rule_id",
        "reason",
        "approver",
        "review_status",
        "outcome",
        "mode",
    }


def test_log_failure_blocks_execution(monkeypatch, tmp_path):
    checkpoint = Checkpoint(sandbox_root=str(tmp_path), audit_log_path=str(tmp_path / "audit.jsonl"))

    def fail_write(_entry):
        raise OSError("disk full")

    monkeypatch.setattr(checkpoint.audit_log, "write_entry", fail_write)
    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(tmp_path / "notes" / "q3.txt")},
        "task": "Read notes",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "req-2",
    }, mode="protected")

    assert result["decision"] == "BLOCK"
    assert result["rule_id"] == "LOG_FAILURE"
