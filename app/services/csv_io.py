import csv
import io

from werkzeug.utils import secure_filename

from app.constants import MAX_CSV_ROWS, MAX_NOTES_LENGTH, PAYMENT_METHODS
from app.services.text import transaction_fingerprint
from app.services.validation import parse_amount, parse_date, validate_category_name


class CsvRejected(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def display_filename(filename):
    cleaned = secure_filename(filename or "")
    if not cleaned.lower().endswith(".csv"):
        raise CsvRejected("Upload a .csv file.")
    return cleaned


def parse_csv_text(text):
    """Validate a CSV in memory. Nothing is written to disk.

    Returns a list of row dicts. Raises CsvRejected when the file itself is unusable.
    Individual bad rows are returned with an errors list so the user can review them.
    """
    if text is None:
        raise CsvRejected("The CSV file is empty.")
    if "\x00" in text:
        raise CsvRejected("This file is not a valid CSV.")
    sample = text.lstrip("\ufeff")
    if not sample.strip():
        raise CsvRejected("The CSV file is empty.")

    reader = csv.DictReader(io.StringIO(sample))
    if not reader.fieldnames:
        raise CsvRejected(
            "CSV must include a header row with date, description, amount, and category."
        )
    header_map = {}
    for field in reader.fieldnames:
        if field is None:
            continue
        header_map[_normalize_header(field)] = field
    if "description" not in header_map and "title" in header_map:
        header_map["description"] = header_map["title"]
    missing = [name for name in ("date", "description", "amount", "category") if name not in header_map]
    if missing:
        raise CsvRejected(
            "CSV must include date, description, amount, and category columns."
        )

    rows = []
    for line_number, raw in enumerate(reader, start=2):
        if _row_is_blank(raw):
            continue
        if len(rows) >= MAX_CSV_ROWS:
            raise CsvRejected(f"CSV imports are limited to {MAX_CSV_ROWS} transactions.")
        rows.append(_validate_raw_row(line_number, raw, header_map))
    if not rows:
        raise CsvRejected("The CSV file has no transactions.")
    return rows


def apply_duplicates(rows, existing_fingerprints):
    seen = set(existing_fingerprints)
    for row in rows:
        row["duplicate"] = False
        if row["errors"] or not row.get("fingerprint"):
            continue
        if row["fingerprint"] in seen:
            row["duplicate"] = True
        else:
            seen.add(row["fingerprint"])
    return rows


def csv_safe(value):
    """Prefix spreadsheet formulas so Excel and Sheets treat the cell as text."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def summarize_rows(rows):
    invalid = [row for row in rows if row["errors"]]
    duplicates = [row for row in rows if row["duplicate"] and not row["errors"]]
    ready = [row for row in rows if not row["errors"] and not row["duplicate"]]
    return {
        "invalid": invalid,
        "duplicates": duplicates,
        "ready": ready,
        "invalid_count": len(invalid),
        "duplicate_count": len(duplicates),
        "ready_count": len(ready),
    }


def revalidate_stored_row(stored):
    """Run the same checks again at confirm time. Do not trust a stored flag alone."""
    return _build_row(
        line_number=stored.get("line") or 0,
        date_text=stored.get("date") or "",
        description=stored.get("description") or "",
        amount_text="" if stored.get("amount") is None else stored.get("amount"),
        category=stored.get("category") or "",
        payment_method=stored.get("payment_method") or "",
        notes=stored.get("notes") or "",
        payment_was_provided=bool(stored.get("payment_was_provided")),
    )


def _validate_raw_row(line_number, raw, header_map):
    def cell(name):
        source = header_map.get(name)
        if not source:
            return ""
        value = raw.get(source)
        return "" if value is None else str(value).strip()

    payment_text = cell("payment_method")
    return _build_row(
        line_number=line_number,
        date_text=cell("date"),
        description=cell("description"),
        amount_text=cell("amount"),
        category=cell("category"),
        payment_method=payment_text,
        notes=cell("notes"),
        payment_was_provided="payment_method" in header_map and payment_text != "",
    )


def _build_row(line_number, date_text, description, amount_text, category, payment_method, notes, payment_was_provided):
    errors = []
    parsed_date = None
    try:
        parsed_date = parse_date(date_text, error="Invalid date")
    except ValueError as exc:
        errors.append(str(exc))

    description = (description or "").strip()
    if not description:
        errors.append("Missing description")
    elif len(description) > 120:
        errors.append("Description is too long")

    parsed_amount = None
    try:
        parsed_amount = parse_amount(amount_text)
    except ValueError as exc:
        errors.append(str(exc))

    category_name, category_error = validate_category_name(category)
    if not (category or "").strip():
        errors.append("Missing category")
    elif category_error:
        errors.append("Invalid category")

    if payment_was_provided:
        payment = _canonical_payment(payment_method)
        if payment is None:
            errors.append("Invalid payment method")
            payment = " ".join(str(payment_method or "").split())
    else:
        payment = "Other"

    notes = (notes or "").strip()
    if len(notes) > MAX_NOTES_LENGTH:
        errors.append("Notes are too long")

    fingerprint = None
    if parsed_date and description and parsed_amount is not None:
        fingerprint = transaction_fingerprint(parsed_date.isoformat(), description, parsed_amount)

    return {
        "line": line_number,
        "date": parsed_date.isoformat() if parsed_date else (date_text or ""),
        "description": description,
        "amount": parsed_amount,
        "category": category_name or (category or "").strip(),
        "payment_method": payment,
        "notes": notes,
        "payment_was_provided": payment_was_provided,
        "errors": errors,
        "duplicate": False,
        "fingerprint": fingerprint,
    }


def _canonical_payment(value):
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        return None
    for name in PAYMENT_METHODS:
        if cleaned.lower() == name.lower():
            return name
    return None


def _normalize_header(value):
    return " ".join(str(value).strip().lower().replace("_", " ").split()).replace(" ", "_")


def _row_is_blank(raw):
    return all(not str(value or "").strip() for value in raw.values())
