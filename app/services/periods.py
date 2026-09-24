import calendar
from datetime import date, timedelta

from app.services.validation import parse_date


def start_of_month(day):
    return day.replace(day=1)


def add_months(day, months):
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def months_in_range(start, end):
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def iter_months(start, end):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month == 13:
            month = 1
            year += 1


def resolve_period(preset, today, start_text="", end_text=""):
    """Return (start, end, error) for an analytics preset.

    "This month", "last 3 months", "last 6 months", and "this year" end today,
    so the figures are month-to-date rather than a forecast of the rest of the month.
    "Last month" is the previous full calendar month.
    """
    preset = preset or "this_month"
    if preset == "this_month":
        return start_of_month(today), today, None
    if preset == "last_month":
        end = start_of_month(today) - timedelta(days=1)
        return start_of_month(end), end, None
    if preset == "last_3_months":
        return start_of_month(add_months(today, -2)), today, None
    if preset == "last_6_months":
        return start_of_month(add_months(today, -5)), today, None
    if preset == "this_year":
        return date(today.year, 1, 1), today, None
    if preset == "custom":
        try:
            start = parse_date(start_text)
            end = parse_date(end_text)
        except ValueError:
            return None, None, "Enter a valid start and end date."
        if start > end:
            return None, None, "The start date must be on or before the end date."
        if (end - start).days > 366 * 5:
            return None, None, "Choose a range of 5 years or fewer."
        return start, end, None
    return None, None, "Choose a time period."


PERIOD_OPTIONS = [
    ("this_month", "This month"),
    ("last_month", "Last month"),
    ("last_3_months", "Last 3 months"),
    ("last_6_months", "Last 6 months"),
    ("this_year", "This year"),
    ("custom", "Custom date range"),
]
