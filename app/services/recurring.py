import statistics
from datetime import datetime

from app.services.text import normalize_description

MIN_OCCURRENCES = 3
# (name, typical gap in days, allowed distance from that gap)
CADENCES = (
    ("weekly", 7, 2),
    ("biweekly", 14, 3),
    ("monthly", 30, 5),
    ("quarterly", 91, 12),
    ("yearly", 365, 20),
)
CADENCE_LABELS = {
    "weekly": "Approx. weekly",
    "biweekly": "Approx. every two weeks",
    "monthly": "Approx. monthly",
    "quarterly": "Approx. quarterly",
    "yearly": "Approx. yearly",
}

EXPLANATION = (
    "A group is listed when the same description appears at least three times, "
    "every amount is within ₹5 or 15% of the typical amount (whichever is larger), "
    "and the gaps between dates line up with a weekly, two-week, monthly, quarterly, "
    "or yearly rhythm. Descriptions are compared after lowercasing and removing punctuation. "
    "These are detected recurring expenses, not confirmed subscriptions."
)


def detect_recurring(expenses):
    """Group transactions that look regularly repeated.

    The result is a heuristic. Callers should label it as detected, not as a subscription.
    """
    groups = {}
    for expense in expenses:
        key = normalize_description(expense.get("description"))
        if not key:
            continue
        groups.setdefault(key, []).append(expense)

    found = []
    for items in groups.values():
        if len(items) < MIN_OCCURRENCES:
            continue
        amounts = []
        dates = []
        for item in items:
            try:
                amounts.append(float(item["amount"]))
                dates.append(datetime.strptime(item["date"], "%Y-%m-%d"))
            except (KeyError, TypeError, ValueError):
                amounts = []
                break
        if len(amounts) < MIN_OCCURRENCES:
            continue
        median_amount = statistics.median(amounts)
        if median_amount <= 0:
            continue
        tolerance = max(5.0, median_amount * 0.15)
        if any(abs(amount - median_amount) > tolerance for amount in amounts):
            continue
        dates.sort()
        gaps = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
        if not gaps:
            continue
        median_gap = statistics.median(gaps)
        cadence = _match_cadence(gaps, median_gap)
        if not cadence:
            continue
        latest = max(items, key=lambda item: item["date"])
        found.append(
            {
                "description": latest["description"],
                "amount": round(float(median_amount), 2),
                "cadence": cadence,
                "label": CADENCE_LABELS[cadence],
                "occurrences": len(items),
                "last_date": latest["date"],
            }
        )
    found.sort(key=lambda item: (-item["amount"], item["description"].lower()))
    return found


def _match_cadence(gaps, median_gap):
    for name, target, tolerance in CADENCES:
        if abs(median_gap - target) > tolerance:
            continue
        close = sum(1 for gap in gaps if abs(gap - target) <= tolerance)
        if close / len(gaps) >= 0.6:
            return name
    return None
