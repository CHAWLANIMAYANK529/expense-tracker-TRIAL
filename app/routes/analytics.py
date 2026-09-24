from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.security import login_required
from app.services.analytics import chart_colors, summarize
from app.services.anomalies import EXPLANATION as UNUSUAL_EXPLANATION
from app.services.anomalies import detect_unusual
from app.services.expenses import load_expenses
from app.services.periods import PERIOD_OPTIONS, resolve_period
from app.services.recurring import EXPLANATION as RECURRING_EXPLANATION
from app.services.recurring import detect_recurring

bp = Blueprint("analytics", __name__)


@bp.route("/analytics")
@login_required
def index():
    today = date.today()
    preset = request.args.get("period", "this_month")
    start_text = request.args.get("start", "")
    end_text = request.args.get("end", "")
    start, end, error = resolve_period(preset, today, start_text, end_text)
    if error:
        flash(error, "warning")
        start, end, _ignored = resolve_period("this_month", today)
        preset = "this_month"

    user_id = session["user_id"]
    ranged = load_expenses(user_id, start, end)
    summary = summarize(ranged, start, end)
    all_expenses = load_expenses(user_id)
    summary["category_colors"] = chart_colors(len(summary["categories"]))
    return render_template(
        "analytics.html",
        summary=summary,
        start=start,
        end=end,
        preset=preset,
        start_text=start.isoformat(),
        end_text=end.isoformat(),
        period_options=PERIOD_OPTIONS,
        recurring=detect_recurring(all_expenses),
        unusual=detect_unusual(all_expenses, today),
        recurring_explanation=RECURRING_EXPLANATION,
        unusual_explanation=UNUSUAL_EXPLANATION,
    )
