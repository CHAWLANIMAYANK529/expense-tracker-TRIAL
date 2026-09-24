from datetime import date

from tests.conftest import category_id, expense_form, login, register


def test_create_edit_and_delete_expense(client, app):
    register(client)
    login(client)
    created = client.post("/expenses/new", data=expense_form(app), follow_redirects=True)
    assert b"Expense added." in created.data
    assert b"Groceries" in created.data
    assert "₹450" in created.get_data(as_text=True)

    with app.app_context():
        from app.db import get_db

        expense_id = get_db().execute("SELECT id FROM expenses").fetchone()["id"]

    edit_page = client.get(f"/expenses/{expense_id}/edit")
    assert 'value="450"' in edit_page.get_data(as_text=True)
    assert 'value="450.0"' not in edit_page.get_data(as_text=True)

    edited = client.post(
        f"/expenses/{expense_id}/edit",
        data=expense_form(app, description="Groceries updated", amount="500"),
        follow_redirects=True,
    )
    assert b"Expense updated." in edited.data
    assert b"Groceries updated" in edited.data

    deleted = client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)
    assert b"Expense deleted." in deleted.data
    assert b"Groceries updated" not in deleted.data


def test_invalid_amount_is_not_saved(client, app):
    register(client)
    login(client)
    response = client.post(
        "/add-expense",
        data=expense_form(app, amount="-20", date=date.today().isoformat()),
    )
    assert b"Enter an amount greater than zero." in response.data
    with app.app_context():
        from app.db import get_db

        count = get_db().execute("SELECT COUNT(*) AS count FROM expenses").fetchone()["count"]
    assert count == 0


def test_missing_expense_returns_404(client):
    register(client)
    login(client)
    response = client.get("/expenses/999/edit")
    assert response.status_code == 404


def test_search_filters_description_and_ignores_injection(client, app):
    register(client)
    login(client)
    client.post("/expenses/new", data=expense_form(app, description="Metro card", notes=""))
    client.post(
        "/expenses/new",
        data=expense_form(app, description="Pharmacy", notes="keep this private", category_id=category_id(app, "Health")),
    )
    by_note = client.get("/transactions?search=private")
    assert b"Pharmacy" in by_note.data
    assert b"Metro card" not in by_note.data

    injected = client.get("/transactions?search=%25' OR 1=1 --")
    assert b"Metro card" not in injected.data
    assert b"Pharmacy" not in injected.data


def test_pagination(client, app):
    register(client)
    login(client)
    for index in range(11):
        client.post(
            "/expenses/new",
            data=expense_form(app, description=f"Item {index}", amount=str(index + 1), date=f"2026-09-{index + 1:02d}"),
        )
    first = client.get("/transactions")
    second = client.get("/transactions?page=2")
    assert b"Page 1 of 2" in first.data
    assert b"Page 2 of 2" in second.data
    assert b"Item 0" in second.data or b"Item 10" in second.data


def test_invalid_filters_are_dropped_from_later_links(client, app):
    register(client)
    login(client)
    client.post("/expenses/new", data=expense_form(app, description="Item"))
    ignored = client.get("/transactions?date_from=not-a-date&amount_min=0&search=Item")
    body = ignored.get_data(as_text=True)
    assert "date from filter was ignored" in body
    assert "not-a-date" not in body
    assert "amount min filter was ignored" not in body
    assert 'name="amount_min" value="0.0"' in body


def test_custom_category_is_saved(client, app):
    register(client)
    login(client)
    custom = client.post(
        "/expenses/new",
        data=expense_form(app, description="Chaat", amount="80", new_category="Street food"),
        follow_redirects=True,
    )
    assert b"Street food" in custom.data
    assert b"Chaat" in custom.data
