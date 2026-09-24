import sqlite3
from datetime import date

from app.db import DatabaseError, get_db
from app.formatters import coerce_date
from app.services.analytics import chart_colors, daily_series, monthly_series, summarize
from app.services.anomalies import detect_unusual
from app.services.budget import budget_snapshot
from app.services.expenses import load_expenses
from app.services.periods import add_months, start_of_month
from app.services.recurring import detect_recurring


def build_dashboard(user_id, today=None, chart_range="month"):
    today = today or date.today()
    month_start = start_of_month(today)
    all_expenses = load_expenses(user_id)
    this_month = [
        item for item in all_expenses if month_start.isoformat() <= item["date"] <= today.isoformat()
    ]
    chart_start, chart_end, chart_label = _chart_window(chart_range, today, all_expenses)
    chart_expenses = [
        item
        for item in all_expenses
        if (chart_start is None or item["date"] >= chart_start.isoformat())
        and (chart_end is None or item["date"] <= chart_end.isoformat())
    ]
    category_summary = summarize(chart_expenses, chart_start or today, chart_end or today)
    if chart_range == "month":
        time_points = daily_series(chart_expenses, chart_start, chart_end)
        time_heading = "Spending by day"
    else:
        time_points = monthly_series(chart_expenses, chart_start, chart_end)
        time_heading = "Spending by month"

    comparison_start = start_of_month(add_months(today, -5))
    comparison = monthly_series(
        [
            item
            for item in all_expenses
            if comparison_start.isoformat() <= item["date"] <= today.isoformat()
        ],
        comparison_start,
        today,
    )
    budget_amount = current_budget_amount(user_id, today)
    snapshot = budget_snapshot(sum(item["amount"] for item in this_month), budget_amount)
    recent = sorted(all_expenses, key=lambda item: (item["date"], item["id"]), reverse=True)[:8]
    highest = sorted(all_expenses, key=lambda item: (float(item["amount"]), item["id"]), reverse=True)[:5]
    recurring = detect_recurring(all_expenses)
    unusual = detect_unusual(all_expenses, today)
    category_labels = [row["category"] for row in category_summary["categories"]]
    category_values = [row["total"] for row in category_summary["categories"]]
    return {
        "total": round(sum(float(item["amount"]) for item in all_expenses), 2),
        "count": len(all_expenses),
        "this_month": round(sum(float(item["amount"]) for item in this_month), 2),
        "month_start": month_start,
        "today": today,
        "budget": snapshot,
        "recent": recent,
        "highest": highest,
        "recurring": recurring[:3],
        "recurring_count": len(recurring),
        "unusual": unusual[:3],
        "unusual_count": len(unusual),
        "chart_range": chart_range,
        "chart_label": chart_label,
        "time_heading": time_heading,
        "charts": {
            "category_labels": category_labels,
            "category_values": category_values,
            "category_colors": chart_colors(len(category_labels)),
            "time_labels": [point["label"] for point in time_points],
            "time_values": [point["total"] for point in time_points],
            "month_labels": [point["label"] for point in comparison],
            "month_values": [point["total"] for point in comparison],
        },
    }


def current_budget_amount(user_id, today):
    row = get_db().execute(
        """
        SELECT amount FROM budgets
        WHERE user_id = ? AND year = ? AND month = ?
        """,
        (user_id, today.year, today.month),
    ).fetchone()
    if row:
        return row["amount"]
    user = get_db().execute("SELECT budget FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return 0
    return user["budget"] or 0


def save_budget(user_id, amount, today=None):
    today = today or date.today()
    connection = get_db()
    try:
        connection.execute("UPDATE users SET budget = ? WHERE id = ?", (amount, user_id))
        connection.execute(
            """
            INSERT INTO budgets (user_id, year, month, amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, year, month) DO UPDATE SET amount = excluded.amount
            """,
            (user_id, today.year, today.month, amount),
        )
        connection.commit()
    except sqlite3.Error as exc:
        connection.rollback()
        raise DatabaseError("The budget could not be saved. Please try again.") from exc


def _chart_window(chart_range, today, all_expenses):
    month_start = start_of_month(today)
    if chart_range == "six_months":
        return start_of_month(add_months(today, -5)), today, "Last 6 months"
    if chart_range == "all":
        earliest, latest = _date_bounds(all_expenses)
        end = latest if latest and latest > today else today
        return earliest or month_start, end, "All time"
    return month_start, today, "This month"


def _date_bounds(expenses):
    parsed = [day for day in (coerce_date(item.get("date")) for item in expenses) if day]
    if not parsed:
        return None, None
    return min(parsed), max(parsed)
