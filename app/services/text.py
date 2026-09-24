import re


def normalize_description(value):
    """Lowercase a description and drop punctuation so 'NETFLIX!' matches 'Netflix'."""
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def transaction_fingerprint(expense_date, description, amount):
    return f"{expense_date}|{normalize_description(description)}|{float(amount):.2f}"


def like_contains(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
