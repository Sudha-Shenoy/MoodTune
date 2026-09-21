"""Routes package for MoodTune."""
from .main_routes import main_bp
from .auth_routes import auth_bp, login_required

__all__ = ["main_bp", "auth_bp", "login_required"]
