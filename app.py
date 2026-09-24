"""Flask application entry point and factory for MoodTune."""
import os
from flask import Flask
from config.config import Config
from models import db
from routes.main_routes import main_bp
from routes.auth_routes import auth_bp
from routes.recommendation_routes import recommendation_bp
from routes.playlist_routes import playlist_bp


def create_app(config_class=Config):
    """Application factory for MoodTune."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(playlist_bp)

    # CLI command for table creation
    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables."""
        try:
            db.create_all()
            print("Database tables created successfully.")
        except Exception as exc:
            print(f"Error initializing database: {exc}")
            print("Please verify MySQL80 is running and DB credentials in .env are configured.")

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=app.config.get("DEBUG", True))
