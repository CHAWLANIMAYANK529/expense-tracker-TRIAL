import csv
import io
import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for

from app.db import DatabaseError, get_db, utc_now_stamp
from app.security import login_required
from app.services.csv_io import (
    CsvRejected,
    apply_duplicates,
    csv_safe,
    display_filename,
    parse_csv_text,
    revalidate_stored_row,
    summarize_rows,
)
from app.services.expenses import existing_fingerprints, insert_imported_rows, load_expenses
from app.services.validation import parse_date

bp = Blueprint("imports", __name__)


@bp.route("/import", methods=["GET"])
@login_required
def index():
    return render_template("import.html")


@bp.route("/import", methods=["POST"])
@login_required
def upload():
    upload_file = request.files.get("file")
    if upload_file is None or not upload_file.filename:
        flash("Choose a CSV file to upload.", "danger")
        return redirect(url_for("imports.index"))
    try:
        filename = display_filename(upload_file.filename)
    except CsvRejected as exc:
        flash(exc.message, "danger")
        return redirect(url_for("imports.index"))

    raw = upload_file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("CSV must be UTF-8 encoded.", "danger")
        return redirect(url_for("imports.index"))

    try:
        rows = parse_csv_text(text)
    except CsvRejected as exc:
        flash(exc.message, "danger")
        return redirect(url_for("imports.index"))

    apply_duplicates(rows, existing_fingerprints(session["user_id"]))
    token = _store_preview(session["user_id"], filename, rows)
    return redirect(url_for("imports.preview", token=token))


@bp.route("/import/preview/<token>")
@login_required
def preview(token):
    stored = _load_preview(session["user_id"], token)
    if stored is None:
        flash("This import preview has expired. Upload the CSV again.", "warning")
        return redirect(url_for("imports.index"))
    summary = summarize_rows(stored["rows"])
    return render_template(
        "import_preview.html",
        token=token,
        filename=stored["filename"],
        rows=stored["rows"],
        summary=summary,
    )


@bp.route("/import/preview/<token>", methods=["POST"])
@login_required
def confirm(token):
    stored = _load_preview(session["user_id"], token)
    if stored is None:
        flash("This import preview has expired. Upload the CSV again.", "warning")
        return redirect(url_for("imports.index"))

    include_duplicates = request.form.get("include_duplicates") == "1"
    checked = [revalidate_stored_row(row) for row in stored["rows"]]
    apply_duplicates(checked, existing_fingerprints(session["user_id"]))
    chosen = []
    skipped_invalid = 0
    skipped_duplicates = 0
    for row in checked:
        if row["errors"]:
            skipped_invalid += 1
            continue
        if row["duplicate"] and not include_duplicates:
            skipped_duplicates += 1
            continue
        chosen.append(row)

    if not chosen:
        flash("No transactions were imported. Fix the invalid rows or include duplicates.", "warning")
        return redirect(url_for("imports.preview", token=token))

    try:
        imported = insert_imported_rows(
            session["user_id"],
            stored["filename"],
            chosen,
            preview_token=token,
        )
    except DatabaseError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("imports.preview", token=token))
    parts = [f"Imported {imported} transaction{'s' if imported != 1 else ''}."]
    if skipped_invalid:
        parts.append(f"Skipped {skipped_invalid} invalid row{'s' if skipped_invalid != 1 else ''}.")
    if skipped_duplicates:
        parts.append(
            f"Skipped {skipped_duplicates} possible duplicate{'s' if skipped_duplicates != 1 else ''}."
        )
    flash(" ".join(parts), "success")
    return redirect(url_for("expenses.index"))


@bp.route("/export-csv")
@login_required
def export_csv():
    start, end, error = _export_range()
    if error:
        flash(error, "danger")
        return redirect(url_for("expenses.index"))
    expenses = load_expenses(session["user_id"], start, end)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Date", "Description", "Amount", "Category", "Payment Method", "Notes"])
    for expense in expenses:
        writer.writerow(
            [
                csv_safe(expense["date"]),
                csv_safe(expense["description"]),
                csv_safe(f"{float(expense['amount']):.2f}"),
                csv_safe(expense["category"]),
                csv_safe(expense["payment_method"]),
                csv_safe(expense["notes"]),
            ]
        )
    payload = buffer.getvalue()
    response = Response(payload, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    return response


def _export_range():
    start = _optional_query_date("date_from")
    end = _optional_query_date("date_to")
    if request.args.get("date_from") and start is None:
        return None, None, "Enter a valid start date for the export."
    if request.args.get("date_to") and end is None:
        return None, None, "Enter a valid end date for the export."
    if start and end and start > end:
        return None, None, "The export start date must be on or before the end date."
    return start, end, None


def _optional_query_date(name):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return parse_date(raw, error="Invalid date")
    except ValueError:
        return None


def _store_preview(user_id, filename, rows):
    import secrets

    _purge_old_previews()
    token = secrets.token_urlsafe(24)
    get_db().execute(
        """
        INSERT INTO import_previews (token, user_id, filename, payload, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, user_id, filename, json.dumps(rows), utc_now_stamp()),
    )
    get_db().commit()
    return token


def _load_preview(user_id, token):
    row = get_db().execute(
        """
        SELECT filename, payload, created_at
        FROM import_previews
        WHERE token = ? AND user_id = ?
        """,
        (token, user_id),
    ).fetchone()
    if row is None:
        return None
    created = datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(hours=24):
        _delete_preview(token)
        return None
    return {"filename": row["filename"], "rows": json.loads(row["payload"])}


def _delete_preview(token):
    get_db().execute("DELETE FROM import_previews WHERE token = ?", (token,))
    get_db().commit()


def _purge_old_previews():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    get_db().execute("DELETE FROM import_previews WHERE created_at < ?", (cutoff,))
