"""Domain model (OOP layer).

Enums, entity classes and the Bug lifecycle *State Machine*.
Pure Python - no Flask, no SQL - so it can be unit tested in isolation
(Separation of Concerns / layered architecture).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    REPORTER = "REPORTER"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def weight(self) -> int:
        return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}[self.value]


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Status(str, Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    IN_TESTING = "IN_TESTING"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


CLOSED_STATES = {Status.CLOSED, Status.REJECTED, Status.DUPLICATE, Status.VERIFIED}


class InvalidTransition(Exception):
    """Raised when a bug is moved to a state not allowed by the lifecycle."""


class BugStateMachine:
    """Finite State Machine for the bug life cycle (table-driven State pattern).

    TRANSITIONS maps current status -> {allowed next status: roles allowed}.
    """

    _DEV = {Role.DEVELOPER, Role.MANAGER, Role.ADMIN}
    _QA = {Role.TESTER, Role.MANAGER, Role.ADMIN}
    _MGR = {Role.MANAGER, Role.ADMIN}

    TRANSITIONS: dict = {
        Status.NEW: {Status.ASSIGNED: _MGR, Status.REJECTED: _MGR, Status.DUPLICATE: _MGR | _QA},
        Status.ASSIGNED: {Status.IN_PROGRESS: _DEV, Status.REJECTED: _MGR | _DEV},
        Status.IN_PROGRESS: {Status.FIXED: _DEV, Status.ASSIGNED: _MGR},
        Status.FIXED: {Status.IN_TESTING: _QA},
        Status.IN_TESTING: {Status.VERIFIED: _QA, Status.REOPENED: _QA},
        Status.VERIFIED: {Status.CLOSED: _MGR | _QA},
        Status.REOPENED: {Status.ASSIGNED: _MGR, Status.IN_PROGRESS: _DEV},
        Status.CLOSED: {Status.REOPENED: _MGR | _QA},
        Status.REJECTED: {Status.NEW: _MGR},
        Status.DUPLICATE: {},
    }

    @classmethod
    def allowed_next(cls, current: Status, role: Role) -> list:
        return [s.value for s, roles in cls.TRANSITIONS.get(current, {}).items() if role in roles]

    @classmethod
    def validate(cls, current: Status, target: Status, role: Role) -> None:
        allowed = cls.TRANSITIONS.get(current, {})
        if target not in allowed:
            raise InvalidTransition(f"Cannot move bug from {current.value} to {target.value}")
        if role not in allowed[target]:
            raise InvalidTransition(
                f"Role {role.value} may not move bug from {current.value} to {target.value}")


def derive_priority(severity: Severity, blocks_release: bool = False) -> Priority:
    """Business rule: priority comes from severity, bumped one level if it blocks a release."""
    base = {Severity.CRITICAL: 1, Severity.HIGH: 2, Severity.MEDIUM: 3, Severity.LOW: 4}[severity]
    if blocks_release and base > 1:
        base -= 1
    return Priority(f"P{base}")


# Role Based Access Control matrix (action -> roles allowed)
PERMISSIONS = {
    "create_bug": {Role.ADMIN, Role.MANAGER, Role.DEVELOPER, Role.TESTER, Role.REPORTER},
    "assign_bug": {Role.ADMIN, Role.MANAGER},
    "manage_projects": {Role.ADMIN, Role.MANAGER},
    "manage_releases": {Role.ADMIN, Role.MANAGER},
    "manage_users": {Role.ADMIN},
    "view_audit": {Role.ADMIN, Role.MANAGER},
}


@dataclass
class User:
    id: Optional[int]
    username: str
    email: str
    role: Role
    password_hash: str = ""
    skills: str = ""  # comma separated components e.g. "ui,auth"

    def can(self, action: str) -> bool:
        return self.role in PERMISSIONS.get(action, set())

    def skill_set(self) -> set:
        return {s.strip().lower() for s in self.skills.split(",") if s.strip()}

    def to_public(self) -> dict:
        return {"id": self.id, "username": self.username, "email": self.email,
                "role": self.role.value, "skills": self.skills}


@dataclass
class Bug:
    id: Optional[int]
    project_id: int
    title: str
    description: str
    reporter_id: int
    severity: Severity = Severity.MEDIUM
    priority: Priority = Priority.P3
    status: Status = Status.NEW
    component: str = "general"
    assignee_id: Optional[int] = None

    def transition(self, target: Status, actor: User) -> Status:
        BugStateMachine.validate(self.status, target, actor.role)
        old, self.status = self.status, target
        return old

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATES
