from tests.conftest import login, register


def test_register_and_login(client):
    response = register(client)
    assert b"Registration successful. Please log in." in response.data
    response = login(client)
    assert response.status_code == 200
    assert b"Hello, Asha" in response.data


def test_duplicate_email_is_rejected(client):
    register(client)
    response = register(client)
    assert b"Email already registered." in response.data


def test_short_password_is_rejected(client):
    response = register(client, password="short")
    assert b"Password must be at least 8 characters." in response.data


def test_invalid_login(client):
    register(client)
    response = login(client, password="wrong-password")
    assert b"Invalid email or password." in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logout(client):
    register(client)
    login(client)
    response = client.post("/logout", follow_redirects=True)
    assert b"Log in" in response.data
    follow = client.get("/dashboard")
    assert follow.status_code == 302


def test_get_logout_does_not_end_the_session(client):
    register(client)
    login(client)
    response = client.get("/logout")
    assert response.status_code == 405
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"Hello, Asha" in dashboard.data


def test_new_account_has_no_budget_until_one_is_saved(client):
    register(client)
    login(client)
    page = client.get("/dashboard")
    body = page.get_data(as_text=True)
    assert "Not set" in body
    assert "₹5,000" not in body


def test_email_match_ignores_capital_letters(client, app):
    from werkzeug.security import generate_password_hash

    from app.db import get_db

    with app.app_context():
        get_db().execute(
            "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, NULL)",
            ("Asha", "Asha@Example.com", generate_password_hash("password123")),
        )
        get_db().commit()
    response = register(client, email="asha@example.com")
    assert b"Email already registered." in response.data
    logged_in = login(client, email="asha@example.com")
    assert b"Hello, Asha" in logged_in.data
