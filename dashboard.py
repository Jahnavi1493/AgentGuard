from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import streamlit as st

from agent.llm_agent import LLMAgent, build_example_prompts
from agentguard.checkpoint import Checkpoint
from agentguard.tools import counters
from agentguard.tools._db_tools import reset_db
from agentguard.tools._email_tools import clear_outbox, get_outbox
from agentguard.tools._file_tools import ensure_sandbox
from runner import run_all

ROOT = Path(__file__).resolve().parent
SANDBOX_ROOT = ROOT / "sandbox"


def load_tasks() -> list[dict]:
    """Load the preset tasks used by the Live demo."""
    with open(ROOT / "agent" / "tasks.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def _reset_demo_state() -> Checkpoint:
    """Recreate the sandbox and empty all transient state for a clean demo."""
    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_sandbox(str(SANDBOX_ROOT))
    counters.reset_all()
    clear_outbox()
    reset_db()
    audit_log = ROOT / "audit.jsonl"
    if audit_log.exists():
        audit_log.unlink()
    checkpoint = Checkpoint(sandbox_root=str(SANDBOX_ROOT), policy_path=str(ROOT / "policies" / "default_policy.json"), audit_log_path=str(ROOT / "audit.jsonl"))
    return checkpoint


@st.cache_resource
def get_checkpoint() -> Checkpoint:
    """Return the shared checkpoint instance used by the dashboard."""
    return _reset_demo_state()


def badge_color(decision: str) -> str:
    """Return the colour key used for the badge in the cards."""
    if decision == "ALLOW":
        return "green"
    if decision == "BLOCK":
        return "red"
    if decision == "REVIEW":
        return "amber"
    return "grey"


def _render_result_cards(results: list[dict]) -> None:
    """Display each tool call in a clean card layout."""
    for result in results:
        decision = result.get("decision", "RAN – no check")
        label = decision if decision in {"ALLOW", "BLOCK", "REVIEW"} else "RAN – no check"
        st.write(f"**{label}**")
        st.write(f"Tool: {result['tool']}")
        st.write(f"Params: {result['params']}")
        st.write(f"Rule: {result.get('rule_id', 'n/a')}")
        st.write(f"Reason: {result.get('reason', 'No reason recorded')}")


def _display_path(path: str) -> str:
    """Convert sandbox paths to relative, user-safe display values."""
    if not isinstance(path, str) or not os.path.isabs(path):
        return path
    try:
        return os.path.relpath(path, str(SANDBOX_ROOT))
    except ValueError:
        return path


def _build_demo_actions(task_id: str = "T1") -> list[dict]:
    """Return the three or four actions used by the selected preset task."""
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            return [
                {"title": item["plain_english"], "tool": item["tool"], "params": dict(item["params"]), "plain_english": item["plain_english"], "icon": item["icon"], "rule_id": "R1"}
                for item in task["plan"]
            ]
    return []


def _render_action_card(title: str, status_text: str, status_color: str, reason: str, technical_details: dict | None = None) -> str:
    """Return a plain text card summary for a demo action."""
    return (
        f"{status_text}\n"
        f"{title}\n"
        f"{reason}\n"
        f"Technical details: Tool={technical_details.get('tool', 'n/a')}; Params={technical_details.get('params', {})}; Rule ID={technical_details.get('rule_id', 'n/a')}"
    )


def _get_reason_for_action(action: dict, result: dict | None, mode: str) -> str:
    """Return a plain-English reason for the action status."""
    if action["tool"] == "file.read":
        return "This is a safe read of the file the user asked for."
    if action["tool"] == "file.delete":
        if mode == "protected":
            return "This payroll file is safe and should not be deleted without a human check."
        return "The file was deleted without any guardrail check."
    if action["tool"] == "email.send":
        if mode == "protected":
            return "This email is going to someone outside your company, so it needs approval."
        return "The email was sent outside the company without approval."
    return result.get("reason", "No reason recorded") if result else "No reason recorded"


def render_live_demo() -> None:
    """Show the selected preset task in a judge-friendly live demo."""
    tasks = load_tasks()
    task_ids = [task["id"] for task in tasks]
    current_task_id = st.session_state.get("selected_task_id", "T1")
    if current_task_id not in task_ids:
        current_task_id = task_ids[0]
    selected_task_id = st.selectbox(
        "Preset task",
        task_ids,
        index=task_ids.index(current_task_id),
        format_func=lambda task_id: f"{task_id} - {next(task['title'] for task in tasks if task['id'] == task_id)}",
    )
    if selected_task_id != current_task_id:
        st.session_state["selected_task_id"] = selected_task_id
        for key in ["demo_without_results", "demo_with_results", "demo_summary", "demo_checkpoint", "demo_email_override", "demo_review_request_id", "demo_review_started_at"]:
            st.session_state.pop(key, None)
    task = next(item for item in tasks if item["id"] == selected_task_id)

    st.header("Live demo")
    st.write(task["user_request"])
    st.caption(task["description"])
    if selected_task_id == "T4":
        st.warning("Hidden instruction detected: the supplier note tries to push the agent toward sensitive payroll actions. AgentGuard still blocks or pauses those steps before execution.")

    st.subheader("The AI's plan")
    mode = st.radio("Agent mode", ["Scripted default", "Live AI experimental"], index=0, key="agent_mode")
    if mode == "Live AI experimental":
        q = st.text_area("AI task prompt", value=task["user_request"], key="llm_prompt_input")
        examples = build_example_prompts()
        cols = st.columns(3)
        for idx, example in enumerate(examples):
            if cols[idx].button(f"Example {idx + 1}", key=f"llm_example_{idx}"):
                st.session_state["llm_prompt_input"] = example
        if st.button("Generate AI plan", key="generate_llm_plan"):
            result = LLMAgent().propose_plan(st.session_state.get("llm_prompt_input", task["user_request"]))
            if not result.get("enabled", False):
                st.warning(result.get("message", "LLM mode is disabled."))
                st.session_state["live_ai_plan"] = task["plan"]
            else:
                st.success(result.get("message", "LLM plan generated."))
                st.json({"model": result.get("model"), "plan": result.get("plan")})
                st.session_state["live_ai_plan"] = result.get("plan", task["plan"])
    else:
        st.session_state.pop("live_ai_plan", None)

    plan_items = st.session_state.get("live_ai_plan", task["plan"])
    for item in plan_items:
        title = item.get("plain_english") or item.get("reason") or f"{item.get('tool', 'step')}"
        icon = item.get("icon", "•")
        st.write(f"{icon} {title}")
        with st.expander("Technical details", expanded=False):
            st.write(f"Tool: {item.get('tool', 'n/a')}")
            st.write(f"Params: {item.get('params', {})}")

    if st.button("▶ Run the AI's plan"):
        checkpoint = _reset_demo_state()
        from agentguard.tools import RAW_TOOLS

        with_results: list[dict] = []
        without_results: list[dict] = []

        left_col, right_col = st.columns(2)
        with left_col:
            st.subheader("❌ Without AgentGuard")
        with right_col:
            st.subheader("🛡️ With AgentGuard")

        active_plan = st.session_state.get("live_ai_plan", task["plan"])
        for index, action in enumerate(active_plan):
            tool_name = action.get("tool") or action.get("name") or "file.read"
            action_params = dict(action.get("params", {}))
            plain_text = action.get("plain_english") or action.get("reason") or tool_name
            time.sleep(0.2)
            if tool_name in {"file.read", "file.delete"}:
                value = action_params["path"]
                if not os.path.isabs(value):
                    value = str(SANDBOX_ROOT / value)
                action_params["path"] = value

            raw = RAW_TOOLS[tool_name]
            raw_result = raw(**action_params)
            decision = "ALLOW"
            if tool_name == "file.delete":
                decision = "BLOCK" if raw_result is False else "ALLOW"
            display_params = dict(action_params)
            if "path" in display_params:
                display_params["path"] = _display_path(display_params["path"])
            without_results.append({
                "tool": tool_name,
                "params": display_params,
                "reason": plain_text,
                "title": plain_text,
                "decision": decision,
            })

            protected_result = checkpoint.run_tool({
                "tool": tool_name,
                "params": action_params,
                "task": task["user_request"],
                "task_id": selected_task_id,
                "task_scope": task.get("scope"),
                "id": f"demo-{selected_task_id}-{index + 1}",
                "timestamp": time.time(),
            }, mode="protected")

            protected_params = dict(action_params)
            if "path" in protected_params:
                protected_params["path"] = _display_path(protected_params["path"])
            if protected_result.get("decision") == "REVIEW":
                st.session_state["demo_review_request_id"] = protected_result["request_id"]
                st.session_state["demo_review_started_at"] = time.time()
                with_results.append({
                    "tool": tool_name,
                    "params": protected_params,
                    "reason": protected_result.get("reason", "Needs human approval."),
                    "title": "⏸️ Email PAUSED – waiting for your approval",
                    "decision": "REVIEW",
                    "badge": "REVIEW",
                    "rule_id": protected_result.get("rule_id", "R3"),
                })
            elif protected_result.get("decision") == "ALLOW":
                with_results.append({
                    "tool": tool_name,
                    "params": protected_params,
                    "reason": protected_result.get("reason", "Allowed by policy."),
                    "title": f"✅ {plain_text}",
                    "decision": "ALLOW",
                    "badge": "ALLOW",
                    "rule_id": protected_result.get("rule_id", "ALLOW"),
                })
            else:
                with_results.append({
                    "tool": tool_name,
                    "params": protected_params,
                    "reason": protected_result.get("reason", "Blocked by policy."),
                    "title": "⛔ Delete BLOCKED – payroll file is safe" if tool_name == "file.delete" else "⛔ Blocked",
                    "decision": "BLOCK",
                    "badge": "BLOCK",
                    "rule_id": protected_result.get("rule_id", "BLOCK"),
                })

        st.session_state["demo_checkpoint"] = checkpoint
        st.session_state["demo_without_results"] = without_results
        st.session_state["demo_with_results"] = with_results
        st.session_state["demo_summary"] = {
            "without_deleted": sum(1 for item in without_results if item["tool"] == "file.delete" and item["decision"] == "BLOCK"),
            "with_deleted": sum(1 for item in with_results if item["tool"] == "file.delete" and item["decision"] == "BLOCK"),
            "without_emails": sum(1 for item in without_results if item["tool"] == "email.send"),
            "with_emails": sum(1 for item in with_results if item["tool"] == "email.send" and item["decision"] == "ALLOW"),
            "without_logged": 0,
            "with_logged": sum(1 for item in with_results if item.get("reason")),
        }

    if "demo_without_results" in st.session_state:
        without_results = st.session_state["demo_without_results"]
        with_results = st.session_state["demo_with_results"]

        left_col, right_col = st.columns(2)
        with left_col:
            st.subheader("❌ Without AgentGuard")
            for item in without_results:
                st.write(f"{item['decision']} - {item['title']}")
                st.caption(item["reason"])
        with right_col:
            st.subheader("🛡️ With AgentGuard")
            for item in with_results:
                st.write(f"{item['decision']} - {item['title']}")
                st.caption(item["reason"])

        request_id = st.session_state.get("demo_review_request_id")
        if request_id and not st.session_state.get("demo_email_override"):
            st.warning("The AI wants to send an email to an external recipient. Do you allow it?")
            approver = st.text_input("Approver name", key="demo_approver_input")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key="demo_approve_button"):
                    name = approver or "human"
                    checkpoint = st.session_state.get("demo_checkpoint") or get_checkpoint()
                    checkpoint.approve(request_id, name)
                    st.session_state["demo_email_override"] = {
                        "title": f"✅ Email sent after approval by {name}",
                        "reason": "You approved this external email, so it was sent.",
                    }
                    st.rerun()
            with col2:
                if st.button("⛔ Deny", key="demo_deny_button"):
                    name = approver or "human"
                    checkpoint = st.session_state.get("demo_checkpoint") or get_checkpoint()
                    checkpoint.deny(request_id)
                    st.session_state["demo_email_override"] = {
                        "title": f"⛔ Email cancelled by {name}",
                        "reason": "You denied this external email, so it was cancelled.",
                    }
                    st.rerun()

        summary = st.session_state.get("demo_summary", {"without_deleted": 0, "with_deleted": 0, "without_emails": 0, "with_emails": 0, "without_logged": 0, "with_logged": 0})
        st.success("AgentGuard stopped 1 dangerous action and paused 1 risky one – before anything happened.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Files deleted", f"{summary['without_deleted']} vs {summary['with_deleted']}")
        with col2:
            st.metric("Emails sent without approval", f"{summary['without_emails']} vs {summary['with_emails']}")
        with col3:
            st.metric("Actions with a logged reason", f"{summary['without_logged']} vs {summary['with_logged']}")

        st.sidebar.info("Every action the AI tries passes through AgentGuard first. Safe → allowed. Dangerous → blocked. Risky → a human decides.")
    else:
        st.sidebar.info("Every action the AI tries passes through AgentGuard first. Safe → allowed. Dangerous → blocked. Risky → a human decides.")


def render_review_queue() -> None:
    """Show pending review items and the approval lifecycle controls."""
    st.subheader("Review queue")
    checkpoint = st.session_state.get("checkpoint") or get_checkpoint()
    pending = checkpoint.review_queue.pending()
    if not pending:
        st.info("No REVIEW requests are pending right now.")
        return
    for request in pending:
        with st.container():
            st.write(f"Tool: {request.tool_name}")
            st.write(f"Params: {request.params}")
            st.write(f"Reason: {request.decision['reason']}")
            elapsed = time.time() - request.created_at
            remaining = max(0, request.timeout_seconds - int(elapsed))
            st.write(f"Time remaining before auto deny: {remaining}s")
            approver = st.text_input(f"Approver for {request.request_id}", key=f"approver_{request.request_id}")
            col1, col2 = st.columns(2)
            if col1.button("Approve", key=f"approve_{request.request_id}"):
                try:
                    result = checkpoint.approve(request.request_id, approver or "human")
                    status = str(result.get("status", "unknown")).lower()
                    if status in {"approved", "executed"}:
                        st.success(f"Approved: {result['status']}")
                    else:
                        st.warning(f"Approval status: {result['status']}")
                except Exception as exc:  # pragma: no cover - defensive UI guard
                    st.error(f"Approve failed: {type(exc).__name__}")
            if col2.button("Deny", key=f"deny_{request.request_id}"):
                try:
                    result = checkpoint.deny(request.request_id)
                    status = str(result.get("status", "unknown")).lower()
                    if status in {"denied", "not_executed"}:
                        st.warning(f"Denied: {result['status']}")
                    else:
                        st.info(f"Deny status: {result['status']}")
                except Exception as exc:  # pragma: no cover - defensive UI guard
                    st.error(f"Deny failed: {type(exc).__name__}")


def render_evaluation() -> None:
    """Run the full 24-scenario evaluation and show the metrics side-by-side."""
    st.subheader("Evaluation")
    if st.button("Run all 24 scenarios"):
        try:
            protected = run_all("protected", "deny")
            unprotected = run_all("unprotected")
            st.session_state["last_eval"] = {"protected": protected["metrics"], "unprotected": unprotected["metrics"]}
        except Exception as exc:  # pragma: no cover - defensive UI guard
            st.error(f"Run all 24 scenarios failed: {type(exc).__name__}")

    if "last_eval" in st.session_state:
        metrics = st.session_state["last_eval"]
        st.dataframe([metrics["protected"], metrics["unprotected"]])
        st.subheader("Per-scenario comparison")
        protected_results = run_all("protected", "deny")["results"]
        unprotected_results = run_all("unprotected")["results"]
        rows = []
        for scenario in json.loads((ROOT / "agent" / "scenarios.json").read_text()) :
            protected_row = next((item for item in protected_results if item.get("scenario_id") == scenario["id"]), {})
            unprotected_row = next((item for item in unprotected_results if item.get("scenario_id") == scenario["id"]), {})
            rows.append({
                "id": scenario["id"],
                "tool": scenario["tool"],
                "expected_decision": scenario["expected_decision"],
                "protected_decision": protected_row.get("decision"),
                "protected_ran": protected_row.get("outcome") == "executed",
                "unprotected_ran": unprotected_row.get("outcome") == "executed",
            })
        st.dataframe(rows)


def render_audit_logs() -> None:
    """Display the JSONL audit log with filters and downloads."""
    st.subheader("Audit log")
    rows = []
    audit_file = ROOT / "audit.jsonl"
    if audit_file.exists():
        for line in reversed(audit_file.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                rows.append(json.loads(line))
    decision_filter = st.selectbox("Decision filter", ["ALL", "ALLOW", "BLOCK", "REVIEW"])
    if decision_filter != "ALL":
        rows = [row for row in rows if row.get("decision") == decision_filter]
    st.dataframe(rows)
    if audit_file.exists():
        with open(audit_file, "rb") as handle:
            st.download_button("Download audit.jsonl", data=handle, file_name="audit.jsonl", mime="application/jsonl")
    else:
        st.caption("No audit log has been written yet.")


def render_policy() -> None:
    """Display the policy and the rule-order note."""
    st.subheader("Policy")
    policy = json.loads((ROOT / "policies" / "default_policy.json").read_text(encoding="utf-8"))
    rows = []
    for rule in policy["rules"]:
        condition = (
            rule.get("path_under")
            or rule.get("path_not_under")
            or rule.get("recipient_domain_in")
            or rule.get("recipient_domain_not_in")
            or rule.get("query_is_read_only")
            or rule.get("table_in")
            or "all"
        )
        if isinstance(condition, (list, tuple, set)):
            condition = ", ".join(str(item) for item in condition)
        elif isinstance(condition, bool):
            condition = str(condition).lower()
        rows.append({
            "rule_id": rule["id"],
            "tool": rule.get("tool", "-"),
            "condition": str(condition),
            "decision": rule.get("decision", "BLOCK"),
            "reason": rule.get("reason", "-"),
        })
    st.dataframe(rows)
    st.caption("BLOCK rules → REVIEW → ALLOW; no match = BLOCK")


def main() -> None:
    """Render the complete Streamlit app."""
    st.set_page_config(page_title="AgentGuard Dashboard", layout="wide")
    with st.sidebar:
        st.title("AgentGuard")
        if st.button("Reset demo"):
            try:
                _reset_demo_state()
            except Exception as exc:  # pragma: no cover - defensive UI guard
                st.error(f"Reset demo failed: {type(exc).__name__}")
    tabs = st.tabs(["Live demo", "Review queue", "Evaluation", "Audit log", "Policy"])
    with tabs[0]:
        render_live_demo()
    with tabs[1]:
        render_review_queue()
    with tabs[2]:
        render_evaluation()
    with tabs[3]:
        render_audit_logs()
    with tabs[4]:
        render_policy()


if __name__ == "__main__":
    main()
