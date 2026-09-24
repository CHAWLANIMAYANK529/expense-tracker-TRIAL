from datetime import date, timedelta

from app.services.recurring import detect_recurring
from seed import build_demo_expenses


def _monthly(description, amount, start, months=4):
    rows = []
    for index in range(months):
        day = start + timedelta(days=30 * index)
        rows.append(
            {
                "description": description,
                "amount": amount,
                "date": day.isoformat(),
                "category": "Bills",
            }
        )
    return rows


def test_monthly_amounts_are_detected():
    rows = _monthly("Netflix", 649, date(2026, 1, 5))
    found = detect_recurring(rows)
    assert len(found) == 1
    assert found[0]["description"] == "Netflix"
    assert found[0]["amount"] == 649
    assert found[0]["label"] == "Approx. monthly"


def test_punctuation_and_case_still_match():
    rows = _monthly("NETFLIX!", 649, date(2026, 1, 5))
    found = detect_recurring(rows)
    assert found[0]["cadence"] == "monthly"


def test_two_occurrences_are_not_enough():
    rows = _monthly("Netflix", 649, date(2026, 1, 5), months=2)
    assert detect_recurring(rows) == []


def test_irregular_amounts_are_not_recurring():
    rows = [
        {"description": "Uber", "amount": amount, "date": f"2026-0{index}-05", "category": "Transport"}
        for index, amount in enumerate([200, 900, 400, 1500], start=1)
    ]
    assert detect_recurring(rows) == []


def test_demo_data_detects_the_three_bills():
    found = detect_recurring(build_demo_expenses(date(2026, 9, 24)))
    labels = {item["description"]: item["label"] for item in found}
    assert labels["Netflix"] == "Approx. monthly"
    assert labels["Spotify"] == "Approx. monthly"
    assert labels["Internet"] == "Approx. monthly"
    assert set(labels) == {"Netflix", "Spotify", "Internet"}
