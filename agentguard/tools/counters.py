"""Track raw tool invocations for the guarded runtime and the unprotected baseline."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, TypeVar

_CALL_COUNTS = defaultdict(int)


F = TypeVar("F", bound=Callable[..., Any])


def increment(tool_name: str) -> None:
    """Increase the counted number of calls for a tool."""
    _CALL_COUNTS[tool_name] += 1


def get_count(tool_name: str) -> int:
    """Read the current call count for a tool."""
    return _CALL_COUNTS.get(tool_name, 0)


def get_total_calls() -> int:
    """Return the total number of raw tool invocations recorded across all tools."""
    return sum(_CALL_COUNTS.values())


def reset_all() -> None:
    """Reset all call counts back to zero."""
    _CALL_COUNTS.clear()


def wrap_raw_tool(tool_name: str, func: F) -> F:
    """Wrap a raw tool so the counter increments on every real execution."""

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        increment(tool_name)
        return func(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


__all__ = ["increment", "get_count", "reset_all", "wrap_raw_tool"]
