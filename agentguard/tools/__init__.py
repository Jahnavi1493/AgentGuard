"""Public package API for AgentGuard.

The package intentionally keeps raw function names private. The runner accesses
wrapped raw tools via a private mapping, not via module-level aliases.
"""

from .counters import wrap_raw_tool


def get_raw_tools():
    """Return the wrapped raw-tool mapping used by the checkpoint and baseline runs."""
    from ._db_tools import query_db
    from ._email_tools import send_email
    from ._file_tools import delete_file, read_file

    return {
        "file.read": wrap_raw_tool("file.read", read_file),
        "file.delete": wrap_raw_tool("file.delete", delete_file),
        "email.send": wrap_raw_tool("email.send", send_email),
        "db.query": wrap_raw_tool("db.query", query_db),
    }


RAW_TOOLS = get_raw_tools()

__all__ = []
