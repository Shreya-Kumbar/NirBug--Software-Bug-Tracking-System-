"""Observer pattern: an in-process event bus.

Services publish events ("bug.created", "bug.status_changed", ...) and
listeners (audit logger, notifier) subscribe to them. Publishers do not know
who listens -> low coupling, easy to add e.g. an e-mail notifier later.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self):
        self._subs: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._subs[event].append(handler)

    def publish(self, event: str, **payload) -> None:
        for handler in self._subs[event] + self._subs["*"]:
            handler(event, **payload)


class AuditListener:
    """Writes every event into the audit_log table (accountability / non-repudiation)."""

    def __init__(self, audit_repo):
        self.repo = audit_repo

    def __call__(self, event, actor_id=None, detail="", ip=None, **_):
        self.repo.create(user_id=actor_id, action=event, detail=detail, ip_address=ip)


class NotificationListener:
    """Sends in-app notifications to the people affected by a bug event."""

    def __init__(self, notif_repo):
        self.repo = notif_repo

    def __call__(self, event, notify=(), message="", **_):
        for uid in set(u for u in notify if u):
            self.repo.create(user_id=uid, message=message)
