"""Audit logging utilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(slots=True)
class AuditEvent:
    """Represents a single audit log entry."""

    event_id: str
    user_id: str
    action: str
    resource: str
    timestamp: datetime = field(default_factory=_utcnow)
    details: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """Append-only in-memory logger for auditing sensitive actions."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def log(
        self,
        user_id: str,
        action: str,
        resource: str,
        details: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        """Record a new audit event and return the stored entry."""

        event = AuditEvent(
            event_id=str(uuid4()),
            user_id=user_id,
            action=action,
            resource=resource,
            details=dict(details or {}),
        )
        self._events.append(event)
        return event

    def query(self, filters: Mapping[str, Any] | None = None) -> list[AuditEvent]:
        """Return audit events that match the provided filters."""

        if not filters:
            return list(self._events)

        def matches(event: AuditEvent) -> bool:
            for attr, expected in filters.items():
                if getattr(event, attr, None) != expected:
                    return False
            return True

        return [event for event in self._events if matches(event)]


__all__ = ["AuditEvent", "AuditLogger"]
