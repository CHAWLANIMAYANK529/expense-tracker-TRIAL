# Expense Tracker 2.0

Personal finance analytics for one person. You record expenses, set a monthly budget, import and export CSV files, and review spending patterns calculated from your own transactions.

The dashboard does not use sample numbers. Every total, chart, budget percentage, recurring group, and unusual-spending flag is computed from the SQLite database when the page loads.

## Features

- Register and log in. Passwords are hashed with Werkzeug.
- Add, edit, and delete expenses. Each expense has an amount, category, description, date, payment method, and optional notes.
- Built-in categories: Food, Transport, Shopping, Bills, Entertainment, Health, Education, Travel, and Other. You can also create your own.
- Search, filter, and sort the transaction list. Long lists are paginated.
- Monthly budget with a progress bar. A warning appears at 80%. At 100% the page says the budget has been exceeded.
- Dashboard charts: category distribution, spending over time, and a six-month comparison.
- Analytics for this month, last month, the last 3 months, the last 6 months, this year, or a custom range.
- CSV import with a preview. Invalid rows and possible duplicates are shown before anything is saved.
- CSV export, with an optional date range.
- Detected recurring expenses, labeled as a heuristic rather than confirmed subscriptions.
- Unusual spending, compared with your own earlier months. The app does not judge a purchase as good or bad.

## Screenshots

Place images next to these captions when you capture them. The files are not in the repository yet.

- Dashboard — four totals, budget progress, and the three charts
- Analytics — period summary, category trend, unusual spending, detected recurring expenses
- Transactions — filters, sortable table, and CSV export
- Budget — spent, remaining, and the 80% warning
- CSV import — preview with invalid rows called out before confirm

## Tech stack

- Python
- Flask
- SQLite
- HTML, CSS, and JavaScript
- Bootstrap 5
- Chart.js

Gunicorn is included so the same app can be served in production. Pytest runs the tests. No other services are required.

## Installation

```bash
git clone https://github.com/CHAWLANIMAYANK529/expense-tracker.git
cd expense-tracker

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt

python run.py
```

Open http://127.0.0.1:5000

Set `SECRET_KEY` in the environment before you share the app with anyone else. If it is unset, the app creates `instance/secret_key` on first launch and reuses it. That file is gitignored.

```bash
# Linux/macOS
export SECRET_KEY="replace-this-with-a-long-random-string"

# Windows PowerShell
$env:SECRET_KEY="replace-this-with-a-long-random-string"
```

The database file is `database.db` in the project root. Override it with `DATABASE_PATH` if you want a different file.

## Demo data

`python seed.py` creates a demo account and replaces only that account's transactions. Other users are left alone. The script prints how many rows it inserted. The dashboard then calculates the totals; they are not hard-coded.

- Email: `demo@example.com`
- Password: `demo12345` (only when the account is created for the first time)
- Monthly budget: ₹20,000

The generated months end in the current month. Food in the current month is about 65% above the average of the five months before it, so the unusual-spending section has a real example. Netflix, Spotify, and Internet repeat on a monthly gap so the recurring detector has something to find.

A valid import sample is `examples/sample_transactions.csv`. A file with bad rows is `examples/sample_with_errors.csv`.

## Database

SQLite, in `database.db`. On startup the app creates any missing tables and upgrades an older expenses table in place. Existing users, password hashes, amounts, dates, and expense ids are kept. Older rows stored a category as text; those names are trimmed and linked to a category record. `title` is kept as `description`.

| Table | What it stores |
| --- | --- |
| `users` | Name, email, password hash, and the monthly budget amount |
| `categories` | Built-in categories (`user_id` is null) and categories a user created |
| `expenses` | One transaction: owner, description, amount, category, date, payment method, notes |
| `budgets` | The budget amount saved for a user for a specific year and month |
| `import_batches` | One confirmed CSV import |
| `imported_transactions` | Which expense came from which import row |
| `import_previews` | The checked CSV, held until the user confirms or it expires after 24 hours |

Recurring expenses and unusual spending are not stored. They are calculated from `expenses` when you open the dashboard or analytics page, so they cannot drift away from the transactions.

Foreign keys link expenses to users and categories, and import rows to the batch that created them. Indexes cover expenses by user and date, user and category, and user and amount.

An expense belongs to the user who created it. Queries that read or change an expense always include that user's id. Asking for someone else's expense id returns "not found".

## Analytics

### Budget

The monthly budget is the amount you save on the Budget page. A new account has no monthly budget until you save one. That value is stored on your user and on the `budgets` row for the current year and month.

Spent is the sum of your expenses dated from the first of this month through today. Remaining is the budget minus that sum, so it goes negative after the budget is passed. The percentage is spent divided by the budget.

- Below 80%: the bar and the numbers only
- From 80% up to, but not including, 100%: "You have used N% of your monthly budget."
- 100% or more: "Your monthly budget has been exceeded."

There is no other advice. A budget of zero is treated as "not set" so the page does not divide by zero.

### Recurring expense detection

This is ordinary Python, not a model. Transactions are grouped by description after lowercasing and removing punctuation, so `NETFLIX!` matches `Netflix`.

A group is listed only when all of these are true:

- The description appears at least three times.
- Every amount is within ₹5 or 15% of the median amount, whichever is larger.
- The gaps between dates line up with a weekly, two-week, monthly, quarterly, or yearly rhythm. At least 60% of the gaps have to sit near that rhythm.

The label says "Approx. monthly" (or weekly, and so on) because a regular merchant charge is not proof of a subscription. The page calls these "Detected recurring expenses".

### Unusual spending

For each category, this month's total is compared with the average of up to six earlier calendar months in which that category had spending. Months with no spending in that category are left out of the average. A category with no spending this month is not listed.

A category is listed only when:

- There are at least two earlier months.
- The change is at least 40%.
- The rupee difference is at least ₹500.

"Higher than your historical average" and "Lower than your historical average" are comparisons with your own history. This month is counted as it stands today, even if the month is not over, so a flag can appear before month-end.

### Other figures

For the period you select:

- Total spending is the sum of expenses in that date range.
- Average transaction is the total divided by the number of transactions.
- Average daily spending is the total divided by the number of days in the range, including days with no expenses.
- Average monthly spending is the total divided by the number of calendar months the range touches.
- The top category is the category with the largest sum.
- The largest transaction is the single highest amount.

"This month", "last 3 months", "last 6 months", and "this year" end today. "Last month" is the previous full calendar month. Custom dates are used only when that period is selected.

## Testing

The tests use a temporary SQLite file. They do not write to `database.db`.

```bash
pytest
```

They cover registration, login, expense create/edit/delete, user isolation, budget math, CSV validation and import, recurring detection, unusual spending, analytics totals, and upgrading an older database.

## Project layout

```text
expense-tracker/
├── app/
│   ├── routes/          # HTTP handlers
│   ├── services/        # budget, analytics, CSV, recurring, unusual spending
│   ├── templates/
│   ├── static/
│   ├── db.py            # schema and the in-place upgrade
│   └── security.py      # login required and CSRF
├── examples/            # sample CSV files
├── tests/
├── config.py
├── run.py
├── seed.py
├── requirements.txt
└── database.db
```

`expense-tracker/app.py` is a thin launcher for the old path. Use `python run.py` from the repository root.

## Limitations

- Amounts are stored as SQLite real numbers and rounded to paise on the way in. This is the same approach as the original app. It is fine for personal totals and is not a ledger.
- The currency is rupees. There is no multi-currency support.
- The budget is one number for the month, not a budget per category.
- There is no email verification and no password reset.
- Bootstrap and Chart.js are loaded from a CDN, so the first view needs a network connection for styling and charts.
- Recurring detection misses a subscription when the description changes from month to month, and it can group any repeated charge that happens to be regular.
- Unusual spending ignores a category you have not spent on yet this month, so "I stopped buying this" does not appear until there is some spending.
- CSV cells that start with `=`, `+`, `-`, or `@` are prefixed on export so a spreadsheet does not treat them as formulas.
- Logout is a POST from the sidebar. Opening `/logout` in the address bar does not end the session.
