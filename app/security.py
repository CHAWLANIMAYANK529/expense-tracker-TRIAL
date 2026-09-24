import hmac
import secrets
from functools import wraps

from flask import current_app, redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def ensure_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


def csrf_protect():
    if not current_app.config.get("CSRF_ENABLED", True):
        return None
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    expected = session.get("_csrf_token", "")
    sent = request.form.get("csrf_token", "")
    if not expected or not sent or not _tokens_match(expected, sent):
        return ("Your form expired. Go back, refresh the page, and try again.", 400)
    return None


def _tokens_match(expected, sent):
    if not isinstance(expected, str) or not isinstance(sent, str):
        return False
    try:
        return hmac.compare_digest(expected, sent)
    except (TypeError, ValueError):
        return False

