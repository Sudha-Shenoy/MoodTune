"""Models package for MoodTune."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user_model import User

__all__ = ["db", "User"]
