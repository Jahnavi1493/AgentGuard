from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class AuditLogger:
    """Append-only JSONL logger for agent decisions and outcomes."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write_entry(self, entry: Dict[str, Any]) -> None:
        """Append a single audit record to the JSONL file."""
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def read_entries(self) -> list[Dict[str, Any]]:
        """Read every recorded audit line as a Python object."""
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
