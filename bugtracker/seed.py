"""Demo data so the app is not empty on first run.

All demo accounts use the password:  Demo@1234
"""
from .domain import User, Role

DEMO_PASSWORD = "Demo@1234"

USERS = [
    ("admin", "admin@nirbug.test", "ADMIN", ""),
    ("manager", "manager@nirbug.test", "MANAGER", ""),
    ("dev_alice", "alice@nirbug.test", "DEVELOPER", "ui,performance"),
    ("dev_bob", "bob@nirbug.test", "DEVELOPER", "auth,api,database"),
    ("dev_chen", "chen@nirbug.test", "DEVELOPER", "payment,notifications"),
    ("tester", "tester@nirbug.test", "TESTER", ""),
    ("reporter", "reporter@nirbug.test", "REPORTER", ""),
]

BUGS = [
    ("Login page crashes when password field is empty", "Steps: open /login, leave password blank, press Login. The page crashes with a white screen and console error.", "auth"),
    ("Dashboard takes 25 seconds to load", "With 5000 bugs in the system the dashboard page loads very slowly. CPU usage on server spikes to 100%.", "performance"),
    ("Typo in footer: 'Copyrite'", "The footer of every page says Copyrite instead of Copyright.", "ui"),
    ("Invoice total wrong when coupon applied", "Applying the coupon SAVE10 to an order of 200 shows a total of 200 instead of 180.", "payment"),
    ("Email notification link is broken", "Clicking the link in the assignment email leads to a 404 page.", "notifications"),
    ("API returns 500 when filtering by date", "GET /api/orders?from=2026-01-01 returns internal server error.", "api"),
    ("Button colours inconsistent on settings page", "Save button is blue while every other primary button is purple.", "ui"),
    ("Session expires after one minute", "Users are logged out after about one minute of inactivity, should be 30 minutes.", "auth"),
]


def seed_demo_data(s) -> None:
    ids = {}
    for name, email, role, skills in USERS:
        ids[name] = s.auth.register(name, email, DEMO_PASSWORD, role, skills, by_admin=True)["id"]
    shop = s.projects.create(name="ShopEase Web", description="E-commerce web application")
    s.projects.create(name="ShopEase Mobile", description="Android / iOS app")
    r1 = s.releases.create(project_id=shop, version="v1.0", status="RELEASED", release_date="2026-09-01")
    r2 = s.releases.create(project_id=shop, version="v1.1", release_date="2026-12-15")

    def u(name):
        row = s.users.get(ids[name])
        return User(id=row["id"], username=row["username"], email=row["email"], role=Role(row["role"]))

    created = []
    for i, (title, desc, comp) in enumerate(BUGS):
        b = s.bug_service.create(u("reporter" if i % 2 else "tester"),
                                 {"project_id": shop, "title": title, "description": desc,
                                  "component": comp, "target_release_id": r2 if i < 5 else None,
                                  "found_in_version": "v1.0"})
        created.append(b["id"])
    mgr, dev, qa = u("manager"), u("dev_bob"), u("tester")
    # walk a few bugs through the lifecycle so every state appears
    for bid in created[:6]:
        s.bug_service.assign(mgr, bid)
    b0 = s.bugs.get(created[0])
    d0 = u(s.users.get(b0["assignee_id"])["username"])
    s.bug_service.change_status(d0, created[0], "IN_PROGRESS")
    s.bug_service.change_status(d0, created[0], "FIXED")
    s.bug_service.change_status(qa, created[0], "IN_TESTING")
    s.bug_service.change_status(qa, created[0], "VERIFIED")
    s.bug_service.change_status(qa, created[0], "CLOSED")
    d2 = u(s.users.get(s.bugs.get(created[2])["assignee_id"])["username"])
    s.bug_service.change_status(d2, created[2], "IN_PROGRESS")
    s.bug_service.comment(d2, created[2], "Reproduced, fixing the footer template now.")
    _ = (r1, dev)
