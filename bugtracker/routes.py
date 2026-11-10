"""Presentation / controller layer: REST API (JSON over HTTP).

Each endpoint: authenticate -> authorise (RBAC) -> call a service -> return JSON.
"""
from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request

from .services.core import ServiceError

api = Blueprint("api", __name__, url_prefix="/api")


def svc():
    return current_app.config["SERVICES"]


def client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0]


def login_required(permission: str | None = None):
    """Decorator: checks the Bearer token and (optionally) an RBAC permission."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            user = svc().auth.user_from_token(token)
            if not user:
                return jsonify(error="Authentication required"), 401
            if permission and not user.can(permission):
                return jsonify(error="Forbidden: insufficient role"), 403
            g.user = user
            return fn(*a, **kw)
        return wrapper
    return deco


@api.errorhandler(ServiceError)
def handle_service_error(e: ServiceError):
    return jsonify(error=e.message), e.status


@api.before_request
def rate_limit():
    if request.endpoint == "api.login" and not current_app.config["LOGIN_LIMITER"].allow(client_ip()):
        return jsonify(error="Too many login attempts, slow down"), 429


def body() -> dict:
    return request.get_json(silent=True) or {}


# ------------------------------------------------------------------ auth
@api.post("/auth/register")
def register():
    d = body()
    return jsonify(svc().auth.register(d.get("username"), d.get("email"), d.get("password"))), 201


@api.post("/auth/login")
def login():
    d = body()
    return jsonify(svc().auth.login(d.get("username"), d.get("password"), ip=client_ip()))


@api.get("/auth/me")
@login_required()
def me():
    return jsonify(g.user.to_public())


# ------------------------------------------------------------------ users
@api.get("/users")
@login_required()
def list_users():
    return jsonify([{k: u[k] for k in ("id", "username", "email", "role", "skills")}
                    for u in svc().users.all()])


@api.post("/users")
@login_required("manage_users")
def create_user():
    d = body()
    return jsonify(svc().auth.register(d.get("username"), d.get("email"), d.get("password"),
                                       d.get("role", "REPORTER"), d.get("skills", ""), by_admin=True)), 201


# ------------------------------------------------------------------ projects & releases
@api.get("/projects")
@login_required()
def list_projects():
    projects = svc().projects.all()
    for p in projects:
        p["releases"] = svc().releases.for_project(p["id"])
    return jsonify(projects)


@api.post("/projects")
@login_required("manage_projects")
def create_project():
    d = body()
    name = (d.get("name") or "").strip()
    if len(name) < 2:
        raise ServiceError("Project name too short")
    if svc().db.one("SELECT id FROM projects WHERE name = ?", (name,)):
        raise ServiceError("Project already exists", 409)
    pid = svc().projects.create(name=name, description=d.get("description", ""))
    svc().events.publish("project.created", actor_id=g.user.id, detail=name)
    return jsonify(svc().projects.get(pid)), 201


@api.post("/projects/<int:pid>/releases")
@login_required("manage_releases")
def create_release(pid):
    d = body()
    if not svc().projects.get(pid):
        raise ServiceError("Project not found", 404)
    version = (d.get("version") or "").strip()
    if not version:
        raise ServiceError("Version required")
    rid = svc().releases.create(project_id=pid, version=version, release_date=d.get("release_date"))
    svc().events.publish("release.created", actor_id=g.user.id, detail=version)
    return jsonify(svc().releases.get(rid)), 201


@api.get("/releases/<int:rid>/readiness")
@login_required()
def release_readiness(rid):
    return jsonify(svc().analytics.release_readiness(rid))


@api.post("/releases/<int:rid>/ship")
@login_required("manage_releases")
def ship_release(rid):
    r = svc().analytics.release_readiness(rid)
    if not r["ready"]:
        raise ServiceError(f"Release blocked by {r['blockers']} open critical/high bug(s)", 409)
    svc().releases.update(rid, status="RELEASED")
    svc().events.publish("release.shipped", actor_id=g.user.id, detail=r["version"])
    return jsonify(svc().analytics.release_readiness(rid))


# ------------------------------------------------------------------ bugs
@api.get("/bugs")
@login_required()
def list_bugs():
    a = request.args
    assignee = g.user.id if a.get("mine") == "1" else a.get("assignee_id")
    return jsonify(svc().bugs.search(a.get("status"), a.get("severity"), a.get("project_id"),
                                     assignee, a.get("q")))


@api.post("/bugs/analyze")
@login_required()
def analyze_bug():
    d = body()
    return jsonify(svc().bug_service.analyze(int(d.get("project_id") or 0),
                                             d.get("title", ""), d.get("description", "")))


@api.post("/bugs")
@login_required("create_bug")
def create_bug():
    return jsonify(svc().bug_service.create(g.user, body(), ip=client_ip())), 201


@api.get("/bugs/<int:bid>")
@login_required()
def get_bug(bid):
    return jsonify(svc().bug_service.full(g.user, bid))


@api.patch("/bugs/<int:bid>")
@login_required()
def update_bug(bid):
    return jsonify(svc().bug_service.update_fields(g.user, bid, body()))


@api.post("/bugs/<int:bid>/assign")
@login_required("assign_bug")
def assign_bug(bid):
    d = body()
    return jsonify(svc().bug_service.assign(g.user, bid, d.get("assignee_id"),
                                            d.get("strategy", "skill_based"), ip=client_ip()))


@api.post("/bugs/<int:bid>/status")
@login_required()
def change_status(bid):
    d = body()
    return jsonify(svc().bug_service.change_status(g.user, bid, d.get("status", ""), ip=client_ip(),
                                                   duplicate_of=d.get("duplicate_of")))


@api.post("/bugs/<int:bid>/comments")
@login_required()
def add_comment(bid):
    return jsonify(svc().bug_service.comment(g.user, bid, body().get("body"))), 201


# ------------------------------------------------------------------ misc
@api.get("/dashboard")
@login_required()
def dashboard():
    return jsonify(svc().analytics.dashboard())


@api.get("/audit")
@login_required("view_audit")
def audit():
    return jsonify(svc().audit.recent())


@api.get("/notifications")
@login_required()
def notifications():
    return jsonify(svc().notifications.for_user(g.user.id))


@api.post("/notifications/read")
@login_required()
def notifications_read():
    svc().db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (g.user.id,))
    return jsonify(ok=True)


@api.get("/health")
def health():
    return jsonify(status="ok")
