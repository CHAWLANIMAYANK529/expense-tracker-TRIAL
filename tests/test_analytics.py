from datetime import date

from app.services.analytics import summarize
from tests.conftest import expense_form, login, register


def test_summary_math():
    expenses = [
        {"description": "Dinner", "amount": 400, "date": "2026-09-02", "category": "Food"},
        {"description": "Laptop", "amount": 8500, "date": "2026-09-18", "category": "Shopping"},
        {"description": "Metro", "amount": 100, "date": "2026-08-04", "category": "Transport"},
    ]
    summary = summarize(expenses, date(2026, 8, 1), date(2026, 9, 30))
    assert summary["total"] == 9000
    assert summary["count"] == 3
    assert summary["average_transaction"] == 3000
    assert summary["largest"]["description"] == "Laptop"
    assert summary["top_category"]["category"] == "Shopping"
    assert summary["top_category"]["total"] == 8500
    assert summary["month_count"] == 2
    assert summary["average_monthly"] == 4500


def test_analytics_page_uses_database_totals(client, app):
    register(client)
    login(client)
    client.post("/expenses/new", data=expense_form(app, description="Laptop", amount="8500", date="2026-08-12", category_id=_category(app, "Shopping")))
    client.post("/expenses/new", data=expense_form(app, description="Dinner", amount="500", date="2026-08-02"))
    page = client.get("/analytics?period=custom&start=2026-08-01&end=2026-08-31")
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert _value(body, "analytics-total") == "₹9,000"
    assert _value(body, "analytics-count") == "2"
    assert _value(body, "analytics-average") == "₹4,500"
    assert _value(body, "analytics-largest") == "₹8,500"
    assert _value(body, "analytics-top-category") == "Shopping"
    assert "historical average" in body
    assert "not confirmed subscriptions" in body


def _category(app, name):
    from tests.conftest import category_id

    return category_id(app, name)


def _value(body, element_id):
    import re

    match = re.search(rf'id="{element_id}"[^>]*>([^<]+)', body)
    assert match, element_id
    return match.group(1).strip()
