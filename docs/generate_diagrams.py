"""Generates all UML / design diagrams as PNG images using matplotlib.

Run:  python docs/generate_diagrams.py      -> docs/diagrams/*.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrams")
os.makedirs(OUT, exist_ok=True)
INK, BLUE, PURPLE, GREEN, ORANGE, GREY = "#1e293b", "#e0e7ff", "#ede9fe", "#dcfce7", "#ffedd5", "#f1f5f9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 10)
    ax.set_ylim(0, h * 10)
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", color=INK, pad=12)
    return fig, ax


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def box(ax, x, y, w, h, text, fc=BLUE, fs=9, bold=False, round_=True, ec=INK):
    style = "round,pad=0.02,rounding_size=1.2" if round_ else "square,pad=0.0"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=INK, wrap=True)


def arrow(ax, p1, p2, text="", style="-|>", dashed=False, color=INK, fs=7.5, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=12, color=color, lw=1.1,
                                 linestyle="--" if dashed else "-", connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 1.2, text, ha="center", fontsize=fs,
                color="#334155", bbox=dict(fc="white", ec="none", pad=0.5))


def actor(ax, x, y, name):
    ax.add_patch(plt.Circle((x, y + 9), 1.6, fc="white", ec=INK, lw=1.2))
    ax.plot([x, x], [y + 7.4, y + 3], color=INK, lw=1.2)
    ax.plot([x - 2.5, x + 2.5], [y + 6, y + 6], color=INK, lw=1.2)
    ax.plot([x, x - 2], [y + 3, y], color=INK, lw=1.2)
    ax.plot([x, x + 2], [y + 3, y], color=INK, lw=1.2)
    ax.text(x, y - 2.5, name, ha="center", fontsize=9, fontweight="bold")


def usecase(ax, x, y, text, w=24, h=6):
    ax.add_patch(Ellipse((x, y), w, h, fc=PURPLE, ec=INK, lw=1.1))
    ax.text(x, y, text, ha="center", va="center", fontsize=8)


# ------------------------------------------------------------------ 1. USE CASE
def use_case():
    fig, ax = canvas(13, 10, "Use Case Diagram – NirBug")
    ax.add_patch(FancyBboxPatch((25, 3), 80, 92, boxstyle="round,pad=0,rounding_size=2", fc="#fafafa", ec=INK))
    ax.text(65, 92, "NirBug System", ha="center", fontweight="bold", fontsize=11)
    ucs = {
        "login": (45, 85, "Login / Logout"), "register": (85, 85, "Register (self sign-up)"),
        "report": (45, 76, "Report Bug"),
        "ai": (85, 76, "AI Severity Prediction"), "dup": (85, 67, "Detect Duplicates"),
        "search": (45, 67, "Search & Filter Bugs"), "comment": (45, 58, "Comment on Bug"),
        "assign": (45, 49, "Assign Developer"), "auto": (85, 49, "Auto-assign (Strategy)"),
        "status": (45, 40, "Update Bug Status"), "verify": (45, 31, "Verify / Reopen Fix"),
        "release": (45, 22, "Manage Releases"), "ready": (85, 22, "Check Release Readiness"),
        "dash": (85, 36, "View Dashboard"), "users": (45, 12, "Manage Users"), "audit": (85, 12, "View Audit Log"),
    }
    for k, (x, y, t) in ucs.items():
        usecase(ax, x, y, t)
    actors = {"Reporter": (10, 72), "Developer": (10, 42), "Tester": (10, 22), "Manager": (120, 55), "Admin": (120, 15)}
    for n, (x, y) in actors.items():
        actor(ax, x, y, n)
    links = {"Reporter": ["login", "register", "report", "search", "comment"],
             "Developer": ["login", "status", "comment", "search"],
             "Tester": ["login", "verify", "report"],
             "Manager": ["login", "assign", "release", "dash", "audit"], "Admin": ["login", "users", "audit"]}
    for a, ucl in links.items():
        ax_, ay = actors[a]
        for u in ucl:
            x, y, _ = ucs[u]
            ex = x - 12 if ax_ < x else x + 12
            ax.plot([ax_ + (3 if ax_ < x else -3), ex], [ay + 6, y], color="#64748b", lw=0.8)
    for a, b, lbl in [("report", "ai", "«include»"), ("report", "dup", "«include»"),
                      ("assign", "auto", "«extend»"), ("release", "ready", "«include»")]:
        x1, y1, _ = ucs[a]
        x2, y2, _ = ucs[b]
        arrow(ax, (x1 + 12, y1), (x2 - 12, y2), lbl, dashed=True)
    ax.text(65, 6.5, "All actors log in. Only Reporters self-register; the Admin creates other accounts (Manage Users).",
            ha="center", fontsize=7.5, style="italic")
    ax.text(65, 4, "Generalisation: Admin ⊃ Manager ⊃ Developer/Tester ⊃ Reporter (every user can report bugs)",
            ha="center", fontsize=7.5, style="italic")
    save(fig, "01_use_case.png")


# ------------------------------------------------------------------ 2. CLASS
def uml_class(ax, x, y, w, name, attrs, ops, fc=BLUE, stereo=""):
    lh = 2.6
    h_name = 4.5 if not stereo else 6.5
    h_a, h_o = lh * max(1, len(attrs)) + 1, lh * max(1, len(ops)) + 1
    top = y
    ax.add_patch(plt.Rectangle((x, top - h_name), w, h_name, fc=fc, ec=INK, lw=1.1))
    if stereo:
        ax.text(x + w / 2, top - 2, stereo, ha="center", va="center", fontsize=7, style="italic")
    ax.text(x + w / 2, top - h_name + 2.2, name, ha="center", va="center", fontweight="bold", fontsize=9)
    ax.add_patch(plt.Rectangle((x, top - h_name - h_a), w, h_a, fc="white", ec=INK, lw=1.1))
    for i, a in enumerate(attrs):
        ax.text(x + 1, top - h_name - 1.8 - i * lh, a, fontsize=7, va="center")
    ax.add_patch(plt.Rectangle((x, top - h_name - h_a - h_o), w, h_o, fc="white", ec=INK, lw=1.1))
    for i, o in enumerate(ops):
        ax.text(x + 1, top - h_name - h_a - 1.8 - i * lh, o, fontsize=7, va="center")
    return (x, top - h_name - h_a - h_o, w, h_name + h_a + h_o)


def class_diagram():
    fig, ax = canvas(16, 11, "Class Diagram – Domain & Service Layer")
    C = {}
    C["User"] = uml_class(ax, 2, 104, 30, "User", ["- id: int", "- username: str", "- email: str", "- role: Role",
                          "- password_hash: str", "- skills: str"], ["+ can(action): bool", "+ skill_set(): set", "+ to_public(): dict"])
    C["Role"] = uml_class(ax, 2, 62, 22, "Role", ["ADMIN", "MANAGER", "DEVELOPER", "TESTER", "REPORTER"], [], GREY, "«enumeration»")
    C["Bug"] = uml_class(ax, 44, 104, 34, "Bug", ["- id: int", "- title: str", "- description: str", "- severity: Severity",
                         "- priority: Priority", "- status: Status", "- component: str", "- assignee_id: int"],
                         ["+ transition(target, actor): Status", "+ is_open(): bool"])
    C["SM"] = uml_class(ax, 44, 58, 34, "BugStateMachine", ["+ TRANSITIONS: dict"],
                        ["+ validate(cur, target, role)", "+ allowed_next(cur, role): list"], PURPLE)
    C["Sev"] = uml_class(ax, 26, 40, 20, "Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], ["+ weight(): int"], GREY, "«enumeration»")
    C["Status"] = uml_class(ax, 2, 32, 22, "Status", ["NEW, ASSIGNED, IN_PROGRESS,", "FIXED, IN_TESTING,", "VERIFIED, CLOSED,", "REOPENED, REJECTED, DUP"], [], GREY, "«enumeration»")
    C["BS"] = uml_class(ax, 90, 104, 34, "BugService", ["- repos, events, ai"], ["+ create(actor, data)", "+ assign(actor, id, strategy)",
                        "+ change_status(actor, id, s)", "+ comment(actor, id, body)", "+ analyze(title, desc)"], GREEN)
    C["Strat"] = uml_class(ax, 90, 62, 34, "AssignmentStrategy", [], ["+ choose(devs, bug): int"], PURPLE, "«abstract»")
    C["LL"] = uml_class(ax, 82, 38, 22, "LeastLoaded", [], ["+ choose()"], PURPLE)
    C["SB"] = uml_class(ax, 108, 38, 22, "SkillBased", [], ["+ choose()"], PURPLE)
    C["AI"] = uml_class(ax, 130, 104, 28, "BugIntelligence", ["- model: Pipeline"], ["+ predict_severity(t)", "+ find_duplicates(t, c)",
                        "+ guess_component(t)", "+ evaluate(): dict"], ORANGE)
    C["Repo"] = uml_class(ax, 130, 66, 28, "Repository", ["- db: Database", "- table: str"], ["+ get(id)", "+ create(**data)", "+ update(id, **d)"], GREEN, "«generic»")
    C["Bus"] = uml_class(ax, 130, 30, 28, "EventBus", ["- subs: dict"], ["+ subscribe(evt, h)", "+ publish(evt, **p)"], ORANGE)
    C["Aud"] = uml_class(ax, 52, 20, 26, "AuditListener", [], ["+ __call__(event)"], ORANGE)

    def mid(k, side):
        x, y, w, h = C[k]
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]
    arrow(ax, mid("User", "b"), mid("Role", "t"), "has", style="-|>")
    arrow(ax, mid("User", "r"), mid("Bug", "l"), "reports 1..*", style="-")
    arrow(ax, mid("Bug", "b"), mid("SM", "t"), "uses", dashed=True)
    arrow(ax, (50, C["Bug"][1]), mid("Sev", "t"), "", style="-|>")
    arrow(ax, (46, C["Bug"][1]), mid("Status", "r"), "", style="-|>", rad=0.2)
    arrow(ax, mid("BS", "l"), mid("Bug", "r"), "manages", style="-")
    arrow(ax, mid("BS", "b"), mid("Strat", "t"), "uses", dashed=True)
    arrow(ax, mid("LL", "t"), (100, C["Strat"][1]), "", style="-|>")
    arrow(ax, mid("SB", "t"), (114, C["Strat"][1]), "", style="-|>")
    arrow(ax, mid("BS", "r"), mid("AI", "l"), "uses", dashed=True)
    arrow(ax, (124, 92), mid("Repo", "t"), "uses", dashed=True)
    arrow(ax, (124, 82), mid("Bus", "t"), "", dashed=True, rad=-0.2)
    ax.text(150, 44, "publishes", fontsize=7.5, color="#334155")
    arrow(ax, mid("Aud", "r"), mid("Bus", "l"), "subscribes", dashed=True)
    ax.text(2, 3, "Legend:  ─▷ inheritance / association    - - -> dependency    Blue = entity, Purple = pattern, Green = service/repo, Orange = AI / events",
            fontsize=7.5, style="italic")
    save(fig, "02_class.png")


# ------------------------------------------------------------------ 3. SEQUENCE
def sequence():
    fig, ax = canvas(15, 10, "Sequence Diagram – Report a Bug (with AI Triage)")
    parts = ["Reporter", "Browser (SPA)", "Flask API", "BugService", "BugIntelligence", "Repository / DB", "EventBus"]
    xs = [8 + i * 22 for i in range(len(parts))]
    for x, p in zip(xs, parts):
        box(ax, x - 9, 90, 18, 6, p, BLUE if p != "Reporter" else GREY, fs=8, bold=True)
        ax.plot([x, x], [8, 90], ls="--", color="#94a3b8", lw=0.9)
    msgs = [(0, 1, "fill form (title, description)"), (1, 2, "POST /api/bugs/analyze"), (2, 3, "analyze()"),
            (3, 4, "predict_severity(text)"), (4, 3, "HIGH, 0.81", True), (3, 4, "find_duplicates(text, open)"),
            (4, 3, "[#8 65%]", True), (3, 1, "AI suggestion shown", True), (0, 1, "Submit"),
            (1, 2, "POST /api/bugs + Bearer token"), (2, 2, "verify token, RBAC"), (2, 3, "create(actor, data)"),
            (3, 3, "validate input, derive_priority()"), (3, 5, "INSERT bugs, bug_history"), (5, 3, "bug id", True),
            (3, 6, "publish('bug.created')"), (6, 5, "INSERT audit_log"), (3, 2, "bug JSON", True),
            (2, 1, "201 Created", True), (1, 0, "toast 'Bug #9 created'", True)]
    y = 85
    for m in msgs:
        a, b, t = m[0], m[1], m[2]
        ret = len(m) > 3
        if a == b:
            ax.annotate("", xy=(xs[a] + 0.5, y - 2), xytext=(xs[a] + 0.5, y),
                        arrowprops=dict(arrowstyle="-|>", connectionstyle="bar,fraction=-0.6", color=INK, lw=1))
            ax.text(xs[a] + 5, y - 1, t, fontsize=7.5)
        else:
            arrow(ax, (xs[a], y), (xs[b], y), t, dashed=ret)
        y -= 3.8
    for x in xs[1:]:
        ax.add_patch(plt.Rectangle((x - 0.8, 10), 1.6, 76, fc="white", ec="#94a3b8", lw=0.6, zorder=0))
    save(fig, "03_sequence.png")


# ------------------------------------------------------------------ 4. ACTIVITY
def activity():
    fig, ax = canvas(11, 13, "Activity Diagram – Bug Triage and Resolution")
    ax.add_patch(plt.Circle((55, 124), 2, color=INK))
    steps = [(55, 114, "Reporter submits bug"), (55, 104, "AI predicts severity &\nchecks duplicates"),
             (55, 80, "Manager assigns developer\n(manual or auto strategy)"), (55, 70, "Developer works on fix"),
             (55, 60, "Developer marks FIXED"), (55, 50, "Tester verifies fix"), (55, 26, "Bug VERIFIED → CLOSED"),
             (90, 92, "Mark DUPLICATE\n(link original)"), (90, 38, "REOPEN bug")]
    for x, y, t in steps:
        box(ax, x - 15, y - 4, 30, 8, t, BLUE, fs=8)
    for (x, y, t) in [(55, 92, "Duplicate?"), (55, 38, "Test passed?")]:
        ax.add_patch(Polygon([(x, y + 5), (x + 9, y), (x, y - 5), (x - 9, y)], fc=ORANGE, ec=INK))
        ax.text(x, y, t, ha="center", va="center", fontsize=7.5)
    seq = [(122, 118), (110, 108), (100, 97), (87, 84), (76, 74), (66, 64), (56, 54), (46, 43), (33, 30)]
    for a, b in seq:
        arrow(ax, (55, a), (55, b))
    ax.text(57, 85.5, "no", fontsize=8)
    arrow(ax, (64, 92), (75, 92), "yes")
    ax.text(57, 31.5, "yes", fontsize=8)
    arrow(ax, (64, 38), (75, 38), "no")
    arrow(ax, (90, 42), (71, 70), "assign again", rad=0.3)
    ax.add_patch(plt.Circle((55, 12), 2.4, fc="white", ec=INK, lw=1.5))
    ax.add_patch(plt.Circle((55, 12), 1.5, color=INK))
    arrow(ax, (55, 22), (55, 14.5))
    arrow(ax, (90, 88), (57, 13.5), rad=-0.3)
    save(fig, "04_activity.png")


# ------------------------------------------------------------------ 5. STATE
def state():
    fig, ax = canvas(15, 9, "State Machine Diagram – Bug Life Cycle")
    S = {"NEW": (12, 60), "ASSIGNED": (40, 60), "IN_PROGRESS": (68, 60), "FIXED": (96, 60), "IN_TESTING": (124, 60),
         "VERIFIED": (124, 30), "CLOSED": (96, 30), "REOPENED": (68, 30), "REJECTED": (12, 30), "DUPLICATE": (40, 82)}
    for s, (x, y) in S.items():
        fc = GREEN if s in ("CLOSED", "VERIFIED") else (GREY if s in ("REJECTED", "DUPLICATE") else BLUE)
        box(ax, x - 10, y - 4, 20, 8, s, fc, fs=8, bold=True)
    ax.add_patch(plt.Circle((12, 78), 1.6, color=INK))
    arrow(ax, (12, 76.4), (12, 64), "report")
    T = [("NEW", "ASSIGNED", "assign [Mgr]"), ("ASSIGNED", "IN_PROGRESS", "start [Dev]"), ("IN_PROGRESS", "FIXED", "fix [Dev]"),
         ("FIXED", "IN_TESTING", "test [QA]"), ("IN_TESTING", "VERIFIED", "pass [QA]"), ("VERIFIED", "CLOSED", "close"),
         ("IN_TESTING", "REOPENED", "fail [QA]"), ("REOPENED", "ASSIGNED", "re-assign"), ("CLOSED", "REOPENED", "regression"),
         ("NEW", "REJECTED", "not a bug"), ("NEW", "DUPLICATE", "duplicate"), ("REJECTED", "NEW", "re-open [Mgr]")]
    for a, b, t in T:
        (x1, y1), (x2, y2) = S[a], S[b]
        if (a, b) == ("REJECTED", "NEW"):
            arrow(ax, (x1 + 4, y1 + 4), (x2 + 4, y2 - 4), t, rad=-0.3)
            continue
        if (a, b) == ("NEW", "REJECTED"):
            arrow(ax, (x1 - 4, y1 - 4), (x2 - 4, y2 + 4), t, rad=-0.3)
            continue
        dx, dy = x2 - x1, y2 - y1
        sx = 10 if dx > 0 else (-10 if dx < 0 else 0)
        sy = 4 if dy > 0 else (-4 if dy < 0 else 0)
        if dx and dy:
            sx = 0
        arrow(ax, (x1 + sx, y1 + sy), (x2 - sx, y2 - sy), t)
    ax.add_patch(plt.Circle((96, 12), 2.2, fc="white", ec=INK, lw=1.4))
    ax.add_patch(plt.Circle((96, 12), 1.3, color=INK))
    arrow(ax, (96, 26), (96, 14.4))
    ax.text(2, 4, "Guards in [ ] are the roles allowed to fire the transition (enforced by BugStateMachine.validate)",
            fontsize=8, style="italic")
    save(fig, "05_state.png")


# ------------------------------------------------------------------ 6. ER
def er():
    fig, ax = canvas(15, 10, "Entity–Relationship Diagram (Database Schema, 3NF)")
    T = {
        "users": (4, 92, ["PK id", "username UNIQUE", "email UNIQUE", "password_hash", "role CHECK", "skills", "failed_logins", "locked_until"]),
        "projects": (58, 92, ["PK id", "name UNIQUE", "description", "created_at"]),
        "releases": (108, 92, ["PK id", "FK project_id", "version", "status CHECK", "release_date"]),
        "bugs": (58, 64, ["PK id", "FK project_id", "FK reporter_id", "FK assignee_id", "FK target_release_id",
                          "FK duplicate_of (self)", "title, description", "severity, priority, status", "ai_severity, ai_confidence"]),
        "comments": (4, 40, ["PK id", "FK bug_id", "FK author_id", "body", "created_at"]),
        "bug_history": (108, 50, ["PK id", "FK bug_id", "FK actor_id", "field", "old_value, new_value"]),
        "audit_log": (108, 20, ["PK id", "user_id", "action", "detail", "ip_address"]),
        "notifications": (58, 20, ["PK id", "FK user_id", "message", "is_read"]),
    }
    pos = {}
    for name, (x, y, cols) in T.items():
        w, h = 34, 4 + 2.6 * len(cols)
        ax.add_patch(plt.Rectangle((x, y - 4), w, 4, fc="#6366f1", ec=INK))
        ax.text(x + w / 2, y - 2, name, color="white", ha="center", va="center", fontweight="bold")
        ax.add_patch(plt.Rectangle((x, y - h), w, h - 4, fc="white", ec=INK))
        for i, c in enumerate(cols):
            ax.text(x + 1, y - 6 - i * 2.6, c, fontsize=7, fontweight="bold" if c.startswith(("PK", "FK")) else "normal")
        pos[name] = (x, y - h, w, h)

    def c(n, side):
        x, y, w, h = pos[n]
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]
    rel = [("users", "r", "bugs", "l", "1 reports / is assigned  N"), ("projects", "b", "bugs", "t", "1 : N"),
           ("projects", "r", "releases", "l", "1 : N"), ("releases", "b", "bugs", "r", "1 targets N"),
           ("bugs", "l", "comments", "r", "1 : N"), ("bugs", "r", "bug_history", "l", "1 : N"),
           ("users", "b", "comments", "t", "1 writes N"), ("users", "b", "notifications", "l", "1 : N")]
    for a, sa, b, sb, t in rel:
        arrow(ax, c(a, sa), c(b, sb), t, style="-")
    ax.text(4, 3, "Also: VIEW v_developer_workload, TRIGGER trg_bugs_updated, INDEX on bugs(status, assignee_id, project_id)",
            fontsize=8, style="italic")
    save(fig, "06_er.png")


# ------------------------------------------------------------------ 7. ARCHITECTURE
def architecture():
    fig, ax = canvas(13, 9, "Layered Architecture (3-tier, MVC-style)")
    layers = [(76, "Presentation Layer – Browser SPA", "index.html · app.js · Tailwind CSS · Chart.js · drag-and-drop board", "#c7d2fe"),
              (60, "Controller Layer – Flask REST API (routes.py)", "Authentication decorator · RBAC · rate limiter · JSON in/out · security headers", BLUE),
              (44, "Service / Business Layer (services/)", "AuthService · BugService · AnalyticsService · AssignmentStrategy · EventBus (Observer)", GREEN),
              (28, "Domain + AI Layer", "User · Bug · BugStateMachine · derive_priority  |  BugIntelligence (TF-IDF + LogisticRegression)", ORANGE),
              (12, "Data Access Layer (db.py) → SQLite", "Repository pattern · parameterised SQL · FK constraints · trigger · view · indexes", PURPLE)]
    for y, t, sub, fc in layers:
        box(ax, 8, y, 114, 12, "", fc)
        ax.text(65, y + 8, t, ha="center", fontweight="bold", fontsize=10.5)
        ax.text(65, y + 3.5, sub, ha="center", fontsize=8.5)
    for y in (76, 60, 44, 28):
        arrow(ax, (65, y), (65, y - 4))
    ax.text(124, 82, "HTTPS\nJSON", fontsize=8, ha="center")
    ax.text(8, 4, "Each layer only calls the layer directly below it → low coupling, high cohesion, easy to test & replace.",
            fontsize=8.5, style="italic")
    save(fig, "07_architecture.png")


# ------------------------------------------------------------------ 8. DFD level 0 / 1
def dfd():
    fig, ax = canvas(13, 8, "Data Flow Diagram – Level 1")
    for x, y, t in [(4, 60, "Reporter /\nTester"), (4, 20, "Developer"), (112, 60, "Manager"), (112, 20, "Admin")]:
        box(ax, x, y, 16, 10, t, GREY, round_=False, bold=True)
    procs = [(40, 64, "1.0\nAuthenticate"), (40, 40, "2.0\nReport &\nTriage Bug"), (70, 64, "3.0\nAssign\nDeveloper"),
             (70, 40, "4.0\nUpdate\nStatus"), (55, 16, "5.0\nRelease &\nAnalytics")]
    for x, y, t in procs:
        ax.add_patch(Ellipse((x + 7, y + 5), 18, 13, fc=BLUE, ec=INK))
        ax.text(x + 7, y + 5, t, ha="center", va="center", fontsize=8)
    for x, y, t in [(95, 44, "D1 Bugs"), (3, 44, "D2 Users"), (95, 6, "D3 Audit Log")]:
        ax.plot([x, x + 18], [y + 5, y + 5], color=INK)
        ax.plot([x, x + 18], [y, y], color=INK)
        ax.text(x + 9, y + 2.5, t, ha="center", va="center", fontsize=8, fontweight="bold")
    flows = [((20, 66), (38, 69), "credentials"), ((20, 62), (38, 45), "bug report"), ((50, 39), (100, 43), "new bug"),
             ((112, 66), (86, 69), "assignment"), ((86, 64), (100, 50), "assignee"), ((20, 24), (68, 42), "status change"),
             ((86, 44), (95, 46), ""), ((105, 44), (70, 26), "bug data"), ((62, 16), (112, 24), "reports"),
             ((41, 65), (16, 50), "lookup"), ((80, 40), (100, 11), "events")]
    for a, b, t in flows:
        arrow(ax, a, b, t, rad=0.25 if t == "new bug" else 0.0)
    save(fig, "08_dfd.png")


# ------------------------------------------------------------------ 9. DEPLOYMENT
def deployment():
    fig, ax = canvas(12, 6, "Deployment Diagram")
    box(ax, 4, 18, 32, 30, "", GREY, round_=False)
    ax.text(20, 44, "«device» Client PC / Mobile", ha="center", fontweight="bold")
    box(ax, 8, 24, 24, 12, "Web Browser\nSPA (HTML/JS/CSS)", BLUE)
    box(ax, 46, 10, 70, 44, "", GREY, round_=False)
    ax.text(81, 50, "«server» Application Server (Python 3.11)", ha="center", fontweight="bold")
    box(ax, 50, 30, 28, 14, "Gunicorn / Flask\nREST API", GREEN)
    box(ax, 84, 30, 28, 14, "BugIntelligence\n(scikit-learn model)", ORANGE)
    box(ax, 66, 13, 28, 12, "SQLite DB file\n(nirbug.db)", PURPLE)
    arrow(ax, (32, 30), (50, 37), "HTTPS / JSON (TLS)", style="<|-|>")
    arrow(ax, (78, 37), (84, 37), "", style="<|-|>")
    arrow(ax, (64, 30), (76, 25), "SQL", style="<|-|>")
    save(fig, "09_deployment.png")


# ------------------------------------------------------------------ 10. GANTT
def gantt():
    # Project window: 31 Oct 2026 (day 0) -> 15 Nov 2026 (day 15) = 16 days.
    # (task, start day, duration in days, owner)
    tasks = [("Requirement gathering & SRS", 0, 3, "Both"), ("Use-case & domain modelling", 2, 2, "Anamika"),
             ("Architecture & DB design", 3, 2, "Shreya"), ("UML diagrams", 4, 3, "Anamika"),
             ("Backend: DB + repositories", 5, 3, "Shreya"), ("Backend: services + security", 7, 3, "Shreya"),
             ("AI module (ML)", 7, 3, "Anamika"), ("Frontend (web UI)", 8, 4, "Anamika"),
             ("Unit + integration tests", 10, 3, "Shreya"), ("System testing & bug fixing", 12, 2, "Both"),
             ("Report, PPT & demo", 13, 3, "Both")]
    colors = {"Anamika": "#6366f1", "Shreya": "#ec4899", "Both": "#10b981"}
    import datetime as _dt
    start = _dt.date(2026, 10, 31)
    fig, ax = plt.subplots(figsize=(12, 5.5))
    for i, (t, s, d, who) in enumerate(tasks):
        ax.barh(i, d, left=s, color=colors[who], edgecolor=INK, height=0.6)
        ax.text(s + d + 0.15, i, who, va="center", fontsize=8)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels([t[0] for t in tasks])
    ax.invert_yaxis()
    ax.set_xlim(0, 17.2)
    ax.set_xticks([i + 0.5 for i in range(16)])      # one label in the middle of each day
    ax.set_xticklabels([(start + _dt.timedelta(days=i)).strftime("%d\n%b") for i in range(16)], fontsize=8)
    ax.tick_params(axis="x", length=0)
    for i in range(17):
        ax.axvline(i, color="#e2e8f0", lw=0.6, zorder=0)
    ax.set_xlabel("Date (2026)")
    for m, d in [("M1 SRS sign-off", 3), ("M2 Design done", 7), ("M3 Feature complete", 13), ("M4 Submission", 16)]:
        ax.axvline(d, color="#f59e0b", ls="--", lw=1)
        ax.text(d, -1, m, rotation=0, fontsize=7.5, ha="center", color="#b45309")
    ax.set_title("Project Schedule – Gantt Chart (31 Oct – 15 Nov 2026, 16 days)", fontsize=14, fontweight="bold", pad=20)
    save(fig, "10_gantt.png")


# ------------------------------------------------------------------ 11. COMPONENT
def component():
    fig, ax = canvas(13, 7, "Component Diagram")
    comps = [(4, 40, "Web UI\n(static/)"), (34, 40, "REST API\n(routes.py)"), (64, 52, "Auth & Security\n(security.py)"),
             (64, 28, "Bug Management\n(services/core.py)"), (96, 52, "AI Engine\n(ml/classifier.py)"),
             (96, 28, "Assignment\n(services/assignment.py)"), (64, 4, "Event Bus\n(services/events.py)"), (96, 4, "Persistence\n(db.py + SQLite)")]
    for x, y, t in comps:
        box(ax, x, y, 26, 12, "«component»\n" + t, BLUE, fs=8)
    for a, b in [((30, 46), (34, 46)), ((60, 49), (64, 57)), ((60, 44), (64, 34)), ((90, 37), (96, 55)),
                 ((90, 34), (96, 34)), ((77, 28), (77, 16)), ((90, 30), (100, 16)), ((90, 10), (96, 10))]:
        arrow(ax, a, b)
    save(fig, "11_component.png")


# ------------------------------------------------------------------ 12. SDLC MODEL
def sdlc():
    import math
    fig, ax = canvas(14, 7.5, "SDLC Model – Iterative Incremental (Agile / Scrum-based)")
    # left: the cycle every sprint goes through
    cx, cy, r, ry = 34, 36, 27, 25
    phases = ["1. Plan &\nRequirements", "2. Analysis", "3. Design", "4. Implement", "5. Test", "6. Review &\nDeliver"]
    cols = [BLUE, PURPLE, "#e0f2fe", GREEN, ORANGE, "#fce7f3"]
    pts = []
    for i, (p, c) in enumerate(zip(phases, cols)):
        a = math.pi / 2 - i * 2 * math.pi / len(phases)
        x, y = cx + r * math.cos(a), cy + ry * math.sin(a)
        pts.append((x, y))
        box(ax, x - 8, y - 4.5, 16, 9, p, c, fs=8, bold=True)
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        dx, dy = x2 - x1, y2 - y1
        # fraction of the segment that lies inside a 18x9 box -> start/end exactly at the box edge
        k = min(8.8 / abs(dx) if dx else 1e9, 5.1 / abs(dy) if dy else 1e9)
        arrow(ax, (x1 + dx * k, y1 + dy * k), (x2 - dx * k, y2 - dy * k), rad=-0.15)
    ax.text(cx, cy + 1.5, "repeated\nevery sprint", ha="center", va="center", fontsize=9, style="italic", color="#475569")
    ax.text(cx, cy - 4, "↻", ha="center", va="center", fontsize=22, color="#6366f1")

    # right: the three increments on the real timeline
    sprints = [("Sprint 1", "31 Oct – 4 Nov", "Requirements & SRS, use cases,\narchitecture, DB schema, login/auth", BLUE),
               ("Sprint 2", "5 – 9 Nov", "Bug workflow & state machine,\nassignment strategies, AI module, API", PURPLE),
               ("Sprint 3", "10 – 15 Nov", "Web UI, releases, dashboard,\nall testing, report & PPT", GREEN)]
    for i, (n, d, w, c) in enumerate(sprints):
        y = 58 - i * 20
        box(ax, 72, y, 62, 15, "", c)
        ax.text(75, y + 11, f"{n}  ·  {d}", fontsize=10, fontweight="bold", color=INK)
        ax.text(75, y + 3.2, w, fontsize=8.5, color=INK)
        ax.text(131, y + 11, f"Increment {i + 1}", fontsize=8, ha="right", color="#475569", style="italic")
        if i < 2:
            arrow(ax, (103, y), (103, y - 5))
    ax.text(103, 9, "Each sprint ends with a working, tested increment + review with the team",
            ha="center", fontsize=8.5, style="italic", color="#475569")
    save(fig, "12_sdlc.png")


if __name__ == "__main__":
    for f in (use_case, class_diagram, sequence, activity, state, er, architecture, dfd, deployment, gantt, component, sdlc):
        f()
