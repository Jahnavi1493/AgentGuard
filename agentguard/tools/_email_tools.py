from __future__ import annotations

from typing import List, Dict, Any

OUTBOX: List[Dict[str, Any]] = []


def send_email(to: str, subject: str = "", body: str = "") -> Dict[str, Any]:
    """Simulate sending an email without contacting the outside world."""
    mail = {"to": to, "subject": subject, "body": body, "sent": True}
    OUTBOX.append(mail)
    return mail


def get_outbox() -> List[Dict[str, Any]]:
    """Return the in-memory outbox snapshot."""
    return list(OUTBOX)


def clear_outbox() -> None:
    """Clear the in-memory outbox for a fresh run."""
    OUTBOX.clear()
