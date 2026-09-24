import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

from app.constants import DEFAULT_CATEGORIES


class DatabaseError(Exception):
    """A database operation failed. The message is safe to show to a user."""


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        g.db = connection
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_schema(connection)
        connection.commit()
    finally:
        connection.close()


def ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            budget REAL
        )
        """
    )
    user_columns = _column_names(connection, "users")
    if user_columns and "budget" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN budget REAL")
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_nocase
        ON users(email COLLATE NOCASE)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, year, month)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            imported_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS import_previews (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_builtin
        ON categories(name COLLATE NOCASE)
        WHERE user_id IS NULL
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_custom
        ON categories(user_id, name COLLATE NOCASE)
        WHERE user_id IS NOT NULL
        """
    )

    # Built-in categories must exist before legacy rows are matched to them.
    seed_default_categories(connection)

    expense_columns = _column_names(connection, "expenses")
    if not expense_columns:
        _create_expenses(connection)
    elif "description" not in expense_columns:
        _migrate_legacy_expenses(connection)

    # Created after expenses so the foreign key points at the upgraded table.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS imported_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            expense_id INTEGER,
            source_row INTEGER,
            fingerprint TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE SET NULL
        )
        """
    )

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_user_category ON expenses(user_id, category_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_user_amount ON expenses(user_id, amount)"
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_imported_fingerprint
        ON imported_transactions(user_id, fingerprint)
        """
    )


def seed_default_categories(connection):
    for name in DEFAULT_CATEGORIES:
        connection.execute(
            "INSERT OR IGNORE INTO categories (user_id, name) VALUES (NULL, ?)",
            (name,),
        )


def _create_expenses(connection):
    connection.execute(
        """
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            category_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Other',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
        """
    )


def _migrate_legacy_expenses(connection):
    """Copy the original expenses table (title/category text) into the new schema.

    Existing ids, amounts, dates, and the owning user are preserved.
    Category names are trimmed and linked to a category row.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    legacy_rows = list(connection.execute("SELECT * FROM expenses"))
    connection.execute("ALTER TABLE expenses RENAME TO expenses_old")
    try:
        _create_expenses(connection)
        for row in legacy_rows:
            description = str(row["title"] or "").strip() or "Untitled"
            category_name = str(row["category"] or "").strip() or "Other"
            category_id = get_or_create_category(connection, row["user_id"], category_name)
            amount = float(row["amount"])
            expense_date = str(row["date"] or "").strip()
            connection.execute(
                """
                INSERT INTO expenses (
                    id, user_id, description, amount, category_id, date,
                    payment_method, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, 'Other', '')
                """,
                (row["id"], row["user_id"], description, amount, category_id, expense_date),
            )
        connection.execute("DROP TABLE expenses_old")
    except Exception:
        connection.execute("DROP TABLE IF EXISTS expenses")
        connection.execute("ALTER TABLE expenses_old RENAME TO expenses")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def get_or_create_category(connection, user_id, name):
    cleaned = " ".join(str(name).split())
    if not cleaned:
        cleaned = "Other"
    existing = connection.execute(
        """
        SELECT id FROM categories
        WHERE name = ? COLLATE NOCASE
          AND (user_id IS NULL OR user_id = ?)
        ORDER BY user_id IS NULL
        LIMIT 1
        """,
        (cleaned, user_id),
    ).fetchone()
    if existing:
        return existing["id"]
    cursor = connection.execute(
        "INSERT INTO categories (user_id, name) VALUES (?, ?)",
        (user_id, cleaned),
    )
    return cursor.lastrowid


def _column_names(connection, table):
    if table not in {"users", "expenses", "categories"}:
        raise ValueError(f"Unexpected table {table}")
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def utc_now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
