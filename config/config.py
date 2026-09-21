"""Application configuration module."""
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Base directory of the MoodTune project
BASE_DIR = Path(__file__).resolve().parent.parent

# Explicitly load .env file from project root if present (with override=True)
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)


class Config:
    """Base application configuration class."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_moodtune_fallback")
    DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    TESTING = False

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in ("1", "true", "yes")

    # Database configuration
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "moodtune")
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

    # Use SQLite by default for local development so the project runs without a
    # configured MySQL service. If a real database URL or MySQL credentials are
    # supplied in the environment, keep using that instead.
    database_url = os.environ.get("DATABASE_URL")
    placeholder_passwords = {
        "",
        "your_mysql_password_here",
        "your_actual_mysql_password_here",
        "changeme",
    }

    if database_url:
        SQLALCHEMY_DATABASE_URI = database_url
    elif DB_PASSWORD and DB_PASSWORD.lower() not in {value.lower() for value in placeholder_passwords}:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'moodtune.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Recommendation Engine configuration (Google Gemini & OpenAI-compatible)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("AI_API_KEY", None)
    AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("GEMINI_API_KEY", None)
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
    AI_MODEL = os.environ.get("AI_MODEL", "gemini-flash-lite-latest")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", None)

    # Future integration placeholders
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", None)


class TestingConfig(Config):
    """Testing configuration class with isolated in-memory database."""

    TESTING = True
    DEBUG = True
    SECRET_KEY = "test_secret_key_moodtune"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
