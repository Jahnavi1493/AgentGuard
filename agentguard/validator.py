from __future__ import annotations

import os
from typing import Any, Dict

from .models import ToolCall

KNOWN_TOOLS = {
    "file.read",
    "file.delete",
    "email.send",
    "db.query",
}

REQUIRED_PARAMS = {
    "file.read": ["path"],
    "file.delete": ["path"],
    "email.send": ["to"],
    "db.query": ["sql"],
}


class ValidationError(ValueError):
    """Raised when a proposed tool call fails validation."""


def _normalise_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("Email address must be a string.")
    if not value or not "@" in value:
        raise ValidationError("Email address is missing a local-part or domain.")
    local, domain = value.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


def _resolve_and_check_path(sandbox_root: str, raw_path: Any) -> str:
    if not isinstance(raw_path, str):
        raise ValidationError("File path must be a string.")
    if not raw_path.strip():
        raise ValidationError("File path is empty.")

    if ".." in raw_path.split(os.sep):
        raise ValidationError("File path contains a traversal segment.")

    candidate = raw_path
    if not os.path.isabs(candidate):
        candidate = os.path.join(sandbox_root, candidate)

    real_candidate = os.path.realpath(candidate)
    sandbox_real = os.path.realpath(sandbox_root)

    try:
        common = os.path.commonpath([sandbox_real, real_candidate])
    except ValueError as exc:  # Different drives on Windows.
        raise ValidationError("File path is outside the sandbox.") from exc

    if common != sandbox_real:
        raise ValidationError("File path escapes the sandbox.")

    return real_candidate


def validate_and_normalise(tool_call: ToolCall, sandbox_root: str) -> ToolCall:
    """Validate tool names, required params, and sandbox-safe paths."""
    if not isinstance(tool_call, ToolCall):
        raise ValidationError("ToolCall object is required.")

    if tool_call.tool not in KNOWN_TOOLS:
        raise ValidationError(f"Unknown tool: {tool_call.tool}")

    params = dict(tool_call.params or {})
    for key in REQUIRED_PARAMS.get(tool_call.tool, []):
        if key not in params:
            raise ValidationError(f"Missing required parameter: {key}")

    if tool_call.tool in {"file.read", "file.delete"}:
        params["path"] = _resolve_and_check_path(sandbox_root, params.get("path"))
    elif tool_call.tool == "email.send":
        params["to"] = _normalise_email(params.get("to"))
    elif tool_call.tool == "db.query":
        sql = params.get("sql")
        if not isinstance(sql, str):
            raise ValidationError("SQL query must be a string.")
        if not sql.strip():
            raise ValidationError("SQL query cannot be empty.")
        params["sql"] = sql.strip()

    tool_call.params = params
    return tool_call


__all__ = ["KNOWN_TOOLS", "ValidationError", "validate_and_normalise"]
