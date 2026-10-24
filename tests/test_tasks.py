import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agentguard.checkpoint import Checkpoint

ROOT = Path(__file__).resolve().parent.parent


def test_tasks_json_has_required_shape():
    tasks = json.loads((ROOT / "agent" / "tasks.json").read_text(encoding="utf-8"))
    assert [task["id"] for task in tasks] == ["T1", "T2", "T3", "T4"]
    for task in tasks:
        assert {"id", "title", "user_request", "icon", "description", "scope", "plan"}.issubset(task.keys())
        for entry in task["plan"]:
            assert {"tool", "params", "plain_english"}.issubset(entry.keys())


def test_phase_1_task_decisions_are_stable_under_protected_deny():
    tasks = json.loads((ROOT / "agent" / "tasks.json").read_text(encoding="utf-8"))
    expected = {
        "T1": [("ALLOW", "R1", True), ("BLOCK", "R2", False), ("REVIEW", "R3", False)],
        "T2": [("ALLOW", "R1", True), ("ALLOW", "SCOPE-ALLOW", True), ("REVIEW", "R3", False), ("BLOCK", "SCOPE", False)],
        "T3": [("ALLOW", "R2b", True), ("BLOCK", "R2", False), ("BLOCK", "SCOPE", False)],
        "T4": [("ALLOW", "R7", True), ("BLOCK", "DEFAULT", False), ("BLOCK", "SCOPE", False)],
    }

    for task in tasks:
        task_id = task["id"]
        sandbox_root = ROOT / "sandbox_task_test" / task_id
        sandbox_root.mkdir(parents=True, exist_ok=True)
        checkpoint = Checkpoint(sandbox_root=str(sandbox_root), policy_path=str(ROOT / "policies" / "default_policy.json"), audit_log_path=str(sandbox_root / "audit.jsonl"))

        results = []
        for plan_item in task["plan"]:
            result = checkpoint.run_tool({
                "tool": plan_item["tool"],
                "params": dict(plan_item["params"]),
                "task": task["user_request"],
                "task_title": task["title"],
                "task_scope": task.get("scope"),
                "id": f"{task_id}-{plan_item['tool']}",
                "timestamp": "2026-01-01T00:00:00Z",
            }, mode="protected")
            if result.get("decision") == "REVIEW":
                checkpoint.deny(result["request_id"])
            results.append((result.get("decision"), result.get("rule_id"), result.get("outcome") == "executed"))

        assert results == expected[task_id], f"Unexpected decisions for {task_id}: {results}"


def test_dashboard_task_picker_and_no_absolute_paths_for_each_task():
    for task_id in ["T1", "T2", "T3", "T4"]:
        at = AppTest.from_file("dashboard.py")
        at.run()
        at.session_state["selected_task_id"] = task_id
        at.run()

        run_demo = next(button for button in at.button if getattr(button, "label", "") == "▶ Run the AI's plan")
        run_demo.click()
        at.run()

        assert not at.exception
        page_text = str(at).lower()
        assert "<div" not in page_text
        assert "/users/" not in page_text

        if task_id == "T4":
            assert any("hidden instruction" in str(item.value).lower() for item in at.warning)
