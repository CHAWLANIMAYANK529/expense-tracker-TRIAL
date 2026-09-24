import shutil
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from config import TestConfig


def test_legacy_schema_is_upgraded_without_losing_rows(tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            budget REAL DEFAULT 5000
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        )
        """
    )
    password = generate_password_hash("password123")
    connection.execute(
        "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?)",
        ("Mayank", "mayank@example.com", password, 6500),
    )
    connection.execute(
        "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
        (1, "Food ", 3000, "Dine in", "2026-05-26"),
    )
    connection.execute(
        "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
        (1, "Travel", 3000, "rishikesh ", "2026-05-26"),
    )
    connection.commit()
    connection.close()

    app = create_app(TestConfig, database=database)
    client = app.test_client()
    client.post("/login", data={"email": "mayank@example.com", "password": "password123"})
    dashboard = client.get("/dashboard?range=all")
    assert dashboard.status_code == 200
    page = dashboard.get_data(as_text=True)
    assert "₹6,000" in page
    assert "Food" in page
    assert "Travel" in page

    with app.app_context():
        rows = get_db().execute(
            """
            SELECT e.id, e.description, e.amount, e.payment_method, c.name AS category
            FROM expenses e JOIN categories c ON c.id = e.category_id
            ORDER BY e.id
            """
        ).fetchall()
        custom = {
            row["name"]
            for row in get_db().execute("SELECT name FROM categories WHERE user_id = 1")
        }
    assert [(row["id"], row["description"], row["amount"]) for row in rows] == [
        (1, "Food", 3000),
        (2, "Travel", 3000),
    ]
    assert rows[0]["category"] == "Dine in"
    assert rows[1]["category"] == "rishikesh"
    assert rows[0]["payment_method"] == "Other"
    assert custom == {"Dine in", "rishikesh"}


def test_existing_project_database_is_preserved(tmp_path):
    source = Path(__file__).resolve().parents[1] / "database.db"
    original = source.read_bytes()
    copied = tmp_path / "database.db"
    shutil.copy(source, copied)

    app = create_app(TestConfig, database=copied)
    with app.app_context():
        user = get_db().execute("SELECT name, email, budget, password FROM users").fetchone()
        rows = get_db().execute(
            """
            SELECT e.description, e.amount, c.name AS category
            FROM expenses e JOIN categories c ON c.id = e.category_id
            ORDER BY e.id
            """
        ).fetchall()
    assert source.read_bytes() == original
    assert user["name"] == "Mayank"
    assert user["email"] == "chawlanimayank529@gmail.com"
    assert user["budget"] == 6500
    assert user["password"].startswith(("pbkdf2:", "scrypt:"))
    assert [(row["description"], row["amount"], row["category"]) for row in rows] == [
        ("Food", 3000.0, "Dine in"),
        ("Travel", 3000.0, "rishikesh"),
    ]
