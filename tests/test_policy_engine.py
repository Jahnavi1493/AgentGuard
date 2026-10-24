from pathlib import Path

from agentguard.models import ToolCall
from agentguard.policy_engine import PolicyEngine


policy = PolicyEngine(Path(__file__).resolve().parents[1] / "policies" / "default_policy.json")


def test_policy_rules_match_expected():
    read_call = ToolCall("file.read", {"path": "/sandbox/notes/q3.txt"}, "Read notes", "2024-01-01T00:00:00Z")
    decision = policy.evaluate(read_call)
    assert decision.decision == "ALLOW"
    assert decision.rule_id == "R1"

    delete_call = ToolCall("file.delete", {"path": "/sandbox/tmp/old.log"}, "Delete temp log", "2024-01-01T00:01:00Z")
    decision = policy.evaluate(delete_call)
    assert decision.decision == "ALLOW"
    assert decision.rule_id == "R2b"

    email_call = ToolCall("email.send", {"to": "student@example.edu"}, "Send internal email", "2024-01-01T00:02:00Z")
    decision = policy.evaluate(email_call)
    assert decision.decision == "ALLOW"
    assert decision.rule_id == "R4"

    external_email = ToolCall("email.send", {"to": "friend@external.org"}, "Send external email", "2024-01-01T00:03:00Z")
    decision = policy.evaluate(external_email)
    assert decision.decision == "REVIEW"
    assert decision.rule_id == "R3"

    db_read = ToolCall("db.query", {"sql": "SELECT * FROM products"}, "Read products", "2024-01-01T00:04:00Z")
    decision = policy.evaluate(db_read)
    assert decision.decision == "ALLOW"
    assert decision.rule_id == "R6"

    db_block = ToolCall("db.query", {"sql": "DELETE FROM products"}, "Delete from products", "2024-01-01T00:05:00Z")
    decision = policy.evaluate(db_block)
    assert decision.decision == "BLOCK"
    assert decision.rule_id == "R5"


def test_rule_ordering_block_before_review_before_allow():
    blocked = policy.evaluate(ToolCall("file.delete", {"path": "/sandbox/finance/payroll.xlsx"}, "Delete payroll", "2024-01-01T00:06:00Z"))
    assert blocked.decision == "BLOCK"

    review = policy.evaluate(ToolCall("email.send", {"to": "friend@external.org"}, "Send external email", "2024-01-01T00:07:00Z"))
    assert review.decision == "REVIEW"

    allow = policy.evaluate(ToolCall("file.read", {"path": "/sandbox/notes/q3.txt"}, "Read notes", "2024-01-01T00:08:00Z"))
    assert allow.decision == "ALLOW"


def test_no_match_defaults_to_block():
    decision = policy.evaluate(ToolCall("shell.exec", {"cmd": "ls"}, "Run shell command", "2024-01-01T00:09:00Z"))
    assert decision.decision == "BLOCK"
    assert decision.rule_id == "DEFAULT"


def test_rules_r1_through_r6_match_individually():
    cases = [
        (ToolCall("file.read", {"path": "/agentguard/notes/q3.txt"}, "Read notes", "2024-01-01T00:10:00Z"), "ALLOW", "R1"),
        (ToolCall("file.delete", {"path": "/agentguard/finance/payroll.xlsx"}, "Delete payroll", "2024-01-01T00:11:00Z"), "BLOCK", "R2"),
        (ToolCall("file.delete", {"path": "/agentguard/tmp/old.log"}, "Delete tmp log", "2024-01-01T00:12:00Z"), "ALLOW", "R2b"),
        (ToolCall("email.send", {"to": "friend@external.org"}, "Send external email", "2024-01-01T00:13:00Z"), "REVIEW", "R3"),
        (ToolCall("email.send", {"to": "student@example.edu"}, "Send internal email", "2024-01-01T00:14:00Z"), "ALLOW", "R4"),
        (ToolCall("db.query", {"sql": "SELECT * FROM products"}, "Read products", "2024-01-01T00:15:00Z"), "ALLOW", "R6"),
    ]
    for tool_call, expected_decision, expected_rule in cases:
        decision = policy.evaluate(tool_call)
        assert decision.decision == expected_decision
        assert decision.rule_id == expected_rule

    blocked_sql = ToolCall("db.query", {"sql": "DELETE FROM products"}, "Delete from products", "2024-01-01T00:16:00Z")
    decision = policy.evaluate(blocked_sql)
    assert decision.decision == "BLOCK"
    assert decision.rule_id == "R5"
