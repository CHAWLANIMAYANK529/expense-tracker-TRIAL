from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.db import DatabaseError
from app.security import login_required
from app.services.budget import budget_snapshot
from app.services.dashboard import current_budget_amount, save_budget
from app.services.expenses import load_expenses
from app.services.periods import start_of_month
from app.services.validation import validate_budget_amount

bp = Blueprint("budget", __name__)


@bp.route("/budget")
@login_required
def index():
    today = date.today()
    return render_template("budget.html", budget=_snapshot(session["user_id"], today), today=today)


@bp.route("/budget", methods=["POST"])
@bp.route("/set-budget", methods=["POST"])
@login_required
def update():
    amount, error = validate_budget_amount(request.form.get("budget"))
    if error:
        flash(error, "danger")
        return redirect(url_for("budget.index"))
    try:
        save_budget(session["user_id"], amount, date.today())
    except DatabaseError:
        flash("The budget could not be saved. Please try again.", "danger")
        return redirect(url_for("budget.index"))
    flash("Monthly budget saved.", "success")
    return redirect(url_for("budget.index"))


def _snapshot(user_id, today):
    month_start = start_of_month(today)
    expenses = load_expenses(user_id, month_start, today)
    spent = sum(float(item["amount"]) for item in expenses)
    return budget_snapshot(spent, current_budget_amount(user_id, today))
