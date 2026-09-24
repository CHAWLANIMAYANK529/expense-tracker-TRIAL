from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.constants import PAYMENT_METHODS, PER_PAGE
from app.db import DatabaseError
from app.formatters import plain_amount
from app.security import login_required
from app.services.expenses import (
    allowed_category_ids,
    create_expense,
    delete_expense,
    get_expense,
    list_categories,
    query_expenses,
    update_expense,
)
from app.services.validation import parse_amount, parse_date, validate_expense_form

bp = Blueprint("expenses", __name__)


@bp.route("/transactions")
@login_required
def index():
    filters, warnings = _filters_from_request()
    for warning in warnings:
        flash(warning, "warning")
    page = request.args.get("page", 1, type=int) or 1
    expenses, total, page, pages = query_expenses(session["user_id"], filters, page, PER_PAGE)
    return render_template(
        "transactions.html",
        expenses=expenses,
        total=total,
        page=page,
        pages=pages,
        filters=filters,
        categories=list_categories(session["user_id"]),
        payment_methods=PAYMENT_METHODS,
        sort_urls={
            "date_desc": _list_url(filters, sort="date_desc"),
            "date_asc": _list_url(filters, sort="date_asc"),
            "amount_desc": _list_url(filters, sort="amount_desc"),
            "amount_asc": _list_url(filters, sort="amount_asc"),
        },
        prev_url=_list_url(filters, page=page - 1) if page > 1 else None,
        next_url=_list_url(filters, page=page + 1) if page < pages else None,
    )


@bp.route("/expenses/new", methods=["GET", "POST"])
@bp.route("/add-expense", methods=["GET", "POST"])
@login_required
def new_expense():
    return _expense_form()


@bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@bp.route("/edit-expense/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    expense = get_expense(session["user_id"], expense_id)
    if expense is None:
        return render_template("errors/404.html"), 404
    return _expense_form(expense)


@bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@bp.route("/delete-expense/<int:expense_id>", methods=["GET", "POST"])
@login_required
def delete(expense_id):
    if request.method == "GET":
        expense = get_expense(session["user_id"], expense_id)
        if expense is None:
            return render_template("errors/404.html"), 404
        return render_template("confirm_delete.html", expense=expense)
    try:
        deleted = delete_expense(session["user_id"], expense_id)
    except DatabaseError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("expenses.index"))
    if not deleted:
        return render_template("errors/404.html"), 404
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.index"))


def _expense_form(expense=None):
    user_id = session["user_id"]
    categories = list_categories(user_id)
    errors = []
    if expense is None:
        form = {
            "description": "",
            "amount": "",
            "date": date.today().isoformat(),
            "category_id": "",
            "new_category": "",
            "payment_method": "UPI",
            "notes": "",
        }
    else:
        form = {
            "description": expense["description"],
            "amount": plain_amount(expense["amount"]),
            "date": expense["date"],
            "category_id": expense["category_id"],
            "new_category": "",
            "payment_method": expense["payment_method"],
            "notes": expense["notes"],
        }

    if request.method == "POST":
        form = {
            "description": request.form.get("description", ""),
            "amount": request.form.get("amount", ""),
            "date": request.form.get("date", ""),
            "category_id": request.form.get("category_id", ""),
            "new_category": request.form.get("new_category", ""),
            "payment_method": request.form.get("payment_method", ""),
            "notes": request.form.get("notes", ""),
        }
        cleaned, errors = validate_expense_form(form, allowed_category_ids(user_id))
        if not errors:
            try:
                if expense is None:
                    create_expense(user_id, cleaned)
                    flash("Expense added.", "success")
                else:
                    updated = update_expense(user_id, expense["id"], cleaned)
                    if not updated:
                        return render_template("errors/404.html"), 404
                    flash("Expense updated.", "success")
            except DatabaseError as exc:
                flash(str(exc), "danger")
            else:
                return redirect(url_for("expenses.index"))
    return render_template(
        "expense_form.html",
        mode="edit" if expense else "add",
        expense=expense,
        form=form,
        errors=errors,
        categories=categories,
        payment_methods=PAYMENT_METHODS,
    )


def _filters_from_request():
    warnings = []
    search = (request.args.get("search") or "").strip()
    sort = request.args.get("sort") or "date_desc"
    if sort not in {"date_desc", "date_asc", "amount_desc", "amount_asc"}:
        sort = "date_desc"

    category_id = None
    raw_category = (request.args.get("category") or "").strip()
    if raw_category:
        try:
            category_id = int(raw_category)
        except ValueError:
            warnings.append("That category filter was ignored.")

    date_from = _optional_date("date_from", warnings)
    date_to = _optional_date("date_to", warnings)
    if date_from and date_to and date_from > date_to:
        warnings.append("The start date must be on or before the end date.")
        date_from = None
        date_to = None

    amount_min = _optional_amount("amount_min", warnings)
    amount_max = _optional_amount("amount_max", warnings)
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        warnings.append("The minimum amount must be less than or equal to the maximum.")
        amount_min = None
        amount_max = None

    payment_method = (request.args.get("payment_method") or "").strip()
    if payment_method and payment_method not in PAYMENT_METHODS:
        warnings.append("That payment method filter was ignored.")
        payment_method = ""

    filters = {
        "search": search,
        "category_id": category_id,
        "date_from": date_from,
        "date_to": date_to,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "payment_method": payment_method,
        "sort": sort,
    }
    return filters, warnings


def _optional_date(name, warnings):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return parse_date(raw, error="Enter a valid date.").isoformat()
    except ValueError:
        warnings.append(f"The {name.replace('_', ' ')} filter was ignored.")
        return None


def _optional_amount(name, warnings):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return parse_amount(raw, invalid_message="Enter a valid amount.", allow_zero=True)
    except ValueError:
        warnings.append(f"The {name.replace('_', ' ')} filter was ignored.")
        return None


def _list_url(filters, **updates):
    """Build a transactions link from filters that were actually applied."""
    params = {
        "search": filters.get("search") or "",
        "category": filters.get("category_id") or "",
        "date_from": filters.get("date_from") or "",
        "date_to": filters.get("date_to") or "",
        "amount_min": "" if filters.get("amount_min") is None else filters["amount_min"],
        "amount_max": "" if filters.get("amount_max") is None else filters["amount_max"],
        "payment_method": filters.get("payment_method") or "",
        "sort": filters.get("sort") or "date_desc",
    }
    params.update(updates)
    cleaned = {}
    for key, value in params.items():
        if value in ("", None):
            continue
        if key == "page" and int(value) <= 1:
            continue
        if key == "sort" and value == "date_desc":
            continue
        cleaned[key] = value
    return url_for("expenses.index", **cleaned)
