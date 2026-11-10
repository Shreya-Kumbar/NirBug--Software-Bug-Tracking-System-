"""Strategy pattern: interchangeable algorithms for auto-assigning a developer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AssignmentStrategy(ABC):
    name = "base"

    @abstractmethod
    def choose(self, developers: list[dict], bug: dict) -> Optional[int]:
        """developers: rows from v_developer_workload (user_id, open_bugs, load_score, skills)."""


class LeastLoadedStrategy(AssignmentStrategy):
    """Pick the developer with the smallest severity-weighted workload."""
    name = "least_loaded"

    def choose(self, developers, bug):
        if not developers:
            return None
        return min(developers, key=lambda d: (d["load_score"], d["open_bugs"], d["user_id"]))["user_id"]


class SkillBasedStrategy(AssignmentStrategy):
    """Prefer developers whose skills match the bug component; break ties by workload.

    score = 10 * skill_match - load_score   (higher is better)
    """
    name = "skill_based"

    def choose(self, developers, bug):
        if not developers:
            return None
        comp = (bug.get("component") or "").lower()

        def score(d):
            skills = {s.strip().lower() for s in (d.get("skills") or "").split(",")}
            return (10 if comp in skills else 0) - d["load_score"], -d["user_id"]

        return max(developers, key=score)["user_id"]


STRATEGIES = {s.name: s for s in (LeastLoadedStrategy(), SkillBasedStrategy())}
