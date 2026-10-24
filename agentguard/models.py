from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class ToolCall:
    """A structured tool invocation proposed by the mock agent."""

    tool: str
    params: Dict[str, Any]
    task: str
    timestamp: str
    id: str = field(default_factory=lambda: str(uuid4()))
    task_scope: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "params": self.params,
            "task": self.task,
            "timestamp": self.timestamp,
            "task_scope": self.task_scope,
            "task_id": self.task_id,
            "task_title": self.task_title,
        }


@dataclass
class Decision:
    """Decision produced by the policy engine."""

    decision: str
    rule_id: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "rule_id": self.rule_id,
            "reason": self.reason,
        }


@dataclass
class AuditEntry:
    """A single append-only audit event."""

    request_id: str
    timestamp: str
    tool: str
    params: Dict[str, Any]
    decision: str
    rule_id: str
    reason: str
    approver: Optional[str]
    review_status: Optional[str]
    outcome: str
    mode: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "tool": self.tool,
            "params": self.params,
            "decision": self.decision,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "approver": self.approver,
            "review_status": self.review_status,
            "outcome": self.outcome,
            "mode": self.mode,
        }
