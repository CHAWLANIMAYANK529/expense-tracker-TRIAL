from collections import defaultdict

from app.services.periods import add_months, start_of_month

MIN_PERCENT = 40
MIN_RUPEES = 500
MIN_HISTORY_MONTHS = 2
HISTORY_MONTHS = 6

EXPLANATION = (
    "For each category, this month's total is compared with the average of up to "
    "six earlier calendar months in which that category had spending. A category is "
    "listed only when there are at least two earlier months, the change is at least "
    "40%, and the rupee difference is at least ₹500. Months with no spending in that "
    "category are left out of the average. A category with no spending this month is "
    "not listed. This month is counted as it stands today, even if the month is not over. "
    "Higher than your historical average, or lower than it, is a comparison with your "
    "own history — not a judgment about the purchase."
)


def detect_unusual(expenses, today, history_months=HISTORY_MONTHS):
    """Flag category totals that differ from the user's own recent average."""
    current_key = (today.year, today.month)
    history_keys = _previous_month_keys(today, history_months)
    current_totals = defaultdict(float)
    history_totals = defaultdict(lambda: defaultdict(float))

    for expense in expenses:
        parsed = _month_key(expense.get("date"))
        category = (expense.get("category") or "").strip()
        if parsed is None or not category:
            continue
        try:
            amount = float(expense["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        if parsed == current_key:
            # Expenses dated later this month are not spending yet.
            if str(expense.get("date"))[:10] > today.isoformat():
                continue
            current_totals[category] += amount
        elif parsed in history_keys:
            history_totals[category][parsed] += amount

    flags = []
    for category, current in current_totals.items():
        current = round(current, 2)
        if current <= 0:
            continue
        monthly_values = [
            round(history_totals[category][key], 2)
            for key in history_keys
            if history_totals[category][key] > 0
        ]
        if len(monthly_values) < MIN_HISTORY_MONTHS:
            continue
        average = round(sum(monthly_values) / len(monthly_values), 2)
        if average <= 0:
            continue
        difference = round(current - average, 2)
        percent = int(round(difference / average * 100))
        if abs(percent) < MIN_PERCENT or abs(difference) < MIN_RUPEES:
            continue
        flags.append(
            {
                "category": category,
                "current": current,
                "average": average,
                "difference_amount": difference,
                "difference_percent": percent,
                "direction": "higher" if difference > 0 else "lower",
                "months_compared": len(monthly_values),
            }
        )
    flags.sort(key=lambda item: abs(item["difference_percent"]), reverse=True)
    return flags


def _previous_month_keys(today, count):
    keys = set()
    cursor = start_of_month(today)
    for _ in range(count):
        cursor = add_months(cursor, -1)
        keys.add((cursor.year, cursor.month))
    return keys


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
