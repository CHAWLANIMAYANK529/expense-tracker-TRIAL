import math
from datetime import date, datetime


def plain_amount(value):
    """Render an amount for an input. Whole rupees omit the decimal."""
    number = round(float(value), 2)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}"


def format_inr(value):
    """Format a number as rupees with thousands separators. Whole amounts omit paise."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "₹0"
    if not math.isfinite(amount):
        return "₹0"
    sign = "-" if amount < 0 else ""
    rounded = round(abs(amount), 2)
    if abs(rounded - round(rounded)) < 0.001:
        body = f"{int(round(rounded)):,}"
    else:
        body = f"{rounded:,.2f}"
    return f"{sign}₹{body}"


def short_date(value):
    """Format a date as 'Aug 21, 2026'."""
    parsed = coerce_date(value)
    if parsed is None:
        return "" if value in (None, "") else str(value)
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def coerce_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
