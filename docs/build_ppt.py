"""Builds the presentation  ->  docs/BugSense_Presentation.pptx   (16:9, 18 slides)"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
DIA, SHOT = os.path.join(HERE, "diagrams"), os.path.join(HERE, "screenshots")
INDIGO, PURPLE, DARK, LIGHT, WHITE = (RGBColor(0x43, 0x38, 0xCA), RGBColor(0xA8, 0x55, 0xF7),
                                      RGBColor(0x0F, 0x17, 0x2A), RGBColor(0xF1, 0xF5, 0xF9), RGBColor(255, 255, 255))
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height


def rect(s, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(shape, x, y, w, h)
    r.fill.solid()
    r.fill.fore_color.rgb = color
    r.line.fill.background()
    return r


def text(s, x, y, w, h, t, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, "Segoe UI"
    return tb


def slide(title, n):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, W, Inches(1.1), INDIGO)
    rect(s, 0, Inches(1.1), W, Inches(0.06), PURPLE)
    text(s, Inches(0.5), Inches(0.22), Inches(11), Inches(0.8), title, 30, True, WHITE)
    text(s, Inches(12.2), Inches(7.0), Inches(1), Inches(0.4), str(len(prs.slides)), 12, color=RGBColor(0x94, 0xA3, 0xB8))
    return s


def bullets(s, items, x=0.6, y=1.5, w=12.2, size=20):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(5.6))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        head, _, rest = it.partition("|")
        r = p.add_run()
        r.text = "▸ " + head
        r.font.size, r.font.bold, r.font.color.rgb = Pt(size), bool(rest), INDIGO if rest else DARK
        if rest:
            r2 = p.add_run()
            r2.text = " " + rest
            r2.font.size, r2.font.color.rgb = Pt(size - 2), DARK


def image(s, path, x=None, y=1.4, w=None, h=5.8):
    if not os.path.exists(path):
        return
    pic = s.shapes.add_picture(path, 0, Inches(y), height=Inches(h)) if w is None else \
        s.shapes.add_picture(path, 0, Inches(y), width=Inches(w))
    if pic.width > W - Inches(0.6):
        ratio = (W - Inches(0.6)) / pic.width
        pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    pic.left = int((W - pic.width) / 2) if x is None else Inches(x)


# 1 Title
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, INDIGO)
rect(s, Inches(8.5), Inches(-2), Inches(7), Inches(7), PURPLE, MSO_SHAPE.OVAL)
text(s, Inches(0.8), Inches(1.6), Inches(11), Inches(1.2), "🐞 BugSense", 60, True, WHITE)
text(s, Inches(0.8), Inches(2.9), Inches(10), Inches(1.2),
     "AI-Assisted Software Bug Tracking & Issue Management System", 28, False, WHITE)
text(s, Inches(0.8), Inches(4.4), Inches(10), Inches(1.5),
     "Software Engineering Group Project\nMember 1: <Name> (<Roll No>)     Member 2: <Name> (<Roll No>)", 18, False, WHITE)

# 2 Problem
s = slide("Problem Statement", 2)
bullets(s, ["Bugs reported via e-mail / chat / spreadsheets get lost or duplicated",
            "Severity is judged inconsistently – critical bugs wait in the queue",
            "Work is assigned unevenly; some developers overloaded",
            "Managers cannot see which bugs block a release",
            "No history of who changed what → no accountability",
            "Goal:|One system that manages the complete bug life cycle using sound SE practices"])

# 3 Objectives & features
s = slide("Objectives & Key Features", 3)
feats = [("Bug Reporting", "structured form, version found, target release"), ("Severity & Priority", "4 severities → P1–P4 rule"),
         ("AI Triage", "ML severity prediction + duplicate detection"), ("Smart Assignment", "skill + workload strategy"),
         ("Life-cycle & Testing", "10-state machine, QA verify / reopen"), ("Release Management", "readiness % and ship gate"),
         ("Dashboard & Kanban", "charts, workload, drag-and-drop"), ("Security & Audit", "RBAC, hashing, lockout, audit log")]
for i, (h, d) in enumerate(feats):
    x, y = Inches(0.5 + (i % 4) * 3.15), Inches(1.6 + (i // 4) * 2.7)
    card = rect(s, x, y, Inches(2.95), Inches(2.4), LIGHT, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.2), y + Inches(0.3), Inches(2.6), Inches(0.6), h, 18, True, INDIGO)
    text(s, x + Inches(0.2), y + Inches(1.0), Inches(2.6), Inches(1.3), d, 14)

# 4 SDLC
s = slide("SDLC Model – Iterative Incremental (Agile / Scrum)", 4)
image(s, os.path.join(DIA, "12_sdlc.png"), y=1.35, h=5.7)

s = slide("SDLC Phases & Why This Model", 4)
phases = [("1. Plan & Requirements", "Problem, scope, SRS, schedule"), ("2. Analysis", "Stakeholders, use cases, feasibility"),
          ("3. Design", "Architecture, UML, ER diagram, patterns"), ("4. Implementation", "Flask back-end, DB, AI, web UI"),
          ("5. Testing", "63 unit / integration / system tests"), ("6. Review & Deploy", "Demo each sprint, plan the next"),
          ("7. Maintenance", "Fix, adapt, extend after delivery")]
for i, (h, d) in enumerate(phases):
    x, y = Inches(0.5 + (i % 4) * 3.15), Inches(1.45 + (i // 4) * 1.55)
    rect(s, x, y, Inches(2.95), Inches(1.35), LIGHT, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.15), y + Inches(0.12), Inches(2.7), Inches(0.5), h, 15, True, INDIGO)
    text(s, x + Inches(0.15), y + Inches(0.6), Inches(2.7), Inches(0.7), d, 12)
bullets(s, ["Why Iterative Incremental:|16-day deadline, 2-person team, changing requirements, working product after every sprint",
            "Why not Waterfall:|no going back after design; nothing works until the end",
            "Why not Spiral:|too heavy (risk-driven) for a small project"], y=4.75, size=16)

# 5 SRS
s = slide("Requirements (SRS – IEEE 830)", 5)
text(s, Inches(0.6), Inches(1.4), Inches(6), Inches(0.5), "Functional (16)", 22, True, INDIGO)
bullets(s, ["Register / login, 5 roles (RBAC)", "Report bug + AI severity", "Priority derivation", "Duplicate detection",
            "Manual / auto assignment", "Enforced life cycle", "Comments, history, notifications", "Releases + ship gate",
            "Search, dashboard, Kanban, audit log"], x=0.6, y=2.0, w=6, size=16)
text(s, Inches(7), Inches(1.4), Inches(6), Inches(0.5), "Non-functional (10)", 22, True, INDIGO)
bullets(s, ["Security: PBKDF2, lockout, rate limit, CSP", "Performance: < 300 ms, DB indexes", "Usability: responsive, dark mode",
            "Reliability: FK / CHECK constraints", "Maintainability: layers, patterns, 63 tests", "Portability: any OS, Python 3.10+",
            "Accountability: audit log"], x=7, y=2.0, w=6, size=16)

# 6-10 diagrams
for n, (f, t) in enumerate([("01_use_case.png", "Use-Case Diagram"), ("02_class.png", "Class Diagram"),
                            ("03_sequence.png", "Sequence Diagram – Report a Bug"), ("05_state.png", "State Diagram – Bug Life Cycle"),
                            ("04_activity.png", "Activity Diagram – Triage & Resolution")], start=6):
    s = slide(t, n)
    image(s, os.path.join(DIA, f))

# 11 Architecture
s = slide("Architecture & Design Patterns", 11)
image(s, os.path.join(DIA, "07_architecture.png"), x=0.3, y=1.4, h=5.2)
bullets(s, ["Repository|– data access", "Strategy|– assignment", "State|– life cycle", "Observer|– audit/notify",
            "Factory|– create_app", "Decorator|– auth", "SOLID|principles"], x=8.4, y=1.5, w=4.8, size=17)

# 12 Database
s = slide("Database Design (3NF)", 12)
image(s, os.path.join(DIA, "06_er.png"), x=0.3, y=1.4, h=5.7)
bullets(s, ["8 tables, FKs", "CHECK / UNIQUE", "3 indexes", "Trigger", "View for workload", "Parameterised SQL"],
        x=9.6, y=1.5, w=3.6, size=16)

# 13 AI
s = slide("AI / ML Module", 13)
bullets(s, ["Severity classifier:|TF-IDF (word + char n-grams) → Logistic Regression",
            "Safety rules:|'crash', 'data loss', 'SQL injection' → CRITICAL",
            "Duplicate detection:|cosine similarity ≥ 0.45 vs open bugs",
            "Smart assignment:|score = 10·skill_match − workload",
            "Human-in-the-loop:|user can override; AI/human agreement shown on dashboard",
            "Evaluation:|stratified 5-fold cross-validation, beats random baseline; improves as data grows"], size=18)

# 15 Security + Testing
s = slide("Security & Testing", 14)
text(s, Inches(0.6), Inches(1.4), Inches(6), Inches(0.5), "Security (STRIDE)", 22, True, INDIGO)
bullets(s, ["PBKDF2-SHA256 salted hashes", "HMAC-signed expiring tokens", "RBAC on every endpoint", "Lockout after 5 failures",
            "Rate limiting (429)", "SQLi: parameterised queries", "XSS: escaping + CSP", "Audit log with IP"], x=0.6, y=2.0, w=6, size=16)
text(s, Inches(7), Inches(1.4), Inches(6), Inches(0.5), "Testing – 63 tests, all pass", 22, True, INDIGO)
bullets(s, ["Unit:|state machine, rules, security, AI", "Integration:|services + SQLite",
            "System:|black-box REST API, end-to-end", "Techniques:|BVA, equivalence classes, state-transition, security",
            "Traceability matrix FR → test"], x=7, y=2.0, w=6, size=16)

# 16 Planning
s = slide("Project Planning", 15)
image(s, os.path.join(DIA, "10_gantt.png"), y=1.3, h=4.4)
bullets(s, ["Member 1:|requirements, UML, AI module, front-end", "Member 2:|architecture, database, back-end, security, testing"],
        y=5.9, size=16)

# 17 Maintenance & conclusion
s = slide("Maintenance, Future Scope & Conclusion", 16)
bullets(s, ["Corrective:|regression test for every fix", "Adaptive:|SQLite → PostgreSQL by changing only db.py; Docker/cloud",
            "Perfective:|e-mail/Slack listener, attachments, Git/CI integration",
            "Preventive:|retrain ML on real data, dependency updates, refactoring",
            "Conclusion:|all required features delivered with a full SDLC – SRS, UML, architecture, OOP, security, testing, planning"],
        size=18)

# 18 Thank you
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, INDIGO)
text(s, 0, Inches(2.6), W, Inches(1.2), "Thank You", 60, True, WHITE, PP_ALIGN.CENTER)
text(s, 0, Inches(3.9), W, Inches(1), "Questions?  ·  Live demo: python -m bugtracker.app", 22, False, WHITE, PP_ALIGN.CENTER)

out = os.path.join(HERE, "BugSense_Presentation.pptx")
prs.save(out)
print("wrote", out)
