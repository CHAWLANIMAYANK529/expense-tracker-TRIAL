from collections import defaultdict

from app.constants import CHART_COLORS
from app.services.periods import iter_months, months_in_range


def summarize(expenses, start, end):
    """Aggregate already-filtered expenses for one date range.

    Average daily spending divides by every day in the range, including days
    with no expenses. Average monthly spending divides by the number of calendar
    months the range touches.
    """
    total = round(sum(float(item["amount"]) for item in expenses), 2)
    count = len(expenses)
    days = max(1, (end - start).days + 1)
    month_count = max(1, months_in_range(start, end))
    category_totals = defaultdict(float)
    largest = None
    for item in expenses:
        amount = float(item["amount"])
        category_totals[item["category"]] += amount
        if largest is None or amount > float(largest["amount"]):
            largest = item
    categories = [
        {"category": name, "total": round(amount, 2)}
        for name, amount in sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
    ]
    for row in categories:
        row["share"] = round(row["total"] / total * 100, 1) if total else 0
    top_category = categories[0] if categories else None
    return {
        "total": total,
        "count": count,
        "average_transaction": round(total / count, 2) if count else 0,
        "average_daily": round(total / days, 2),
        "average_monthly": round(total / month_count, 2),
        "days": days,
        "month_count": month_count,
        "largest": largest,
        "top_category": top_category,
        "categories": categories,
        "months": monthly_series(expenses, start, end),
    }


def monthly_series(expenses, start, end):
    totals = defaultdict(float)
    for item in expenses:
        key = _month_key(item.get("date"))
        if key is None:
            continue
        totals[key] += float(item["amount"])
    points = []
    for year, month in iter_months(start, end):
        points.append(
            {
                "label": _month_label(year, month),
                "total": round(totals[(year, month)], 2),
            }
        )
    return points


def daily_series(expenses, start, end):
    from datetime import timedelta

    totals = defaultdict(float)
    for item in expenses:
        totals[str(item.get("date"))] += float(item["amount"])
    points = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        points.append({"label": f"{cursor.strftime('%b')} {cursor.day}", "total": round(totals[iso], 2)})
        cursor += timedelta(days=1)
    return points


def chart_colors(count):
    if count <= 0:
        return []
    return [CHART_COLORS[index % len(CHART_COLORS)] for index in range(count)]


def _month_label(year, month):
    from datetime import date

    return date(year, month, 1).strftime("%b %Y")


def _month_key(value):
    text = str(value or "")
    if len(text) < 7:
        return None
    try:
        year = int(text[0:4])
        month = int(text[5:7])
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None
    return year, month
