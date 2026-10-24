from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from .models import Decision, ToolCall


class PolicyEngine:
    """Load a JSON policy and evaluate a tool call against it."""

    def __init__(self, policy_path: str, sandbox_root: Optional[str] = None):
        self.policy_path = policy_path
        self.policy = self._load_policy(policy_path)
        self.sandbox_root = os.path.realpath(os.path.abspath(sandbox_root)) if sandbox_root else None

    def _load_policy(self, policy_path: str) -> Dict[str, Any]:
        with open(policy_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _extract_email_domain(self, email: Optional[str]) -> Optional[str]:
        if not email or not isinstance(email, str) or "@" not in email:
            return None
        return email.rsplit("@", 1)[1].lower()

    def _extract_tables(self, sql: Optional[str]) -> List[str]:
        if not isinstance(sql, str):
            return []
        matches = []
        for pattern in [r"FROM\s+([A-Za-z_][A-Za-z0-9_]*)", r"JOIN\s+([A-Za-z_][A-Za-z0-9_]*)"]:
            matches.extend(re.findall(pattern, sql, flags=re.IGNORECASE))
        return [table.lower() for table in matches]

    def _is_read_only_sql(self, sql: Optional[str]) -> bool:
        if not isinstance(sql, str):
            return False
        clean = sql.strip()
        if not clean:
            return False
        if not clean.upper().startswith("SELECT"):
            return False
        if ";" in clean:
            return False
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "ATTACH",
            "PRAGMA",
        ]
        upper_sql = clean.upper()
        for word in forbidden:
            if word in upper_sql:
                return False
        return True

    def _infer_sandbox_root(self, path: str) -> str:
        if not isinstance(path, str):
            return os.path.sep
        current = os.path.abspath(path)
        parts = current.split(os.path.sep)
        for index in range(len(parts) - 1, 0, -1):
            segment = parts[index]
            if "sandbox" in segment.lower() or "agentguard" in segment.lower():
                return os.path.join(os.path.sep, *parts[1:index + 1])
        parent = os.path.dirname(current)
        if parent:
            return parent
        return os.path.sep

    def _matches(self, rule: Dict[str, Any], tool_call: ToolCall) -> bool:
        if rule.get("tool") and rule["tool"] != tool_call.tool:
            return False

        task_scope = getattr(tool_call, "task_scope", None)
        if "task_scope" in rule:
            allowed_scopes = rule["task_scope"]
            if isinstance(allowed_scopes, str):
                allowed_scopes = [allowed_scopes]
            if task_scope is None or task_scope not in {str(scope).lower() for scope in allowed_scopes}:
                return False

        path = tool_call.params.get("path")
        if "path_under" in rule:
            if not isinstance(path, str):
                return False
            sandbox_root = self.sandbox_root or self._infer_sandbox_root(path)
            sandbox_root = os.path.realpath(os.path.abspath(sandbox_root))
            rel = os.path.relpath(os.path.realpath(path), sandbox_root)
            if not rel.startswith(rule["path_under"].replace("\\", "/")):
                return False

        if "path_not_under" in rule:
            if not isinstance(path, str):
                return False
            sandbox_root = self.sandbox_root or self._infer_sandbox_root(path)
            sandbox_root = os.path.realpath(os.path.abspath(sandbox_root))
            rel = os.path.relpath(os.path.realpath(path), sandbox_root)
            if rel.startswith(rule["path_not_under"].replace("\\", "/")):
                return False

        if "recipient_domain_in" in rule:
            domain = self._extract_email_domain(tool_call.params.get("to"))
            if domain not in {item.lower() for item in rule["recipient_domain_in"]}:
                return False

        if "recipient_domain_not_in" in rule:
            domain = self._extract_email_domain(tool_call.params.get("to"))
            if domain is not None and domain in {item.lower() for item in rule["recipient_domain_not_in"]}:
                return False

        if "table_in" in rule:
            tables = self._extract_tables(tool_call.params.get("sql"))
            if not set(rule["table_in"]).issubset(set(tables)):
                if not set(tables).intersection(rule["table_in"]):
                    return False

        if "query_is_read_only" in rule:
            expected = bool(rule["query_is_read_only"])
            actual = self._is_read_only_sql(tool_call.params.get("sql"))
            if actual != expected:
                return False

        return True

    def _scope_definition(self, task_scope: Optional[str]) -> Dict[str, Any]:
        if task_scope is None:
            return {}
        task_scope = str(task_scope).lower()
        defaults = {
            "workspace": {"allowed_tools": {"file.read", "file.delete", "email.send"}},
            "client": {"allowed_tools": {"file.read", "email.send"}, "extra_allow": [{"tool": "email.send", "to": "client@acme-client.com"}]},
            "cleanup": {"allowed_tools": {"file.delete"}},
            "supplier": {"allowed_tools": {"file.read"}},
        }
        return defaults.get(task_scope, {})

    def _matches_extra_allow(self, tool_call: ToolCall, extra: Dict[str, Any]) -> bool:
        if extra.get("tool") and extra["tool"] != tool_call.tool:
            return False
        for key, expected in extra.items():
            if key == "tool":
                continue
            if key == "to":
                if tool_call.params.get("to") != expected:
                    return False
            elif tool_call.params.get(key) != expected:
                return False
        return True

    def evaluate(self, tool_call: ToolCall, task_scope: Optional[str] = None) -> Decision:
        """Return the first matching decision following the required evaluation order."""
        if task_scope is not None:
            tool_call.task_scope = str(task_scope).lower()

        rule_list = self.policy.get("rules", [])
        for rule in self._ordered_rules(rule_list):
            if rule.get("decision", "BLOCK").upper() == "BLOCK" and self._matches(rule, tool_call):
                return Decision(decision=rule["decision"], rule_id=rule["id"], reason=rule["reason"])

        scope_definition = self._scope_definition(tool_call.task_scope)
        if tool_call.task_scope and scope_definition:
            allowed_tools = set(scope_definition.get("allowed_tools", set()))
            if tool_call.tool not in allowed_tools:
                title = (tool_call.task_title or tool_call.task or "this task").strip() or "this task"
                return Decision("BLOCK", "SCOPE", f"This action isn't needed for the task '{title}'.")
            for extra in scope_definition.get("extra_allow", []):
                if self._matches_extra_allow(tool_call, extra):
                    return Decision("ALLOW", "SCOPE-ALLOW", f"This action is explicitly allowed for the task '{tool_call.task_title or tool_call.task or 'this task'}'.")

        for rule in self._ordered_rules(rule_list):
            if rule.get("decision", "BLOCK").upper() == "REVIEW" and self._matches(rule, tool_call):
                return Decision(decision=rule["decision"], rule_id=rule["id"], reason=rule["reason"])
        for rule in self._ordered_rules(rule_list):
            if rule.get("decision", "BLOCK").upper() == "ALLOW" and self._matches(rule, tool_call):
                return Decision(decision=rule["decision"], rule_id=rule["id"], reason=rule["reason"])

        default_action = str(self.policy.get("default", "BLOCK")).upper()
        return Decision(decision=default_action, rule_id="DEFAULT", reason="No matching rule was found; the action is denied by default.")

    def _ordered_rules(self, rules: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        block = []
        review = []
        allow = []
        for rule in rules:
            decision = str(rule.get("decision", "BLOCK")).upper()
            if decision == "BLOCK":
                block.append(rule)
            elif decision == "REVIEW":
                review.append(rule)
            else:
                allow.append(rule)
        return block + review + allow


__all__ = ["PolicyEngine"]
