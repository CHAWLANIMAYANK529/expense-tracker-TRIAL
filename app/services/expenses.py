import sqlite3

from flask import current_app

from app.constants import PAYMENT_METHODS, PER_PAGE
from app.db import DatabaseError, get_db, get_or_create_category
from app.services.text import like_contains, transaction_fingerprint

SORTS = {
    "date_desc": "e.date DESC, e.id DESC",
    "date_asc": "e.date ASC, e.id ASC",
    "amount_desc": "e.amount DESC, e.id DESC",
    "amount_asc": "e.amount ASC, e.id ASC",
}


def list_categories(user_id):
    rows = get_db().execute(
        """
        SELECT id, name, user_id
        FROM categories
        WHERE user_id IS NULL OR user_id = ?
        ORDER BY user_id IS NOT NULL, name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def allowed_category_ids(user_id):
    return {row["id"] for row in list_categories(user_id)}


def load_expenses(user_id, start=None, end=None):
    sql = """
        SELECT e.id, e.description, e.amount, e.date, e.payment_method, e.notes,
               c.name AS category
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE e.user_id = ?
    """
    params = [user_id]
    if start is not None:
        sql += " AND e.date >= ?"
        params.append(start.isoformat())
    if end is not None:
        sql += " AND e.date <= ?"
        params.append(end.isoformat())
    sql += " ORDER BY e.date ASC, e.id ASC"
    return [dict(row) for row in get_db().execute(sql, params)]


def query_expenses(user_id, filters, page, per_page=PER_PAGE):
    where = ["e.user_id = ?"]
    params = [user_id]
    if filters.get("search"):
        where.append(
            "(e.description LIKE ? ESCAPE '\\' OR IFNULL(e.notes, '') LIKE ? ESCAPE '\\')"
        )
        pattern = like_contains(filters["search"])
        params.extend([pattern, pattern])
    if filters.get("category_id"):
        where.append("e.category_id = ?")
        params.append(filters["category_id"])
    if filters.get("date_from"):
        where.append("e.date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("e.date <= ?")
        params.append(filters["date_to"])
    if filters.get("amount_min") is not None:
        where.append("e.amount >= ?")
        params.append(filters["amount_min"])
    if filters.get("amount_max") is not None:
        where.append("e.amount <= ?")
        params.append(filters["amount_max"])
    if filters.get("payment_method") in PAYMENT_METHODS:
        where.append("e.payment_method = ?")
        params.append(filters["payment_method"])

    where_sql = " AND ".join(where)
    order_sql = SORTS.get(filters.get("sort"), SORTS["date_desc"])
    total = get_db().execute(
        f"SELECT COUNT(*) AS count FROM expenses e WHERE {where_sql}",
        params,
    ).fetchone()["count"]
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), pages)
    offset = (page - 1) * per_page
    rows = get_db().execute(
        f"""
        SELECT e.id, e.description, e.amount, e.date, e.payment_method, e.notes,
               c.name AS category
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        [*params, per_page, offset],
    ).fetchall()
    return [dict(row) for row in rows], total, page, pages


def get_expense(user_id, expense_id):
    row = get_db().execute(
        """
        SELECT e.id, e.description, e.amount, e.date, e.payment_method, e.notes,
               e.category_id, c.name AS category
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE e.id = ? AND e.user_id = ?
        """,
        (expense_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def create_expense(user_id, cleaned):
    connection = get_db()
    try:
        category_id = _resolve_category(connection, user_id, cleaned)
        cursor = connection.execute(
            """
            INSERT INTO expenses (
                user_id, description, amount, category_id, date, payment_method, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                cleaned["description"],
                cleaned["amount"],
                category_id,
                cleaned["date"].isoformat(),
                cleaned["payment_method"],
                cleaned["notes"],
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.Error as exc:
        connection.rollback()
        current_app.logger.exception("Could not create expense")
        raise DatabaseError("The expense could not be saved. Please try again.") from exc


def update_expense(user_id, expense_id, cleaned):
    connection = get_db()
    try:
        category_id = _resolve_category(connection, user_id, cleaned)
        cursor = connection.execute(
            """
            UPDATE expenses
            SET description = ?, amount = ?, category_id = ?, date = ?,
                payment_method = ?, notes = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                cleaned["description"],
                cleaned["amount"],
                category_id,
                cleaned["date"].isoformat(),
                cleaned["payment_method"],
                cleaned["notes"],
                expense_id,
                user_id,
            ),
        )
        connection.commit()
        return cursor.rowcount == 1
    except sqlite3.Error as exc:
        connection.rollback()
        current_app.logger.exception("Could not update expense")
        raise DatabaseError("The expense could not be updated. Please try again.") from exc


def delete_expense(user_id, expense_id):
    connection = get_db()
    try:
        cursor = connection.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        connection.commit()
        return cursor.rowcount == 1
    except sqlite3.Error as exc:
        connection.rollback()
        current_app.logger.exception("Could not delete expense")
        raise DatabaseError("The expense could not be deleted. Please try again.") from exc


def existing_fingerprints(user_id):
    rows = get_db().execute(
        "SELECT date, description, amount FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {
        transaction_fingerprint(row["date"], row["description"], row["amount"])
        for row in rows
    }


def insert_imported_rows(user_id, filename, rows, preview_token=None):
    """Insert rows that have already been revalidated. One transaction for the batch.

    When preview_token is set, that preview is deleted in the same transaction.
    A second confirm then finds nothing to import.
    """
    connection = get_db()
    try:
        if preview_token:
            removed = connection.execute(
                "DELETE FROM import_previews WHERE token = ? AND user_id = ?",
                (preview_token, user_id),
            )
            if removed.rowcount != 1:
                connection.rollback()
                raise DatabaseError("This import preview has expired. Upload the CSV again.")
        cursor = connection.execute(
            """
            INSERT INTO import_batches (user_id, filename, created_at, imported_count, skipped_count)
            VALUES (?, ?, datetime('now'), 0, 0)
            """,
            (user_id, filename),
        )
        batch_id = cursor.lastrowid
        imported = 0
        for row in rows:
            category_id = get_or_create_category(connection, user_id, row["category"])
            expense_cursor = connection.execute(
                """
                INSERT INTO expenses (
                    user_id, description, amount, category_id, date, payment_method, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
                INSERT INTO imported_transactions (
                    batch_id, user_id, expense_id, source_row, fingerprint
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    user_id,
                    expense_cursor.lastrowid,
                    row["line"],
                    row["fingerprint"],
                ),
            )
            imported += 1
        connection.execute(
            "UPDATE import_batches SET imported_count = ? WHERE id = ?",
            (imported, batch_id),
        )
        connection.commit()
        return imported
    except sqlite3.Error as exc:
        connection.rollback()
        current_app.logger.exception("Could not import transactions")
        raise DatabaseError("The import could not be saved. No rows were added.") from exc


def _resolve_category(connection, user_id, cleaned):
    if cleaned.get("new_category"):
        return get_or_create_category(connection, user_id, cleaned["new_category"])
    return cleaned["category_id"]
