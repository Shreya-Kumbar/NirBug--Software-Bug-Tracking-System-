"""Application factory (Factory pattern) + entry point.

Run:  python -m bugtracker.app        -> http://127.0.0.1:5000
"""
from __future__ import annotations

import os
import secrets

from flask import Flask, send_from_directory

from .db import Database
from .routes import api
from .security import SECURITY_HEADERS, RateLimiter
from .services.core import Services

BASE = os.path.dirname(os.path.abspath(__file__))


def create_app(db_path: str | None = None, seed: bool = True) -> Flask:
    app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")
    db_path = db_path or os.environ.get("NIRBUG_DB", os.path.join(BASE, "..", "nirbug.db"))
    secret = os.environ.get("NIRBUG_SECRET") or secrets.token_hex(32)

    db = Database(db_path)
    db.init_schema()
    services = Services(db, secret)
    app.config.update(SERVICES=services, LOGIN_LIMITER=RateLimiter(10, 60),
                      MAX_CONTENT_LENGTH=1 * 1024 * 1024)
    if seed and not services.users.all():
        from .seed import seed_demo_data
        seed_demo_data(services)

    app.register_blueprint(api)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.after_request
    def add_headers(resp):
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        return resp

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
