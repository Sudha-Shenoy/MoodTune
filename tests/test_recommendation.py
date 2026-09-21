"""Integration tests for MoodTune Module 05: Recommendation Routes and Session State."""
from unittest.mock import patch
import pytest
from flask import session
from app import create_app
from config.config import TestingConfig
from models import db, User


@pytest.fixture
def app():
    """Create and configure a Flask test application with isolated in-memory database."""
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


def create_and_login_user(client, app, name="Music Fan", email="musicfan@example.com", password="Password@123"):
    """Helper to create and log in an authenticated user."""
    with app.app_context():
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={"email": email, "password": password}
    )


# 1. Unauthenticated JSON request returns 401
def test_generate_recommendation_unauthenticated_json(client):
    """Verify unauthenticated POST /generate-recommendation returns 401."""
    response = client.post(
        "/generate-recommendation",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data
    assert "Authentication required" in data["error"]


# 2. Unauthenticated form request redirects to /login
def test_generate_recommendation_unauthenticated_form(client):
    """Verify unauthenticated browser submission redirects to /login."""
    response = client.post("/generate-recommendation")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# 3. Missing selected mood returns 400
def test_generate_recommendation_missing_mood(client, app):
    """Verify request fails with 400 when mood is not in session."""
    create_and_login_user(client, app)

    with client:
        # Set only language in session
        client.post("/preferences", json={"language": "Kannada"})
        response = client.post(
            "/generate-recommendation",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Please select a mood and language first." in data["error"]


# 4. Missing selected language returns 400
def test_generate_recommendation_missing_language(client, app):
    """Verify request fails with 400 when language is not in session."""
    create_and_login_user(client, app)

    with client:
        # Set only mood in session
        client.post("/preferences", json={"mood": "Happy"})
        response = client.post(
            "/generate-recommendation",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Please select a mood and language first." in data["error"]


# 5. Authenticated user with preferences calls AI service and returns 200 JSON
@patch("routes.recommendation_routes.generate_music_recommendation")
def test_generate_recommendation_authenticated_success(mock_generate, client, app):
    """Verify valid authenticated call successfully returns AI recommendation."""
    mock_generate.return_value = {
        "mood": "Happy",
        "language": "Kannada",
        "music_style": ["upbeat", "positive", "energetic", "celebratory"],
        "search_queries": [
            "Kannada happy songs",
            "Kannada dance hits",
            "Kannada feel good melodies"
        ],
        "description": "Joyful and energetic Kannada celebration tunes."
    }

    create_and_login_user(client, app)

    with client:
        # Set both preferences
        client.post("/preferences", json={"mood": "Happy", "language": "Kannada"})

        response = client.post(
            "/generate-recommendation",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["recommendation"]["mood"] == "Happy"
        assert data["recommendation"]["language"] == "Kannada"
        assert len(data["recommendation"]["music_style"]) == 4

        # Verify session storage
        assert session.get("ai_recommendation") is not None
        assert session["ai_recommendation"]["description"] == "Joyful and energetic Kannada celebration tunes."


# 6. AI service failure returns 500 with user-friendly message
@patch("routes.recommendation_routes.generate_music_recommendation")
def test_generate_recommendation_service_error(mock_generate, client, app):
    """Verify unexpected AI failure returns friendly 500 without exposing stack traces."""
    from services.ai_service import AIServiceError
    mock_generate.side_effect = AIServiceError("Upstream network failed")

    create_and_login_user(client, app)

    with client:
        client.post("/preferences", json={"mood": "Chill", "language": "Hindi"})
        response = client.post(
            "/generate-recommendation",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
        assert "Sorry, MoodTune couldn't create your recommendation" in data["error"]


# 7. AI configuration error returns 503 with friendly message
@patch("routes.recommendation_routes.generate_music_recommendation")
def test_generate_recommendation_config_error(mock_generate, client, app):
    """Verify missing API key returns friendly 503."""
    from services.ai_service import AIConfigurationError
    mock_generate.side_effect = AIConfigurationError()

    create_and_login_user(client, app)

    with client:
        client.post("/preferences", json={"mood": "Chill", "language": "Hindi"})
        response = client.post(
            "/generate-recommendation",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 503
        data = response.get_json()
        assert "AI recommendation engine is not configured" in data["error"]


# 8. Homepage renders existing session recommendation without calling AI
@patch("routes.recommendation_routes.generate_music_recommendation")
def test_homepage_renders_session_recommendation(mock_generate, client, app):
    """Verify GET / displays recommendation stored in session without invoking the AI engine."""
    create_and_login_user(client, app)

    cached_rec = {
        "mood": "Romantic",
        "language": "Telugu",
        "music_style": ["melodic", "acoustic", "sweet", "gentle"],
        "search_queries": ["Telugu romantic hits", "Telugu love melody", "Telugu acoustic"],
        "description": "Sweet acoustic Telugu love melodies."
    }

    with client:
        with client.session_transaction() as sess:
            sess["ai_recommendation"] = cached_rec

        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify recommendation card content is in the HTML
        assert "Your MoodTune Vibe" in html
        assert "Romantic • Telugu" in html
        assert "Sweet acoustic Telugu love melodies." in html
        assert "Telugu romantic hits" in html

        # Crucial: verify AI service was NOT called during page load
        mock_generate.assert_not_called()
