import os
import secrets
from pathlib import Path

from flask import Flask, render_template, request, session

from app.db import close_db, init_db
from app.formatters import format_inr, plain_amount, short_date
from app.security import csrf_protect, ensure_csrf_token
from config import ROOT_DIR, Config, default_database_path


def create_app(config_class=Config, database=None):
    app = Flask(
        __name__,
        instance_path=str(ROOT_DIR / "instance"),
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)
    if database:
        app.config["DATABASE"] = str(database)
    elif not app.config.get("DATABASE"):
        app.config["DATABASE"] = str(default_database_path())

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)
    _ensure_secret_key(app)
    if app.config.get("TESTING"):
        app.config["PROPAGATE_EXCEPTIONS"] = True

    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    @app.context_processor
    def inject_globals():
        current_user = None
        if session.get("user_id"):
            current_user = {
                "id": session["user_id"],
                "name": session.get("user_name") or "Account",
            }
        return {
            "current_user": current_user,
            "csrf_token": ensure_csrf_token(),
        }

    @app.template_filter("inr")
    def inr_filter(value):
        return format_inr(value)

    @app.template_filter("plain_amount")
    def plain_amount_filter(value):
        return plain_amount(value)

    @app.template_filter("short_date")
    def short_date_filter(value):
        return short_date(value)

    @app.before_request
    def check_csrf():
        failure = csrf_protect()
        if failure is None:
            return None
        message, status = failure
        return render_template("errors/400.html", message=message), status

    @app.after_request
    def security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if session.get("user_id"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template(
            "errors/400.html",
            message="That file is too large. CSV imports are limited to 1 MB.",
        ), 413

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return render_template(
            "errors/400.html",
            message="That action is not available from this address.",
        ), 405

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error("Unhandled error", exc_info=error)
        return render_template("errors/500.html"), 500

    from app.routes.analytics import bp as analytics_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.budget import bp as budget_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.expenses import bp as expenses_bp
    from app.routes.imports import bp as imports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(imports_bp)
    return app


def _ensure_secret_key(app):
    if app.config.get("SECRET_KEY"):
        return
    secret_path = Path(app.instance_path) / "secret_key"
    if secret_path.exists():
        app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8").strip()
        return
    key = secrets.token_hex(32)
    secret_path.write_text(key, encoding="utf-8")
    app.config["SECRET_KEY"] = key
