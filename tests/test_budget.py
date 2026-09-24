from datetime import date

from app.services.budget import budget_snapshot
from tests.conftest import expense_form, login, register


def test_budget_math_matches_the_examples():
    healthy = budget_snapshot(14200, 20000)
    assert healthy["remaining"] == 5800
    assert healthy["percent"] == 71
    assert healthy["level"] == "ok"

    warning = budget_snapshot(850, 1000)
    assert warning["percent"] == 85
    assert warning["level"] == "warning"
    assert warning["message"] == "You have used 85% of your monthly budget."

    exact = budget_snapshot(1000, 1000)
    assert exact["level"] == "exceeded"
    assert exact["message"] == "Your monthly budget has been exceeded."

    over = budget_snapshot(1500, 1000)
    assert over["remaining"] == -500
    assert over["level"] == "exceeded"

    unset = budget_snapshot(100, 0)
    assert unset["configured"] is False

    rounds_up_to_warning = budget_snapshot(799, 1000)
    assert rounds_up_to_warning["percent"] == 80
    assert rounds_up_to_warning["level"] == "warning"

    rounds_up_to_exceeded = budget_snapshot(996, 1000)
    assert rounds_up_to_exceeded["percent"] == 100
    assert rounds_up_to_exceeded["level"] == "exceeded"
    assert rounds_up_to_exceeded["message"] == "Your monthly budget has been exceeded."


def test_dashboard_shows_warning_and_exceeded_from_real_rows(client, app):
    register(client)
    login(client)
    saved = client.post("/set-budget", data={"budget": "1000"}, follow_redirects=True)
    assert b"Monthly budget saved." in saved.data
    saved_page = saved.get_data(as_text=True)
    assert 'value="1000"' in saved_page
    assert 'value="1000.0"' not in saved_page

    today = date.today().isoformat()
    client.post("/expenses/new", data=expense_form(app, amount="850", date=today, description="Dinner"))
    warning = client.get("/dashboard")
    assert b"You have used 85% of your monthly budget." in warning.data
    assert _text(warning, "month-spending") == "₹850"
    assert _text(warning, "budget-remaining") == "₹150"

    client.post("/expenses/new", data=expense_form(app, amount="200", date=today, description="Snack"))
    exceeded = client.get("/dashboard")
    assert b"Your monthly budget has been exceeded." in exceeded.data


def test_dashboard_totals_come_from_stored_expenses(client, app):
    import calendar
    import json
    import re

    register(client)
    login(client)
    today = date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    future = date(today.year, today.month, last)
    assert future > today or future == today
    if future == today:
        future = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)

    client.post("/expenses/new", data=expense_form(app, description="Coffee", amount="100", date=today.isoformat()))
    client.post("/expenses/new", data=expense_form(app, description="Rent later", amount="5000", date=future.isoformat()))

    page = client.get("/dashboard")
    body = page.get_data(as_text=True)
    assert _text(page, "month-spending") == "₹100"
    assert _text(page, "total-spending") == "₹5,100"
    charts = json.loads(re.search(r'id="chart-data"[^>]*>(.*?)</script>', body).group(1))
    assert charts["month_values"][-1] == 100
    assert sum(charts["category_values"]) == 100

    everything = client.get("/dashboard?range=all")
    all_charts = json.loads(
        re.search(r'id="chart-data"[^>]*>(.*?)</script>', everything.get_data(as_text=True)).group(1)
    )
    assert sum(all_charts["category_values"]) == 5100


def _text(response, element_id):
    import re

    match = re.search(rf'id="{element_id}"[^>]*>([^<]+)', response.get_data(as_text=True))
    assert match, element_id
    return match.group(1).strip()
