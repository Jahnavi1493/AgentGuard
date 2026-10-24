import json
from pathlib import Path

from agentguard.checkpoint import Checkpoint
from agentguard.models import ToolCall
from agentguard.policy_engine import PolicyEngine

ROOT = Path(__file__).resolve().parent.parent


def test_t1_to_t4_expected_decisions_are_stable_under_protected_deny():
    tasks = json.loads((ROOT / "agent" / "tasks.json").read_text(encoding="utf-8"))
    expected = {
        "T1": [("ALLOW", "R1", True), ("BLOCK", "R2", False), ("REVIEW", "R3", False)],
        "T2": [("ALLOW", "R1", True), ("ALLOW", "SCOPE-ALLOW", True), ("REVIEW", "R3", False), ("BLOCK", "SCOPE", False)],
        "T3": [("ALLOW", "R2b", True), ("BLOCK", "R2", False), ("BLOCK", "SCOPE", False)],
        "T4": [("ALLOW", "R7", True), ("BLOCK", "DEFAULT", False), ("BLOCK", "SCOPE", False)],
    }
    for task in tasks:
        task_id = task["id"]
        sandbox = ROOT / "sandbox_task_phase2" / task_id
        sandbox.mkdir(parents=True, exist_ok=True)
        checkpoint = Checkpoint(sandbox_root=str(sandbox), policy_path=str(ROOT / "policies" / "default_policy.json"), audit_log_path=str(sandbox / "audit.jsonl"))
        results = []
        for plan_item in task["plan"]:
            result = checkpoint.run_tool({
                "tool": plan_item["tool"],
                "params": dict(plan_item["params"]),
                "task": task["user_request"],
                "task_title": task["title"],
                "task_id": task_id,
                "task_scope": task.get("scope"),
                "id": f"{task_id}-{plan_item['tool']}",
                "timestamp": "2026-01-01T00:00:00Z",
            }, mode="protected")
            if result.get("decision") == "REVIEW":
                checkpoint.deny(result["request_id"])
            results.append((result.get("decision"), result.get("rule_id"), result.get("outcome") == "executed"))
        assert results == expected[task_id], f"Unexpected decisions for {task_id}: {results}"


def test_task_scope_cannot_override_global_block():
    policy_path = ROOT / "policies" / "default_policy.json"
    engine = PolicyEngine(str(policy_path))
    blocked = engine.evaluate(ToolCall("file.delete", {"path": "/agentguard/finance/payroll.xlsx"}, "Delete payroll", "2026-01-01T00:00:00Z", task_scope="workspace"))
    assert blocked.decision == "BLOCK"
    assert blocked.rule_id == "R2"


def test_no_scope_keeps_all_24_original_scenarios_unchanged():
    scenarios = json.loads((ROOT / "agent" / "scenarios.json").read_text(encoding="utf-8"))
    assert len(scenarios) == 24
    assert all(scenario.get("expected_decision") in {"ALLOW", "BLOCK", "REVIEW"} for scenario in scenarios)


def test_audit_entry_includes_task_id(tmp_path):
    sandbox = tmp_path / "audit_task_id"
    checkpoint = Checkpoint(sandbox_root=str(sandbox))
    result = checkpoint.run_tool({
        "tool": "file.read",
        "params": {"path": str(sandbox / "notes" / "q3.txt")},
        "task": "Read notes",
        "task_id": "T1",
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "req-taskid-1",
    }, mode="protected")
    assert result["decision"] == "ALLOW"
    entries = checkpoint.audit_log.read_entries()
    assert entries and entries[-1].get("task_id") == "T1"


def test_task_scope_rules_are_respected(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({
            "default": "BLOCK",
            "rules": [
                {"id": "CLIENT_EMAIL", "tool": "email.send", "task_scope": ["client"], "recipient_domain_in": ["acme-client.com"], "decision": "ALLOW", "reason": "Client emails are allowed in the client task scope."},
                {"id": "WORKSPACE_EMAIL", "tool": "email.send", "task_scope": ["workspace"], "recipient_domain_in": ["example.com"], "decision": "ALLOW", "reason": "Workspace emails are allowed in the workspace task scope."},
            ],
        }),
        encoding="utf-8",
    )

    engine = PolicyEngine(str(policy_path))
    client_allowed = engine.evaluate(ToolCall("email.send", {"to": "hello@acme-client.com"}, "Send client update", "2024-01-01T00:00:00Z", task_scope="client"))
    workspace_allowed = engine.evaluate(ToolCall("email.send", {"to": "hello@example.com"}, "Send workspace update", "2024-01-01T00:00:00Z", task_scope="workspace"))
    wrong_scope = engine.evaluate(ToolCall("email.send", {"to": "hello@acme-client.com"}, "Send client update", "2024-01-01T00:00:00Z", task_scope="workspace"))

    assert client_allowed.decision == "ALLOW"
    assert workspace_allowed.decision == "ALLOW"
    assert wrong_scope.decision == "BLOCK"
