"""INTEGRATION TESTS - service layer + repositories + real (in-memory) SQLite database."""
import pytest

from bugtracker.domain import Role, User
from bugtracker.services.core import ServiceError, row_to_user


def u(services, name) -> User:
    return row_to_user(services.users.by_username(name))


def new_bug(services, actor="reporter", **kw):
    data = {"project_id": 1, "title": "Checkout page shows blank screen",
            "description": "After clicking pay the page becomes blank", **kw}
    return services.bug_service.create(u(services, actor), data)


def test_it01_create_bug_persists_with_ai_fields(services):
    b = new_bug(services)
    row = services.bugs.get(b["id"])
    assert row["status"] == "NEW" and row["ai_severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert services.history.for_bug(b["id"])[0]["new_value"] == "NEW"


def test_it02_validation_rejects_short_title(services):
    with pytest.raises(ServiceError):
        new_bug(services, title="bad")


def test_it03_auto_assign_skill_based(services):
    b = new_bug(services, component="payment")
    r = services.bug_service.assign(u(services, "manager"), b["id"])
    assert r["assignee_name"] == "dev_chen" and r["status"] == "ASSIGNED"


def test_it04_developer_cannot_assign(services):
    b = new_bug(services)
    with pytest.raises(ServiceError) as e:
        services.bug_service.assign(u(services, "dev_bob"), b["id"])
    assert e.value.status == 403


def test_it05_full_lifecycle_and_history(services):
    b = new_bug(services, component="auth")
    mgr, qa = u(services, "manager"), u(services, "tester")
    b = services.bug_service.assign(mgr, b["id"], assignee_id=services.users.by_username("dev_bob")["id"])
    dev = u(services, "dev_bob")
    for actor, st in [(dev, "IN_PROGRESS"), (dev, "FIXED"), (qa, "IN_TESTING"), (qa, "VERIFIED"), (qa, "CLOSED")]:
        b = services.bug_service.change_status(actor, b["id"], st)
    assert b["status"] == "CLOSED"
    statuses = [h["new_value"] for h in services.history.for_bug(b["id"]) if h["field"] == "status"]
    assert statuses == ["NEW", "ASSIGNED", "IN_PROGRESS", "FIXED", "IN_TESTING", "VERIFIED", "CLOSED"]


def test_it06_developer_cannot_touch_others_bug(services):
    b = new_bug(services, component="payment")
    services.bug_service.assign(u(services, "manager"), b["id"])  # -> dev_chen
    with pytest.raises(ServiceError) as e:
        services.bug_service.change_status(u(services, "dev_bob"), b["id"], "IN_PROGRESS")
    assert e.value.status == 403


def test_it07_invalid_transition_returns_409(services):
    b = new_bug(services)
    with pytest.raises(ServiceError) as e:
        services.bug_service.change_status(u(services, "manager"), b["id"], "CLOSED")
    assert e.value.status == 409


def test_it08_observer_writes_audit_and_notification(services):
    b = new_bug(services, component="payment")
    services.bug_service.assign(u(services, "manager"), b["id"])
    chen = services.users.by_username("dev_chen")["id"]
    assert any(f"#{b['id']}" in n["message"] for n in services.notifications.for_user(chen))
    assert any(a["action"] == "bug.assigned" for a in services.audit.recent())


def test_it09_mark_duplicate(services):
    a, b = new_bug(services), new_bug(services)
    r = services.bug_service.change_status(u(services, "tester"), b["id"], "DUPLICATE", duplicate_of=a["id"])
    assert r["status"] == "DUPLICATE" and r["duplicate_of"] == a["id"]


def test_it10_release_readiness_blocks_on_critical(services):
    rid = services.releases.create(project_id=1, version="v9")
    new_bug(services, title="Server crashes on checkout", target_release_id=rid)
    r = services.analytics.release_readiness(rid)
    assert r["blockers"] == 1 and r["ready"] is False


def test_it11_login_lockout_after_5_failures(services):
    for _ in range(5):
        with pytest.raises(ServiceError):
            services.auth.login("tester", "wrong")
    with pytest.raises(ServiceError) as e:
        services.auth.login("tester", "Demo@1234")
    assert e.value.status == 423


def test_it12_self_registration_cannot_escalate_role(services):
    r = services.auth.register("hacker", "h@x.io", "GoodPass1", role="ADMIN")
    assert r["role"] == "REPORTER"


def test_it13_workload_view(services):
    w = {r["username"]: r for r in services.users.developers_workload()}
    assert set(w) == {"dev_alice", "dev_bob", "dev_chen"}
    assert all(r["load_score"] >= 0 for r in w.values())


def test_it14_dashboard_totals_consistent(services):
    d = services.analytics.dashboard()
    assert d["total"] == d["open"] + d["closed"] == sum(d["by_status"].values())


def test_it15_sql_injection_in_search_is_harmless(services):
    rows = services.bugs.search(q="' OR 1=1; DROP TABLE bugs; --")
    assert rows == [] and services.bugs.all()
