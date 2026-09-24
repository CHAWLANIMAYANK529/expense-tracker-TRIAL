from app.db import get_db
from tests.conftest import expense_form, login, register


def _expense_id(app):
    with app.app_context():
        return get_db().execute("SELECT id, amount, description FROM expenses").fetchone()


def test_users_cannot_read_or_change_each_others_expenses(client, app):
    register(client, name="Asha", email="asha@example.com")
    login(client, email="asha@example.com")
    client.post(
        "/expenses/new",
        data=expense_form(app, description="Asha lunch", amount="250", new_category="Street food"),
    )
    client.post("/logout")

    register(client, name="Rahul", email="rahul@example.com")
    login(client, email="rahul@example.com")
    original = _expense_id(app)

    edit_page = client.get(f"/expenses/{original['id']}/edit")
    assert edit_page.status_code == 404

    update = client.post(
        f"/edit-expense/{original['id']}",
        data=expense_form(app, description="Stolen", amount="1"),
    )
    assert update.status_code == 404

    delete = client.post(f"/expenses/{original['id']}/delete")
    assert delete.status_code == 404

    exported = client.get("/export-csv").get_data(as_text=True)
    assert "Asha lunch" not in exported

    with app.app_context():
        row = get_db().execute(
            "SELECT description, amount FROM expenses WHERE id = ?",
            (original["id"],),
        ).fetchone()
    assert row["description"] == "Asha lunch"
    assert row["amount"] == 250

    form = client.get("/expenses/new")
    assert b"Street food" not in form.data
