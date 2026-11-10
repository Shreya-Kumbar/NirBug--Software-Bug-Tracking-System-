"""AI / ML module: BugIntelligence.

1. Severity classification  - TF-IDF (word 1-2 grams) + Logistic Regression.
2. Duplicate detection      - TF-IDF vectors + cosine similarity against open bugs.
3. Component guessing       - keyword rules (simple expert system).

The model is trained once at start-up on ml/training_data.py (supervised learning).
A safety rule overrides the model for obvious critical keywords (human-in-the-loop:
the reporter/manager can always change the severity; the AI value is stored separately
so the agreement rate between AI and humans can be measured on the dashboard).
"""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline

from .training_data import DATA

CRITICAL_KEYWORDS = re.compile(
    r"\b(crash(es|ed)?|data loss|sql injection|xss|security breach|outage|corrupt(ed)?|"
    r"plain ?text password|auth(entication)? bypass)\b", re.I)

COMPONENT_KEYWORDS = {
    "auth": ["login", "password", "logout", "session", "token", "authentication", "register", "2fa"],
    "ui": ["button", "color", "font", "layout", "icon", "css", "align", "typo", "page", "screen"],
    "database": ["database", "sql", "query", "record", "table", "migration", "backup"],
    "api": ["api", "endpoint", "request", "response", "timeout", "500", "json"],
    "payment": ["payment", "checkout", "invoice", "charge", "order", "refund"],
    "performance": ["slow", "performance", "memory", "cpu", "load", "latency"],
    "notifications": ["email", "notification", "sms", "alert"],
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


class BugIntelligence:
    DUPLICATE_THRESHOLD = 0.45

    def __init__(self):
        texts = [_clean(t) for t, _ in DATA]
        labels = [l for _, l in DATA]
        self.model = self._build()
        self.model.fit(texts, labels)
        self._texts, self._labels = texts, labels

    @staticmethod
    def _build() -> Pipeline:
        """Word 1-2 grams + character 2-5 grams (robust to typos) -> Logistic Regression."""
        features = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ])
        return Pipeline([("features", features), ("clf", LogisticRegression(max_iter=3000, C=20.0))])

    def evaluate(self, folds: int = 5) -> dict:
        """Stratified k-fold cross-validation of the hybrid (rules + ML) classifier."""
        X, y = self._texts, self._labels
        ml_hits = hybrid_hits = 0
        for train, test in StratifiedKFold(folds, shuffle=True, random_state=0).split(X, y):
            m = self._build().fit([X[i] for i in train], [y[i] for i in train])
            for i in test:
                pred = m.predict([X[i]])[0]
                ml_hits += pred == y[i]
                hybrid = "CRITICAL" if CRITICAL_KEYWORDS.search(X[i]) else pred
                hybrid_hits += hybrid == y[i]
        n = len(X)
        return {"samples": n, "folds": folds, "ml_accuracy": round(ml_hits / n, 3),
                "hybrid_accuracy": round(hybrid_hits / n, 3), "random_baseline": 0.25}

    def predict_severity(self, text: str) -> tuple[str, float]:
        text = _clean(text)
        if CRITICAL_KEYWORDS.search(text):
            return "CRITICAL", 0.95
        probs = self.model.predict_proba([text])[0]
        idx = probs.argmax()
        return str(self.model.classes_[idx]), round(float(probs[idx]), 3)

    def find_duplicates(self, text: str, candidates: list[dict], top: int = 3) -> list[dict]:
        """candidates: [{'id','title','description'}]. Returns most similar above threshold."""
        if not candidates:
            return []
        docs = [_clean(f"{c['title']} {c['description']}") for c in candidates]
        vec = TfidfVectorizer(stop_words="english").fit(docs + [_clean(text)])
        sims = cosine_similarity(vec.transform([_clean(text)]), vec.transform(docs))[0]
        ranked = sorted(zip(candidates, sims), key=lambda x: -x[1])
        return [{"id": c["id"], "title": c["title"], "similarity": round(float(s), 3)}
                for c, s in ranked[:top] if s >= self.DUPLICATE_THRESHOLD]

    def guess_component(self, text: str) -> str:
        words = set(re.findall(r"[a-z0-9]+", _clean(text)))
        scores = {comp: sum(k in words for k in kws) for comp, kws in COMPONENT_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] else "general"
