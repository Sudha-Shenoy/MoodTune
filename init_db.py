"""Standalone database table initialization script for MoodTune."""
import sys
from app import create_app
from models import db


def init_database():
    """Create database tables without dropping existing data."""
    app = create_app()
    try:
        with app.app_context():
            db.create_all()
            print("Successfully initialized MoodTune database tables (users).")
    except Exception as exc:
        print(f"Error initializing database: {exc}", file=sys.stderr)
        print("Please verify MySQL80 is running and database credentials in .env are correct.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    init_database()
