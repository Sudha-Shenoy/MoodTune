"""Unit and route tests for MoodTune core application."""
import pytest
from app import create_app
from config.config import TestingConfig
from models import db


@pytest.fixture
def app():
    """Create and configure a Flask application instance for testing."""
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the application."""
    return app.test_client()


def test_index_route_status_code(client):
    """Test that GET / returns HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_index_content(client):
    """Test that GET / displays expected brand, headline, and core sections."""
    response = client.get("/")
    assert response.status_code == 200
    html_content = response.data.decode("utf-8")

    # Core branding and identity
    assert "MoodTune" in html_content
    assert "Music that matches" in html_content
    assert "your mood." in html_content

    # Music discovery sections
    assert "How are you feeling?" in html_content
    assert "Music in your language." in html_content
    assert "Your music journey, simplified." in html_content
    assert "Powered by AI" in html_content
    assert "Start Listening" in html_content
