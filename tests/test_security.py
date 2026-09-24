import re

from app import create_app
from config import TestConfig
from tests.conftest import login, register


class CsrfConfig(TestConfig):
    CSRF_ENABLED = True


def test_post_without_csrf_token_is_rejected(tmp_path):
    app = create_app(CsrfConfig, database=tmp_path / "csrf.db")
    client = app.test_client()
    page = client.get("/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    rejected = client.post("/login", data={"email": "a@example.com", "password": "password123"})
    assert rejected.status_code == 400
    assert b"form expired" in rejected.data.lower() or b"try again" in rejected.data.lower()

    accepted = client.post(
        "/login",
        data={"email": "missing@example.com", "password": "password123", "csrf_token": token},
    )
    assert accepted.status_code != 400


def test_passwords_are_hashed(client, app):
    register(client, password="password123")
    from app.db import get_db

    with app.app_context():
        stored = get_db().execute("SELECT password FROM users").fetchone()["password"]
    assert stored != "password123"
    assert stored.startswith(("pbkdf2:", "scrypt:"))


def test_export_requires_login(client):
    response = client.get("/export-csv")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logged_in_export_contains_own_fields(client, app):
    from tests.conftest import expense_form

    register(client)
    login(client)
    client.post("/expenses/new", data=expense_form(app, description="Metro card", notes="evening"))
    exported = client.get("/export-csv?date_from=2026-09-01&date_to=2026-09-30")
    text = exported.get_data(as_text=True)
    assert exported.mimetype == "text/csv"
    assert exported.headers["Content-Disposition"].endswith("expenses.csv")
    assert "Date,Description,Amount,Category,Payment Method,Notes" in text
    assert "Metro card" in text
    assert "evening" in text
    assert "UPI" in text
