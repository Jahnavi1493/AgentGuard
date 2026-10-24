import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agentguard.checkpoint import Checkpoint


def test_dashboard_boots_and_has_tabs():
    at = AppTest.from_file("dashboard.py")
    at.run()

    assert at.button
    assert [tab.label for tab in at.tabs] == ["Live demo", "Review queue", "Evaluation", "Audit log", "Policy"]


def test_dashboard_run_buttons_and_review_actions():
    at = AppTest.from_file("dashboard.py")
    at.run()

    run_demo = next(button for button in at.button if getattr(button, "label", "") == "▶ Run the AI's plan")
    run_demo.click()
    at.run()
    assert not at.exception

    assert any("AgentGuard stopped 1 dangerous action" in str(item.value) for item in at.success)
    assert any("Without AgentGuard" in str(getattr(item, "value", "")) for item in at.subheader)
    assert any("With AgentGuard" in str(getattr(item, "value", "")) for item in at.subheader)

    root = Path(tempfile.mkdtemp(prefix="agentguard_dashboard_review_"))
    checkpoint = Checkpoint(sandbox_root=str(root), policy_path="policies/default_policy.json", audit_log_path=str(root / "audit.jsonl"))
    checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-1",
    }, mode="protected")
    at.session_state["checkpoint"] = checkpoint
    at.run()

    approver = at.tabs[1].text_input[0]
    approver.input("alice")
    approve_button = at.tabs[1].button[0]
    approve_button.click()
    at.run()
    assert not at.exception
    assert any("approved" in str(item.value).lower() or "executed" in str(item.value).lower() for item in at.success)

    root = Path(tempfile.mkdtemp(prefix="agentguard_dashboard_deny_"))
    checkpoint = Checkpoint(sandbox_root=str(root), policy_path="policies/default_policy.json", audit_log_path=str(root / "audit.jsonl"))
    checkpoint.run_tool({
        "tool": "email.send",
        "params": {"to": "friend@external.org", "subject": "Demo", "body": "Hello"},
        "task": "Send external email",
        "timestamp": "2024-01-01T00:00:00Z",
        "id": "review-2",
    }, mode="protected")
    at.session_state["checkpoint"] = checkpoint
    at.run()

    deny_button = at.tabs[1].button[1]
    deny_button.click()
    at.run()
    assert not at.exception
    assert any("denied" in str(item.value).lower() or "not executed" in str(item.value).lower() for item in at.warning)

    run_all_button = next(button for button in at.button if getattr(button, "label", "") == "Run all 24 scenarios")
    run_all_button.click()
    at.run()
    assert not at.exception

    sidebar_reset = next(button for button in at.button if getattr(button, "label", "") == "Reset demo")
    sidebar_reset.click()
    at.run()
    assert not at.exception
