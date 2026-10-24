from __future__ import annotations

import time
from typing import Any, Dict, Optional


class ReviewRequest:
    """Represents one pending tool call waiting for manual approval."""

    def __init__(self, request_id: str, tool_name: str, params: Dict[str, Any], decision: Dict[str, str], mode: str):
        self.request_id = request_id
        self.tool_name = tool_name
        self.params = params
        self.decision = decision
        self.mode = mode
        self.status = "pending"
        self.approver = None
        self.created_at = time.time()
        self.timeout_seconds = 120

    def expired(self) -> bool:
        return (time.time() - self.created_at) >= self.timeout_seconds

    def approve(self, approver_name: str) -> None:
        self.status = "approved"
        self.approver = approver_name

    def deny(self) -> None:
        self.status = "denied"

    def timed_out(self) -> None:
        self.status = "timed_out"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool": self.tool_name,
            "params": self.params,
            "decision": self.decision,
            "status": self.status,
            "approver": self.approver,
            "timeout_seconds": self.timeout_seconds,
            "seconds_remaining": max(0, self.timeout_seconds - int(time.time() - self.created_at)),
        }


class ApprovalQueue:
    """Keeps track of REVIEW items and their lifecycle."""

    def __init__(self):
        self._items: Dict[str, ReviewRequest] = {}

    def add(self, request_id: str, tool_name: str, params: Dict[str, Any], decision: Dict[str, str], mode: str) -> ReviewRequest:
        request = ReviewRequest(request_id, tool_name, params, decision, mode)
        self._items[request_id] = request
        return request

    def get(self, request_id: str) -> Optional[ReviewRequest]:
        return self._items.get(request_id)

    def pending(self) -> list[ReviewRequest]:
        return [item for item in self._items.values() if item.status == "pending"]

    def approve(self, request_id: str, approver_name: str) -> Optional[ReviewRequest]:
        request = self._items.get(request_id)
        if request is None or request.status != "pending":
            return None
        request.approve(approver_name)
        return request

    def deny(self, request_id: str) -> Optional[ReviewRequest]:
        request = self._items.get(request_id)
        if request is None or request.status != "pending":
            return None
        request.deny()
        return request

    def timed_out(self, request_id: str) -> Optional[ReviewRequest]:
        request = self._items.get(request_id)
        if request is None or request.status != "pending":
            return None
        request.timed_out()
        return request

    def list(self) -> list[Dict[str, Any]]:
        return [item.as_dict() for item in self._items.values()]

    def __len__(self) -> int:
        return len(self._items)
