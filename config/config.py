"""Application configuration module."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the MoodTune project
BASE_DIR = Path(__file__).resolve().parent.parent

# Explicitly load .env file from project root if present
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Config:
    """Base application configuration class."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_moodtune_fallback")
    DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    TESTING = False

    # Future integration placeholders (populated via .env in future modules)
    AI_API_KEY = os.environ.get("AI_API_KEY", None)
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", None)


class TestingConfig(Config):
    """Testing configuration class."""

    TESTING = True
    DEBUG = True
    SECRET_KEY = "test_secret_key_moodtune"
