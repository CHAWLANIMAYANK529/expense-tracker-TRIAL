"""Optional demo data. Run from the repository root: python seed.py

Re-running replaces only the demo user's transactions and sets that account's
monthly budget to ₹20,000. Other accounts are left alone.
"""

import calendar
from datetime import date

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, get_or_create_category
from app.services.periods import add_months, start_of_month

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo12345"
DEMO_NAME = "Demo User"
DEMO_BUDGET = 20000

FOOD_SPLITS = [
    [1800, 1200, 900, 900],
    [2000, 1500, 1100, 700],
    [1600, 1400, 1200, 800],
    [1900, 1300, 1000, 700],
    [2100, 1400, 1200, 800],
    [2800, 2200, 1800, 1620],
]
FOOD_NAMES = ["Groceries", "Restaurant", "Swiggy", "Cafe Coffee Day"]
FOOD_DAYS = [3, 10, 16, 22]
TRANSPORT = [
    ("Uber", 200, "Metro", 1500),
    ("Uber", 900, "Metro", 900),
    ("Uber", 400, "Metro", 1500),
    ("Uber", 1200, "Metro", 550),
    ("Uber", 300, "Metro", 1550),
    ("Uber", 700, "Metro", 1100),
]
SHOPPING = [2000, 2200, 1800, 2400, None]


def build_demo_expenses(today):
    """Return deterministic transactions ending in the month of `today`.

    The five months before `today` average ₹5,100 of food. The current month is
    ₹8,420, which is 65% higher. Netflix, Spotify, and Internet repeat monthly.
    """
    months = [add_months(start_of_month(today), offset) for offset in range(-5, 1)]
    rows = []

    def add(month, day, description, amount, category, payment, notes="", clamp=True):
        placed = _place(month, day, today, clamp)
        if placed is None:
            return
        rows.append(
            {
                "date": placed.isoformat(),
                "description": description,
                "amount": amount,
                "category": category,
                "payment_method": payment,
                "notes": notes,
            }
        )

    for index, month in enumerate(months):
        for amount, name, day in zip(FOOD_SPLITS[index], FOOD_NAMES, FOOD_DAYS):
            add(month, day, name, amount, "Food", "UPI")
        uber_name, uber_amount, metro_name, metro_amount = TRANSPORT[index]
        add(month, 6, uber_name, uber_amount, "Transport", "UPI")
        add(month, 18, metro_name, metro_amount, "Transport", "Cash")
        if index < len(SHOPPING) and SHOPPING[index] is not None:
            add(month, 14, "Amazon", SHOPPING[index], "Shopping", "Card")
        add(month, 5, "Netflix", 649, "Entertainment", "Card", clamp=False)
        add(month, 8, "Spotify", 119, "Entertainment", "UPI", clamp=False)
        add(month, 2, "Internet", 999, "Bills", "Net Banking", clamp=False)

    previous = months[4]
    add(previous, 12, "Laptop", 8500, "Shopping", "Card", "One-off purchase")
    current = months[5]
    add(current, 9, "Amazon", 1200, "Shopping", "Card")
    add(current, 19, "Department store", 900, "Shopping", "Cash")
    add(months[2], 11, "Pharmacy", 450, "Health", "UPI")
    add(months[1], 20, "Course fee", 1500, "Education", "Net Banking")
    add(months[3], 15, "Train tickets", 2400, "Travel", "UPI")
    return rows


def main():
    app = create_app()
    with app.app_context():
        connection = get_db()
        user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (DEMO_EMAIL,),
        ).fetchone()
        if user is None:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, ?)",
                (DEMO_NAME, DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD), DEMO_BUDGET),
            )
            user_id = cursor.lastrowid
            created = True
        else:
            user_id = user["id"]
            created = False
            connection.execute(
                "UPDATE users SET budget = ? WHERE id = ?",
                (DEMO_BUDGET, user_id),
            )

        connection.execute("DELETE FROM imported_transactions WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM import_batches WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM import_previews WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))

        today = date.today()
        rows = build_demo_expenses(today)
        for row in rows:
            category_id = get_or_create_category(connection, user_id, row["category"])
            connection.execute(
                """
                INSERT INTO expenses (
                    user_id, description, amount, category_id, date, payment_method, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    row["description"],
                    row["amount"],
                    category_id,
                    row["date"],
                    row["payment_method"],
                    row["notes"],
                ),
            )
        connection.execute(
            """
            INSERT INTO budgets (user_id, year, month, amount)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, today.year, today.month, DEMO_BUDGET),
        )
        connection.commit()

    print(f"Demo account: {DEMO_EMAIL}")
    if created:
        print(f"Password: {DEMO_PASSWORD}")
    else:
        print("Password was left unchanged. Re-running replaced this account's transactions.")
    print(f"Inserted {len(rows)} transactions through {today.isoformat()}.")
    print(f"Monthly budget set to ₹{DEMO_BUDGET:,}.")


def _place(month, day, today, clamp):
    last = calendar.monthrange(month.year, month.month)[1]
    planned = date(month.year, month.month, min(day, last))
    if planned <= today:
        return planned
    if clamp and planned.year == today.year and planned.month == today.month:
        return today
    return None


if __name__ == "__main__":
    main()
