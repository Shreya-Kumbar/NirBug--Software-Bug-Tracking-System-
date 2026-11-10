"""Business-logic (service) layer.

Controllers (routes) call these services; services use repositories and domain
objects. Errors are reported with ServiceError(message, http_status).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..db import (AuditRepository, BugRepository, CommentRepository, Database, HistoryRepository,
                  NotificationRepository, ProjectRepository, ReleaseRepository, UserRepository)
from ..domain import (Bug, BugStateMachine, InvalidTransition, Role, Severity, Status, User,
                      derive_priority)
from ..ml.classifier import BugIntelligence
from .. import security
from .assignment import STRATEGIES
from .events import AuditListener, EventBus, NotificationListener


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def row_to_user(row: dict) -> User:
    return User(id=row["id"], username=row["username"], email=row["email"], role=Role(row["role"]),
                password_hash=row["password_hash"], skills=row.get("skills") or "")


class Services:
    """Facade that wires repositories, event bus and services together (Dependency Injection)."""

    def __init__(self, db: Database, secret_key: str):
        self.db = db
        self.users = UserRepository(db)
        self.projects = ProjectRepository(db)
        self.releases = ReleaseRepository(db)
        self.bugs = BugRepository(db)
        self.comments = CommentRepository(db)
        self.history = HistoryRepository(db)
        self.audit = AuditRepository(db)
        self.notifications = NotificationRepository(db)
        self.tokens = security.TokenManager(secret_key)
        self.ai = BugIntelligence()
        self.events = EventBus()
        self.events.subscribe("*", AuditListener(self.audit))
        self.events.subscribe("*", NotificationListener(self.notifications))
        self.auth = AuthService(self)
        self.bug_service = BugService(self)
        self.analytics = AnalyticsService(self)


class AuthService:
    def __init__(self, s: Services):
        self.s = s

    def register(self, username: str, email: str, password: str, role: str = "REPORTER",
                 skills: str = "", by_admin: bool = False) -> dict:
        username = (username or "").strip()
        if not (3 <= len(username) <= 30) or not username.replace("_", "").isalnum():
            raise ServiceError("Username must be 3-30 letters, digits or _")
        if not security.valid_email(email):
            raise ServiceError("Invalid e-mail address")
        problems = security.password_problems(password or "")
        if problems:
            raise ServiceError("Password needs " + ", ".join(problems))
        if role not in Role.__members__:
            raise ServiceError("Invalid role")
        if not by_admin and role != "REPORTER":
            role = "REPORTER"  # self-registration can never grant privileged roles
        if self.s.users.by_username(username):
            raise ServiceError("Username already taken", 409)
        if self.s.db.one("SELECT id FROM users WHERE email = ?", (email,)):
            raise ServiceError("E-mail already registered", 409)
        uid = self.s.users.create(username=username, email=email, role=role, skills=skills,
                                  password_hash=security.hash_password(password))
        self.s.events.publish("user.registered", actor_id=uid, detail=f"{username} ({role})")
        return row_to_user(self.s.users.get(uid)).to_public()

    def login(self, username: str, password: str, ip: str = None) -> dict:
        row = self.s.users.by_username(username or "")
        if not row:
            raise ServiceError("Invalid username or password", 401)
        if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > datetime.utcnow():
            raise ServiceError("Account locked due to failed logins. Try again later.", 423)
        if not security.verify_password(row["password_hash"], password or ""):
            fails = row["failed_logins"] + 1
            lock = None
            if fails >= security.MAX_FAILED_LOGINS:
                lock = (datetime.utcnow() + timedelta(minutes=security.LOCKOUT_MINUTES)).isoformat()
                fails = 0
            self.s.users.update(row["id"], failed_logins=fails, locked_until=lock)
            self.s.events.publish("auth.login_failed", actor_id=row["id"], ip=ip, detail=username)
            raise ServiceError("Invalid username or password", 401)
        self.s.users.update(row["id"], failed_logins=0, locked_until=None)
        self.s.events.publish("auth.login", actor_id=row["id"], ip=ip, detail=username)
        user = row_to_user(row)
        return {"token": self.s.tokens.issue(user.id, user.role.value), "user": user.to_public()}

    def user_from_token(self, token: str) -> Optional[User]:
        data = self.s.tokens.verify(token or "")
        if not data:
            return None
        row = self.s.users.get(data["uid"])
        return row_to_user(row) if row else None


class BugService:
    def __init__(self, s: Services):
        self.s = s

    def _get(self, bug_id: int) -> dict:
        bug = self.s.bugs.detail(bug_id)
        if not bug:
            raise ServiceError("Bug not found", 404)
        return bug

    def _record(self, bug_id, actor_id, field, old, new):
        self.s.history.create(bug_id=bug_id, actor_id=actor_id, field=field,
                              old_value=str(old) if old is not None else None,
                              new_value=str(new) if new is not None else None)

    def analyze(self, project_id: int, title: str, description: str) -> dict:
        """AI preview: predicted severity + possible duplicates (used before submitting)."""
        sev, conf = self.s.ai.predict_severity(f"{title} {description}")
        dups = self.s.ai.find_duplicates(f"{title} {description}", self.s.bugs.open_bugs(project_id))
        return {"severity": sev, "confidence": conf, "duplicates": dups,
                "component": self.s.ai.guess_component(f"{title} {description}")}

    def create(self, actor: User, data: dict, ip=None) -> dict:
        if not actor.can("create_bug"):
            raise ServiceError("Not allowed", 403)
        title = (data.get("title") or "").strip()
        desc = (data.get("description") or "").strip()
        if len(title) < 5 or len(title) > 200:
            raise ServiceError("Title must be 5-200 characters")
        if len(desc) < 10:
            raise ServiceError("Description must be at least 10 characters")
        project_id = int(data.get("project_id") or 0)
        if not self.s.projects.get(project_id):
            raise ServiceError("Project not found", 404)

        ai_sev, ai_conf = self.s.ai.predict_severity(f"{title} {desc}")
        sev_value = data.get("severity") or ai_sev  # user choice wins, AI fills the gap
        if sev_value not in Severity.__members__:
            raise ServiceError("Invalid severity")
        severity = Severity(sev_value)
        target_release = data.get("target_release_id") or None
        priority = derive_priority(severity, blocks_release=bool(target_release))
        component = (data.get("component") or self.s.ai.guess_component(f"{title} {desc}")).lower()

        bug_id = self.s.bugs.create(
            project_id=project_id, title=title, description=desc, severity=severity.value,
            priority=priority.value, status=Status.NEW.value, component=component,
            reporter_id=actor.id, found_in_version=data.get("found_in_version", ""),
            target_release_id=target_release, ai_severity=ai_sev, ai_confidence=ai_conf)
        self._record(bug_id, actor.id, "status", None, "NEW")
        self.s.events.publish("bug.created", actor_id=actor.id, ip=ip,
                              detail=f"#{bug_id} {title} [{severity.value}]")
        return self._get(bug_id)

    def update_fields(self, actor: User, bug_id: int, data: dict) -> dict:
        bug = self._get(bug_id)
        if not (actor.can("assign_bug") or actor.id == bug["reporter_id"]):
            raise ServiceError("Only managers or the reporter may edit this bug", 403)
        changes = {}
        for f in ("title", "description", "component", "severity", "target_release_id", "found_in_version"):
            if f in data and data[f] != bug[f]:
                changes[f] = data[f]
        if "severity" in changes:
            if changes["severity"] not in Severity.__members__:
                raise ServiceError("Invalid severity")
            changes["priority"] = derive_priority(
                Severity(changes["severity"]),
                bool(changes.get("target_release_id", bug["target_release_id"]))).value
        for f, v in changes.items():
            self._record(bug_id, actor.id, f, bug[f], v)
        self.s.bugs.update(bug_id, **changes)
        return self._get(bug_id)

    def assign(self, actor: User, bug_id: int, assignee_id: Optional[int] = None,
               strategy: str = "skill_based", ip=None) -> dict:
        if not actor.can("assign_bug"):
            raise ServiceError("Only managers can assign bugs", 403)
        bug = self._get(bug_id)
        if assignee_id is None:
            strat = STRATEGIES.get(strategy)
            if not strat:
                raise ServiceError("Unknown strategy")
            assignee_id = strat.choose(self.s.users.developers_workload(), bug)
            if assignee_id is None:
                raise ServiceError("No developers available")
        dev = self.s.users.get(int(assignee_id))
        if not dev or dev["role"] != "DEVELOPER":
            raise ServiceError("Assignee must be a developer")
        if bug["status"] in ("NEW", "REOPENED"):
            BugStateMachine.validate(Status(bug["status"]), Status.ASSIGNED, actor.role)
            self._record(bug_id, actor.id, "status", bug["status"], "ASSIGNED")
            self.s.bugs.update(bug_id, status="ASSIGNED")
        self._record(bug_id, actor.id, "assignee", bug["assignee_name"], dev["username"])
        self.s.bugs.update(bug_id, assignee_id=dev["id"])
        self.s.events.publish("bug.assigned", actor_id=actor.id, ip=ip, notify=[dev["id"]],
                              detail=f"#{bug_id} -> {dev['username']}",
                              message=f"Bug #{bug_id} '{bug['title']}' was assigned to you")
        return self._get(bug_id)

    def change_status(self, actor: User, bug_id: int, target: str, ip=None,
                      duplicate_of: Optional[int] = None) -> dict:
        bug = self._get(bug_id)
        if target not in Status.__members__:
            raise ServiceError("Invalid status")
        if actor.role == Role.DEVELOPER and bug["assignee_id"] != actor.id:
            raise ServiceError("Developers can only update bugs assigned to them", 403)
        entity = Bug(id=bug_id, project_id=bug["project_id"], title=bug["title"],
                     description=bug["description"], reporter_id=bug["reporter_id"],
                     status=Status(bug["status"]))
        try:
            old = entity.transition(Status(target), actor)
        except InvalidTransition as e:
            raise ServiceError(str(e), 409)
        upd = {"status": target}
        if target == "DUPLICATE":
            if not duplicate_of or not self.s.bugs.get(int(duplicate_of)):
                raise ServiceError("Specify a valid original bug id")
            upd["duplicate_of"] = int(duplicate_of)
        self.s.bugs.update(bug_id, **upd)
        self._record(bug_id, actor.id, "status", old.value, target)
        self.s.events.publish("bug.status_changed", actor_id=actor.id, ip=ip,
                              notify=[bug["reporter_id"], bug["assignee_id"]],
                              detail=f"#{bug_id} {old.value} -> {target}",
                              message=f"Bug #{bug_id} moved {old.value} -> {target}")
        return self._get(bug_id)

    def comment(self, actor: User, bug_id: int, body: str) -> dict:
        bug = self._get(bug_id)
        body = (body or "").strip()
        if not body or len(body) > 5000:
            raise ServiceError("Comment must be 1-5000 characters")
        cid = self.s.comments.create(bug_id=bug_id, author_id=actor.id, body=body)
        self.s.events.publish("bug.commented", actor_id=actor.id, detail=f"#{bug_id}",
                              notify=[u for u in (bug["reporter_id"], bug["assignee_id"]) if u != actor.id],
                              message=f"{actor.username} commented on bug #{bug_id}")
        return {"id": cid}

    def full(self, actor: User, bug_id: int) -> dict:
        bug = self._get(bug_id)
        bug["comments"] = self.s.comments.for_bug(bug_id)
        bug["history"] = self.s.history.for_bug(bug_id)
        bug["allowed_transitions"] = BugStateMachine.allowed_next(Status(bug["status"]), actor.role)
        return bug


class AnalyticsService:
    def __init__(self, s: Services):
        self.s = s

    def dashboard(self) -> dict:
        q = self.s.db.query
        by_status = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) n FROM bugs GROUP BY status")}
        by_sev = {r["severity"]: r["n"] for r in q("SELECT severity, COUNT(*) n FROM bugs GROUP BY severity")}
        trend = q("SELECT DATE(created_at) d, COUNT(*) n FROM bugs GROUP BY d ORDER BY d DESC LIMIT 14")
        mttr = self.s.db.one(
            "SELECT AVG(julianday(h.created_at) - julianday(b.created_at)) AS days FROM bugs b "
            "JOIN bug_history h ON h.bug_id = b.id AND h.field='status' AND h.new_value='CLOSED'")
        total = sum(by_status.values())
        open_ = sum(n for s, n in by_status.items() if s not in ("CLOSED", "REJECTED", "DUPLICATE", "VERIFIED"))
        ai_rows = q("SELECT severity, ai_severity FROM bugs WHERE ai_severity IS NOT NULL")
        ai_acc = (sum(r["severity"] == r["ai_severity"] for r in ai_rows) / len(ai_rows)) if ai_rows else None
        return {"total": total, "open": open_, "closed": total - open_,
                "critical_open": q("SELECT COUNT(*) n FROM bugs WHERE severity='CRITICAL' AND status NOT IN "
                                   "('CLOSED','REJECTED','DUPLICATE','VERIFIED')")[0]["n"],
                "by_status": by_status, "by_severity": by_sev, "trend": list(reversed(trend)),
                "workload": self.s.users.developers_workload(),
                "mttr_days": round(mttr["days"], 2) if mttr and mttr["days"] else None,
                "ai_agreement": round(ai_acc * 100, 1) if ai_acc is not None else None}

    def release_readiness(self, release_id: int) -> dict:
        rel = self.s.releases.get(release_id)
        if not rel:
            raise ServiceError("Release not found", 404)
        bugs = self.s.db.query("SELECT severity, status FROM bugs WHERE target_release_id = ?", (release_id,))
        done = [b for b in bugs if b["status"] in ("VERIFIED", "CLOSED", "REJECTED", "DUPLICATE")]
        blockers = [b for b in bugs if b not in done and b["severity"] in ("CRITICAL", "HIGH")]
        pct = round(100 * len(done) / len(bugs), 1) if bugs else 100.0
        return {**rel, "total": len(bugs), "resolved": len(done), "blockers": len(blockers),
                "percent": pct, "ready": not blockers}
