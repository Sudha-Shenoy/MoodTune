"""Flask application entry point and factory for MoodTune."""
import os
from flask import Flask
from config.config import Config
from routes.main_routes import main_bp


def create_app(config_class=Config):
    """Application factory for MoodTune."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register blueprints
    app.register_blueprint(main_bp)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=app.config.get("DEBUG", True))
