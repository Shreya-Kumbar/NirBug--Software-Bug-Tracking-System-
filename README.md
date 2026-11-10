# BugSense – AI-Assisted Software Bug Tracking & Issue Management System

Software Engineering group project. A full-stack web app for bug reporting, severity classification,
developer assignment, version tracking, testing status and release management.

## Features
- Bug reporting with **AI severity prediction**, component guess and **duplicate detection** (scikit-learn)
- Priority rule (P1–P4), **10-state bug life cycle** enforced per role
- Manual or **automatic assignment** (skill + workload Strategy pattern)
- Testing workflow: FIXED → IN_TESTING → VERIFIED / REOPENED
- Projects, releases, **release readiness** and ship gate
- Dashboard charts, Kanban board (drag & drop), comments, history, notifications, audit log
- Security: PBKDF2 hashing, signed tokens, RBAC, account lockout, rate limiting, CSP / security headers

## Run
```bash
pip install -r requirements.txt
python -m bugtracker.app
```
Open http://127.0.0.1:5000 — demo accounts `admin`, `manager`, `dev_alice`, `dev_bob`, `dev_chen`, `tester`,
`reporter`, all with password `Demo@1234`. Delete `bugsense.db` to reset the demo data.

## Test
```bash
python -m pytest -v        # 63 unit, integration and system tests
```

## Documents
```bash
python docs/generate_diagrams.py   # UML diagrams -> docs/diagrams/
python docs/build_report.py        # docs/BugSense_Project_Report.docx
python docs/build_ppt.py           # docs/BugSense_Presentation.pptx
```

## Structure
```
bugtracker/   app.py, routes.py, domain.py, db.py, security.py, seed.py
              services/ (core, assignment, events)   ml/ (classifier, training data)   static/ (UI)
tests/        test_unit.py, test_integration.py, test_system.py
docs/         diagrams, screenshots, report & PPT generators and outputs
```
