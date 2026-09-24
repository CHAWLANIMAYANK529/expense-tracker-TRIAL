from datetime import date

from app.services.anomalies import detect_unusual
from seed import build_demo_expenses


def _month(category, year, month, amount):
    return {
        "description": category,
        "amount": amount,
        "date": f"{year}-{month:02d}-15",
        "category": category,
    }


def test_food_example_is_65_percent_above_average():
    history = [4800, 5300, 5000, 4900, 5500]
    rows = [_month("Food", 2026, month, amount) for month, amount in enumerate(history, start=4)]
    rows.append(_month("Food", 2026, 9, 8420))
    flags = detect_unusual(rows, today=date(2026, 9, 24))
    assert len(flags) == 1
    food = flags[0]
    assert food["category"] == "Food"
    assert food["current"] == 8420
    assert food["average"] == 5100
    assert food["difference_percent"] == 65
    assert food["direction"] == "higher"


def test_small_changes_are_ignored():
    rows = [_month("Transport", 2026, month, 1800) for month in range(4, 9)]
    rows.append(_month("Transport", 2026, 9, 1900))
    assert detect_unusual(rows, today=date(2026, 9, 24)) == []


def test_one_earlier_month_is_not_enough():
    rows = [_month("Health", 2026, 8, 400), _month("Health", 2026, 9, 2000)]
    assert detect_unusual(rows, today=date(2026, 9, 24)) == []


def test_future_days_this_month_are_not_counted_yet():
    rows = [_month("Food", 2026, month, 5000) for month in range(4, 9)]
    rows.append({"description": "Later", "amount": 8000, "date": "2026-09-30", "category": "Food"})
    rows.append({"description": "Today", "amount": 1000, "date": "2026-09-24", "category": "Food"})
    flags = detect_unusual(rows, today=date(2026, 9, 24))
    food = flags[0]
    assert food["current"] == 1000
    assert food["direction"] == "lower"


def test_demo_flags_food_and_not_a_judgment():
    flags = detect_unusual(build_demo_expenses(date(2026, 9, 24)), today=date(2026, 9, 24))
    assert [item["category"] for item in flags] == ["Food"]
    assert flags[0]["direction"] == "higher"
    assert flags[0]["difference_percent"] == 65
