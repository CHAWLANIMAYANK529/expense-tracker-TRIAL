import pytest

from app import create_app
from app.db import get_db
from config import TestConfig


@pytest.fixture
def app(tmp_path):
    application = create_app(TestConfig, database=tmp_path / "test.db")
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, name="Asha", email="asha@example.com", password="password123"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=True,
    )


def login(client, email="asha@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def category_id(app, name="Food"):
    with app.app_context():
        row = get_db().execute(
            "SELECT id FROM categories WHERE name = ? AND user_id IS NULL",
            (name,),
        ).fetchone()
    return row["id"]


def expense_form(app, **overrides):
    data = {
        "description": "Groceries",
        "amount": "450",
        "date": "2026-09-10",
        "category_id": category_id(app),
        "new_category": "",
        "payment_method": "UPI",
        "notes": "Weekly shop",
    }
    data.update(overrides)
    return data
