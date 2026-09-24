import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def default_database_path():
    """Prefer the database that already lives at the repository root."""
    configured = os.environ.get("DATABASE_PATH")
    if configured:
        return Path(configured)
    root_db = ROOT_DIR / "database.db"
    nested_db = ROOT_DIR / "expense-tracker" / "database.db"
    if root_db.exists():
        return root_db
    if nested_db.exists():
        return nested_db
    return root_db


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE = None
    CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 1_048_576
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE") == "1"
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    CSRF_ENABLED = False
    DATABASE = None
