import math
import re
from datetime import datetime

from app.constants import (
    MAX_AMOUNT,
    MAX_CATEGORY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NOTES_LENGTH,
    MIN_PASSWORD_LENGTH,
    PAYMENT_METHODS,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &/.'-]{0,39}$")
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_amount(value, blank_message="Invalid amount", invalid_message="Invalid amount", allow_zero=False):
    if value is None or str(value).strip() == "":
        raise ValueError(blank_message)
    text = str(value).strip().replace("₹", "").replace(",", "").replace(" ", "")
    try:
        amount = float(text)
    except ValueError:
        raise ValueError(invalid_message) from None
    if (
        not math.isfinite(amount)
        or amount < 0
        or (amount == 0 and not allow_zero)
        or amount > MAX_AMOUNT
    ):
        raise ValueError(invalid_message)
    return round(amount, 2)


def parse_date(value, error="Invalid date"):
    if value is None or str(value).strip() == "":
        raise ValueError(error)
    text = str(value).strip()
    parsed = None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None or parsed.year < 2000 or parsed.year > 2100:
        raise ValueError(error)
    return parsed


def validate_registration(form):
    errors = []
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    if not name:
        errors.append("Name is required.")
    elif len(name) > 80:
        errors.append("Name must be 80 characters or fewer.")
    if not email or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    elif len(password) > 128:
        errors.append("Password must be 128 characters or fewer.")
    return {"name": name, "email": email, "password": password}, errors


def validate_login(form):
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    if not email or not password:
        return {"email": email, "password": password}, ["Enter your email and password."]
    return {"email": email, "password": password}, []


def validate_category_name(name):
    cleaned = " ".join((name or "").split())
    if not cleaned:
        return None, "Enter a category name."
    if len(cleaned) > MAX_CATEGORY_LENGTH or not CATEGORY_RE.match(cleaned):
        return None, "Use 1–40 letters, numbers, spaces, or simple punctuation for the category."
    return cleaned, None


def validate_expense_form(form, allowed_category_ids):
    errors = []
    description = (form.get("description") or "").strip()
    if not description:
        errors.append("Description is required.")
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer.")

    try:
        amount = parse_amount(
            form.get("amount"),
            blank_message="Amount is required.",
            invalid_message="Enter an amount greater than zero.",
        )
    except ValueError as exc:
        errors.append(str(exc))
        amount = None

    try:
        expense_date = parse_date(form.get("date"), error="Enter a valid date.")
    except ValueError as exc:
        errors.append(str(exc))
        expense_date = None

    notes = (form.get("notes") or "").strip()
    if len(notes) > MAX_NOTES_LENGTH:
        errors.append(f"Notes must be {MAX_NOTES_LENGTH} characters or fewer.")

    payment_method = (form.get("payment_method") or "").strip()
    if payment_method not in PAYMENT_METHODS:
        errors.append("Choose a payment method.")
        payment_method = None

    new_category, category_error = validate_category_name(form.get("new_category") or "")
    raw_new = (form.get("new_category") or "").strip()
    category_id = None
    if raw_new:
        if category_error:
            errors.append(category_error)
        else:
            new_category = new_category
    else:
        new_category = None
        raw_id = (form.get("category_id") or "").strip()
        try:
            category_id = int(raw_id)
        except ValueError:
            errors.append("Choose a category.")
        else:
            if category_id not in allowed_category_ids:
                errors.append("Choose a category from the list.")

    return {
        "description": description,
        "amount": amount,
        "date": expense_date,
        "notes": notes,
        "payment_method": payment_method,
        "category_id": category_id,
        "new_category": new_category,
    }, errors


def validate_budget_amount(value):
    try:
        amount = parse_amount(
            value,
            blank_message="Enter a monthly budget.",
            invalid_message="Enter a budget greater than zero.",
        )
    except ValueError as exc:
        return None, str(exc)
    return amount, None
