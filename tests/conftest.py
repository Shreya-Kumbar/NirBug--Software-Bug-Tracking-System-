import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bugtracker.app import create_app  # noqa: E402
from bugtracker.seed import DEMO_PASSWORD  # noqa: E402


@pytest.fixture
def app():
    return create_app(":memory:", seed=True)


@pytest.fixture
def services(app):
    return app.config["SERVICES"]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login(username):
        r = client.post("/api/auth/login", json={"username": username, "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.json
        return {"Authorization": "Bearer " + r.json["token"]}
    return _login
