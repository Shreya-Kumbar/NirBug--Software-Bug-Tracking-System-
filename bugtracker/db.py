"""Data access layer (DBMS).

SQLite database, normalised schema (3NF), foreign keys, indexes, a trigger,
a view, and the Repository pattern so the rest of the code never writes SQL.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN','MANAGER','DEVELOPER','TESTER','REPORTER')),
    skills        TEXT DEFAULT '',
    failed_logins INTEGER DEFAULT 0,
    locked_until  TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS releases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED','RELEASED')),
    release_date TEXT,
    UNIQUE (project_id, version)
);

CREATE TABLE IF NOT EXISTS bugs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id        INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    severity          TEXT NOT NULL,
    priority          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'NEW',
    component         TEXT DEFAULT 'general',
    reporter_id       INTEGER NOT NULL REFERENCES users(id),
    assignee_id       INTEGER REFERENCES users(id),
    found_in_version  TEXT DEFAULT '',
    target_release_id INTEGER REFERENCES releases(id),
    ai_severity       TEXT,
    ai_confidence     REAL,
    duplicate_of      INTEGER REFERENCES bugs(id),
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bugs_status   ON bugs(status);
CREATE INDEX IF NOT EXISTS idx_bugs_assignee ON bugs(assignee_id);
CREATE INDEX IF NOT EXISTS idx_bugs_project  ON bugs(project_id);

CREATE TRIGGER IF NOT EXISTS trg_bugs_updated AFTER UPDATE ON bugs
BEGIN
    UPDATE bugs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id     INTEGER NOT NULL REFERENCES bugs(id) ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES users(id),
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bug_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id     INTEGER NOT NULL REFERENCES bugs(id) ON DELETE CASCADE,
    actor_id   INTEGER REFERENCES users(id),
    field      TEXT NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message    TEXT NOT NULL,
    is_read    INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW IF NOT EXISTS v_developer_workload AS
SELECT u.id AS user_id, u.username,
       COUNT(b.id) AS open_bugs,
       COALESCE(SUM(CASE b.severity WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
                                    WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 1 END), 0) AS load_score
FROM users u
LEFT JOIN bugs b ON b.assignee_id = u.id
     AND b.status IN ('ASSIGNED','IN_PROGRESS','REOPENED')
WHERE u.role = 'DEVELOPER'
GROUP BY u.id;
"""


class Database:
    """Thin wrapper around sqlite3 - one connection per Database object."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # All queries use ? placeholders -> protection against SQL injection.
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid


class Repository:
    """Generic repository: CRUD for one table (Repository design pattern)."""

    table: str = ""
    columns: tuple = ()

    def __init__(self, db: Database):
        self.db = db

    def get(self, id_: int) -> Optional[dict]:
        return self.db.one(f"SELECT * FROM {self.table} WHERE id = ?", (id_,))

    def all(self) -> list[dict]:
        return self.db.query(f"SELECT * FROM {self.table} ORDER BY id")

    def create(self, **data: Any) -> int:
        cols = [c for c in data if c in self.columns]
        sql = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return self.db.execute(sql, tuple(data[c] for c in cols))

    def update(self, id_: int, **data: Any) -> None:
        cols = [c for c in data if c in self.columns]
        if not cols:
            return
        sets = ", ".join(f"{c} = ?" for c in cols)
        self.db.execute(f"UPDATE {self.table} SET {sets} WHERE id = ?",
                        tuple(data[c] for c in cols) + (id_,))

    def delete(self, id_: int) -> None:
        self.db.execute(f"DELETE FROM {self.table} WHERE id = ?", (id_,))


class UserRepository(Repository):
    table = "users"
    columns = ("username", "email", "password_hash", "role", "skills", "failed_logins", "locked_until")

    def by_username(self, username: str) -> Optional[dict]:
        return self.db.one("SELECT * FROM users WHERE username = ?", (username,))

    def developers_workload(self) -> list[dict]:
        return self.db.query(
            "SELECT w.*, u.skills FROM v_developer_workload w JOIN users u ON u.id = w.user_id")


class ProjectRepository(Repository):
    table = "projects"
    columns = ("name", "description")


class ReleaseRepository(Repository):
    table = "releases"
    columns = ("project_id", "version", "status", "release_date")

    def for_project(self, project_id: int) -> list[dict]:
        return self.db.query("SELECT * FROM releases WHERE project_id = ? ORDER BY id", (project_id,))


class BugRepository(Repository):
    table = "bugs"
    columns = ("project_id", "title", "description", "severity", "priority", "status", "component",
               "reporter_id", "assignee_id", "found_in_version", "target_release_id",
               "ai_severity", "ai_confidence", "duplicate_of")

    BASE = """SELECT b.*, p.name AS project_name, r.username AS reporter_name,
                     a.username AS assignee_name, rl.version AS target_version
              FROM bugs b
              JOIN projects p ON p.id = b.project_id
              JOIN users r ON r.id = b.reporter_id
              LEFT JOIN users a ON a.id = b.assignee_id
              LEFT JOIN releases rl ON rl.id = b.target_release_id"""

    def search(self, status=None, severity=None, project_id=None, assignee_id=None, q=None) -> list[dict]:
        where, params = [], []
        for col, val in (("b.status", status), ("b.severity", severity),
                         ("b.project_id", project_id), ("b.assignee_id", assignee_id)):
            if val not in (None, ""):
                where.append(f"{col} = ?")
                params.append(val)
        if q:
            where.append("(b.title LIKE ? OR b.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        sql = self.BASE + (" WHERE " + " AND ".join(where) if where else "") + \
            " ORDER BY b.priority ASC, b.id DESC"
        return self.db.query(sql, tuple(params))

    def detail(self, id_: int) -> Optional[dict]:
        return self.db.one(self.BASE + " WHERE b.id = ?", (id_,))

    def open_bugs(self, project_id: int) -> list[dict]:
        return self.db.query(
            "SELECT id, title, description FROM bugs WHERE project_id = ? "
            "AND status NOT IN ('CLOSED','REJECTED','DUPLICATE')", (project_id,))


class CommentRepository(Repository):
    table = "comments"
    columns = ("bug_id", "author_id", "body")

    def for_bug(self, bug_id: int) -> list[dict]:
        return self.db.query(
            "SELECT c.*, u.username FROM comments c JOIN users u ON u.id = c.author_id "
            "WHERE bug_id = ? ORDER BY c.id", (bug_id,))


class HistoryRepository(Repository):
    table = "bug_history"
    columns = ("bug_id", "actor_id", "field", "old_value", "new_value")

    def for_bug(self, bug_id: int) -> list[dict]:
        return self.db.query(
            "SELECT h.*, u.username FROM bug_history h LEFT JOIN users u ON u.id = h.actor_id "
            "WHERE bug_id = ? ORDER BY h.id", (bug_id,))


class AuditRepository(Repository):
    table = "audit_log"
    columns = ("user_id", "action", "detail", "ip_address")

    def recent(self, limit: int = 100) -> list[dict]:
        return self.db.query(
            "SELECT a.*, u.username FROM audit_log a LEFT JOIN users u ON u.id = a.user_id "
            "ORDER BY a.id DESC LIMIT ?", (limit,))


class NotificationRepository(Repository):
    table = "notifications"
    columns = ("user_id", "message", "is_read")

    def for_user(self, user_id: int) -> list[dict]:
        return self.db.query(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user_id,))
