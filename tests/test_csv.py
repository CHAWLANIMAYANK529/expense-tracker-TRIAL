import io
from urllib.parse import urlparse

from app.services.csv_io import (
    CsvRejected,
    apply_duplicates,
    csv_safe,
    display_filename,
    parse_csv_text,
    revalidate_stored_row,
)
from tests.conftest import expense_form, login, register


SAMPLE = """date,description,amount,category
2026-08-01,Uber,320,Transport
2026-08-02,Restaurant,850,Food
not-a-date,Coffee,100,Food
2026-08-05,Grocery,-20,Food
2026-08-06,,400,Bills
"""


def test_csv_validation_reports_row_errors():
    rows = parse_csv_text(SAMPLE)
    invalid = [row for row in rows if row["errors"]]
    assert len(invalid) == 3
    by_line = {row["line"]: row["errors"] for row in invalid}
    assert by_line[4] == ["Invalid date"]
    assert by_line[5] == ["Invalid amount"]
    assert by_line[6] == ["Missing description"]


def test_csv_requires_headers():
    try:
        parse_csv_text("foo,bar\n1,2\n")
        raised = False
    except CsvRejected as exc:
        raised = True
        assert "date, description, amount, and category" in exc.message
    assert raised


def test_display_filename_strips_directories():
    name = display_filename("../../secrets.csv")
    assert "/" not in name and ".." not in name
    assert name.endswith(".csv")
    try:
        display_filename("notes.txt")
        raised = False
    except CsvRejected:
        raised = True
    assert raised


def test_import_skips_invalid_rows_and_duplicates(client, app):
    register(client)
    login(client)
    first = _upload(client, SAMPLE)
    assert b"3 invalid rows" in first.data
    assert b"Row 4:" in first.data
    assert b"Invalid date" in first.data
    assert b"Row 5:" in first.data
    assert b"Invalid amount" in first.data
    assert b"Row 6:" in first.data
    assert b"Missing description" in first.data

    path = _preview_path(client, SAMPLE)
    client.post(path, follow_redirects=True)

    from app.db import get_db

    with app.app_context():
        rows = get_db().execute("SELECT description FROM expenses ORDER BY description").fetchall()
    assert [row["description"] for row in rows] == ["Restaurant", "Uber"]

    duplicate = _upload(client, "date,description,amount,category\n2026-08-01,Uber,320,Transport\n")
    assert b"possible duplicate" in duplicate.data.lower() or b"Possible duplicate" in duplicate.data
    preview = _location_from_upload(client, "date,description,amount,category\n2026-08-01,Uber,320,Transport\n")
    client.post(preview, follow_redirects=True)
    with app.app_context():
        count = get_db().execute("SELECT COUNT(*) AS count FROM expenses").fetchone()["count"]
    assert count == 2


def test_invalid_payment_method_is_not_imported(client, app):
    register(client)
    login(client)
    text = (
        "date,description,amount,category,payment_method\n"
        "2026-08-01,Cashback,100,Food,Bitcoin\n"
        "2026-08-02,Tea,50,Food,upi\n"
    )
    rows = parse_csv_text(text)
    assert rows[0]["errors"] == ["Invalid payment method"]
    assert rows[0]["payment_method"] == "Bitcoin"
    assert "Invalid payment method" in revalidate_stored_row(rows[0])["errors"]
    assert rows[1]["errors"] == []
    assert rows[1]["payment_method"] == "UPI"

    preview = _upload(client, text)
    assert b"Invalid payment method" in preview.data
    path = _location_from_upload(client, text)
    confirmed = client.post(path, follow_redirects=True)
    assert b"Imported 1 transaction." in confirmed.data
    from app.db import get_db

    with app.app_context():
        stored = get_db().execute(
            "SELECT description, payment_method FROM expenses"
        ).fetchall()
    assert [(row["description"], row["payment_method"]) for row in stored] == [("Tea", "UPI")]


def test_duplicate_rows_in_one_file_are_marked():
    rows = parse_csv_text(
        "date,description,amount,category\n"
        "2026-08-01,Uber,320,Transport\n"
        "2026-08-01,UBER,320,Transport\n"
    )
    apply_duplicates(rows, set())
    assert rows[0]["duplicate"] is False
    assert rows[1]["duplicate"] is True


def test_confirming_an_import_twice_does_not_insert_twice(client, app):
    register(client)
    login(client)
    path = _location_from_upload(
        client,
        "date,description,amount,category\n2026-08-01,Tea,40,Food\n",
    )
    first = client.post(path, follow_redirects=True)
    assert b"Imported 1 transaction." in first.data
    second = client.post(path, follow_redirects=True)
    assert b"expired" in second.data.lower()
    from app.db import get_db

    with app.app_context():
        count = get_db().execute("SELECT COUNT(*) AS count FROM expenses").fetchone()["count"]
    assert count == 1


def test_export_neutralizes_spreadsheet_formulas(client, app):
    register(client)
    login(client)
    client.post(
        "/expenses/new",
        data=expense_form(app, description="=2+2", amount="10", date="2026-08-01", notes=""),
    )
    exported = client.get("/export-csv").get_data(as_text=True)
    assert csv_safe("=2+2") == "'=2+2"
    assert "'=2+2" in exported
    assert "\n=2+2," not in exported


def test_non_csv_upload_is_rejected(client):
    register(client)
    login(client)
    response = client.post(
        "/import",
        data={"file": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Upload a .csv file." in response.data


def _upload(client, text):
    response = client.post(
        "/import",
        data={"file": (io.BytesIO(text.encode("utf-8")), "expenses.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    return response


def _location_from_upload(client, text):
    response = client.post(
        "/import",
        data={"file": (io.BytesIO(text.encode("utf-8")), "expenses.csv")},
        content_type="multipart/form-data",
    )
    return urlparse(response.headers["Location"]).path


def _preview_path(client, text):
    return _location_from_upload(client, text)
