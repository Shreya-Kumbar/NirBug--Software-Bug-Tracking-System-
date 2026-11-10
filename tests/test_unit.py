"""UNIT TESTS - each class/function tested in isolation (no database, no HTTP)."""
import pytest

from bugtracker import security
from bugtracker.domain import (Bug, BugStateMachine, InvalidTransition, Priority, Role, Severity,
                               Status, User, derive_priority)
from bugtracker.ml.classifier import BugIntelligence
from bugtracker.services.assignment import LeastLoadedStrategy, SkillBasedStrategy


def user(role):
    return User(id=1, username="u", email="u@x.io", role=role)


# ---------- UT-01..06: Bug life-cycle state machine
def test_ut01_valid_transition_developer_starts_work():
    bug = Bug(id=1, project_id=1, title="t", description="d", reporter_id=1, status=Status.ASSIGNED)
    assert bug.transition(Status.IN_PROGRESS, user(Role.DEVELOPER)) == Status.ASSIGNED
    assert bug.status == Status.IN_PROGRESS


def test_ut02_invalid_transition_new_to_closed():
    bug = Bug(id=1, project_id=1, title="t", description="d", reporter_id=1)
    with pytest.raises(InvalidTransition):
        bug.transition(Status.CLOSED, user(Role.ADMIN))


def test_ut03_role_not_allowed_reporter_cannot_verify():
    with pytest.raises(InvalidTransition):
        BugStateMachine.validate(Status.IN_TESTING, Status.VERIFIED, Role.REPORTER)


def test_ut04_tester_can_reopen():
    BugStateMachine.validate(Status.IN_TESTING, Status.REOPENED, Role.TESTER)


def test_ut05_duplicate_is_terminal():
    assert BugStateMachine.allowed_next(Status.DUPLICATE, Role.ADMIN) == []


def test_ut06_allowed_next_depends_on_role():
    assert "FIXED" in BugStateMachine.allowed_next(Status.IN_PROGRESS, Role.DEVELOPER)
    assert BugStateMachine.allowed_next(Status.IN_PROGRESS, Role.TESTER) == []


# ---------- UT-07..09: priority business rule (boundary values)
@pytest.mark.parametrize("sev,blocks,expected", [
    (Severity.CRITICAL, False, Priority.P1), (Severity.CRITICAL, True, Priority.P1),
    (Severity.HIGH, False, Priority.P2), (Severity.HIGH, True, Priority.P1),
    (Severity.LOW, False, Priority.P4), (Severity.LOW, True, Priority.P3)])
def test_ut07_derive_priority(sev, blocks, expected):
    assert derive_priority(sev, blocks) == expected


def test_ut08_rbac_matrix():
    assert user(Role.MANAGER).can("assign_bug")
    assert not user(Role.DEVELOPER).can("assign_bug")
    assert user(Role.ADMIN).can("manage_users")
    assert not user(Role.MANAGER).can("manage_users")


# ---------- UT-10..14: security helpers
def test_ut10_password_hash_is_salted_and_verifiable():
    h1, h2 = security.hash_password("Secret123"), security.hash_password("Secret123")
    assert h1 != h2 and "Secret123" not in h1
    assert security.verify_password(h1, "Secret123")
    assert not security.verify_password(h1, "secret123")


@pytest.mark.parametrize("pw,ok", [("short1A", False), ("alllowercase1", False),
                                   ("ALLUPPER123", False), ("NoDigitsHere", False), ("GoodPass1", True)])
def test_ut11_password_policy(pw, ok):
    assert (security.password_problems(pw) == []) == ok


def test_ut12_token_roundtrip_and_tamper():
    tm = security.TokenManager("k")
    tok = tm.issue(7, "ADMIN")
    assert tm.verify(tok) == {"uid": 7, "role": "ADMIN"}
    assert tm.verify(tok[:-2] + "xx") is None
    assert security.TokenManager("other").verify(tok) is None


def test_ut13_rate_limiter():
    rl = security.RateLimiter(3, 60)
    assert [rl.allow("ip") for _ in range(4)] == [True, True, True, False]
    assert rl.allow("other-ip")


@pytest.mark.parametrize("email,ok", [("a@b.com", True), ("bad", False), ("a@b", False), ("x y@b.com", False)])
def test_ut14_email_validation(email, ok):
    assert security.valid_email(email) == ok


# ---------- UT-15..18: assignment strategies
DEVS = [{"user_id": 1, "open_bugs": 3, "load_score": 9, "skills": "ui"},
        {"user_id": 2, "open_bugs": 1, "load_score": 2, "skills": "auth,api"},
        {"user_id": 3, "open_bugs": 0, "load_score": 0, "skills": "payment"}]


def test_ut15_least_loaded():
    assert LeastLoadedStrategy().choose(DEVS, {}) == 3


def test_ut16_skill_based_prefers_matching_skill():
    assert SkillBasedStrategy().choose(DEVS, {"component": "auth"}) == 2


def test_ut17_skill_based_falls_back_to_workload():
    assert SkillBasedStrategy().choose(DEVS, {"component": "unknown"}) == 3


def test_ut18_no_developers():
    assert LeastLoadedStrategy().choose([], {}) is None


# ---------- UT-19..23: AI module
@pytest.fixture(scope="module")
def ai():
    return BugIntelligence()


def test_ut19_critical_keyword_rule(ai):
    assert ai.predict_severity("App crashes on launch")[0] == "CRITICAL"


def test_ut20_cosmetic_is_low(ai):
    assert ai.predict_severity("Typo in footer text, spelling mistake")[0] == "LOW"


def test_ut21_confidence_in_range(ai):
    _, conf = ai.predict_severity("Search results are wrong")
    assert 0 <= conf <= 1


def test_ut22_duplicate_detection(ai):
    cands = [{"id": 1, "title": "Login button not working", "description": "Clicking login does nothing"},
             {"id": 2, "title": "Wrong invoice total", "description": "Discount not applied"}]
    d = ai.find_duplicates("Login button does nothing when clicked", cands)
    assert d and d[0]["id"] == 1
    assert ai.find_duplicates("Completely unrelated rocket telemetry", cands) == []


def test_ut23_component_guess(ai):
    assert ai.guess_component("password reset token login") == "auth"
    assert ai.guess_component("zzz qqq") == "general"


def test_ut24_model_beats_random_baseline(ai):
    r = ai.evaluate()
    assert r["hybrid_accuracy"] > r["random_baseline"]
