from datetime import date

from flask import Blueprint, render_template, request, session

from app.security import login_required
from app.services.dashboard import build_dashboard

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    chart_range = request.args.get("range", "month")
    if chart_range not in {"month", "six_months", "all"}:
        chart_range = "month"
    payload = build_dashboard(session["user_id"], date.today(), chart_range)
    return render_template("dashboard.html", **payload)
