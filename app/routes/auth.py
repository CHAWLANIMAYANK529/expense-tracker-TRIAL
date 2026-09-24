import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db
from app.services.validation import validate_login, validate_registration

bp = Blueprint("auth", __name__)
_DUMMY_PASSWORD_HASH = generate_password_hash("dummy-password-not-used")


@bp.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    errors = []
    form = {"name": "", "email": ""}
    if request.method == "POST":
        form, errors = validate_registration(request.form)
        if not errors:
            connection = get_db()
            try:
                taken = connection.execute(
                    "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
                    (form["email"],),
                ).fetchone()
                if taken:
                    errors.append("Email already registered.")
                else:
                    connection.execute(
                        "INSERT INTO users (name, email, password, budget) VALUES (?, ?, ?, NULL)",
                        (form["name"], form["email"], generate_password_hash(form["password"])),
                    )
                    connection.commit()
                    flash("Registration successful. Please log in.", "success")
                    return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                connection.rollback()
                errors.append("Email already registered.")
    return render_template("register.html", errors=errors, form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    errors = []
    email = ""
    if request.method == "POST":
        form, errors = validate_login(request.form)
        email = form["email"]
        if not errors:
            matches = get_db().execute(
                "SELECT id, name, email, password FROM users WHERE email = ? COLLATE NOCASE",
                (form["email"],),
            ).fetchall()
            user = next(
                (row for row in matches if check_password_hash(row["password"], form["password"])),
                None,
            )
            if user is None:
                if not matches:
                    check_password_hash(_DUMMY_PASSWORD_HASH, form["password"])
                errors.append("Invalid email or password.")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(url_for("dashboard.index"))
    return render_template("login.html", errors=errors, email=email)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
