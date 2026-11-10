"""SYSTEM TESTS - black-box tests through the HTTP REST API (whole system end-to-end)."""


def test_st01_health_and_index(client):
    assert client.get("/api/health").json == {"status": "ok"}
    assert b"BugSense" in client.get("/").data


def test_st02_requires_authentication(client):
    assert client.get("/api/bugs").status_code == 401
    assert client.get("/api/bugs", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_st03_register_then_login(client):
    r = client.post("/api/auth/register", json={"username": "newuser", "email": "n@x.io", "password": "GoodPass1"})
    assert r.status_code == 201 and r.json["role"] == "REPORTER"
    assert client.post("/api/auth/login", json={"username": "newuser", "password": "GoodPass1"}).status_code == 200


def test_st04_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={"username": "weak", "email": "w@x.io", "password": "123"})
    assert r.status_code == 400 and "Password" in r.json["error"]


def test_st05_end_to_end_bug_workflow(client, login):
    rep, mgr, qa = login("reporter"), login("manager"), login("tester")
    b = client.post("/api/bugs", headers=rep, json={
        "project_id": 1, "title": "Password reset email never arrives",
        "description": "Requested reset 5 times, no e-mail received"}).json
    assert b["status"] == "NEW" and b["component"] == "auth"
    b = client.post(f"/api/bugs/{b['id']}/assign", headers=mgr, json={}).json
    dev = login(b["assignee_name"])
    for h, st in [(dev, "IN_PROGRESS"), (dev, "FIXED"), (qa, "IN_TESTING"), (qa, "REOPENED"),
                  (dev, "IN_PROGRESS"), (dev, "FIXED"), (qa, "IN_TESTING"), (qa, "VERIFIED"), (qa, "CLOSED")]:
        r = client.post(f"/api/bugs/{b['id']}/status", headers=h, json={"status": st})
        assert r.status_code == 200, (st, r.json)
    detail = client.get(f"/api/bugs/{b['id']}", headers=rep).json
    assert detail["status"] == "CLOSED" and len(detail["history"]) >= 10


def test_st06_rbac_forbidden(client, login):
    rep = login("reporter")
    assert client.get("/api/audit", headers=rep).status_code == 403
    assert client.post("/api/projects", headers=rep, json={"name": "X"}).status_code == 403
    assert client.post("/api/users", headers=login("manager"), json={}).status_code == 403


def test_st07_ai_analyze_endpoint(client, login):
    r = client.post("/api/bugs/analyze", headers=login("reporter"), json={
        "project_id": 1, "title": "Session expires after one minute", "description": "logged out quickly"}).json
    assert r["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert any(d["title"].startswith("Session expires") for d in r["duplicates"])


def test_st08_xss_payload_stored_as_text(client, login):
    payload = "<script>alert(1)</script> injected title"
    b = client.post("/api/bugs", headers=login("reporter"), json={
        "project_id": 1, "title": payload, "description": "xss test description"}).json
    # API returns raw JSON text; the front-end escapes it before rendering (esc()).
    assert b["title"] == payload
    assert "Content-Security-Policy" in client.get("/").headers


def test_st09_security_headers(client):
    h = client.get("/api/health").headers
    assert h["X-Frame-Options"] == "DENY" and h["X-Content-Type-Options"] == "nosniff"


def test_st10_login_rate_limit(client):
    codes = [client.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code for _ in range(12)]
    assert 429 in codes


def test_st11_release_ship_blocked_then_allowed(client, login):
    mgr = login("manager")
    rel = client.post("/api/projects/1/releases", headers=mgr, json={"version": "v2.0"}).json
    b = client.post("/api/bugs", headers=mgr, json={"project_id": 1, "title": "Database corrupted on save",
                                                    "description": "data lost after save", "target_release_id": rel["id"]}).json
    assert client.post(f"/api/releases/{rel['id']}/ship", headers=mgr).status_code == 409
    client.post(f"/api/bugs/{b['id']}/status", headers=mgr, json={"status": "REJECTED"})
    r = client.post(f"/api/releases/{rel['id']}/ship", headers=mgr)
    assert r.status_code == 200 and r.json["status"] == "RELEASED"


def test_st12_filters_and_search(client, login):
    h = login("manager")
    crit = client.get("/api/bugs?severity=CRITICAL", headers=h).json
    assert crit and all(b["severity"] == "CRITICAL" for b in crit)
    assert all("Typo" in b["title"] for b in client.get("/api/bugs?q=Typo", headers=h).json)


def test_st13_notifications_flow(client, login):
    h = login("dev_alice")
    n = client.get("/api/notifications", headers=h).json
    assert n and any("assigned to you" in x["message"] for x in n)
    client.post("/api/notifications/read", headers=h)
    assert all(x["is_read"] for x in client.get("/api/notifications", headers=h).json)
