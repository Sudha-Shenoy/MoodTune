"""Unit and integration tests for MoodTune Module 04: Authentication-Gated Preferences."""
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


def create_and_login_user(client, app, name="Test Explorer", email="explorer@example.com", password="Password@123"):
    """Helper function to create a test user and log them in."""
    with app.app_context():
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={"email": email, "password": password}
    )


# 1. GET /preferences when logged out returns authenticated=False
def test_preferences_get_logged_out(client):
    """Verify GET /preferences returns 200 with authenticated=False when unauthenticated."""
    response = client.get("/preferences")
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is False
    assert data["selected_mood"] is None
    assert data["selected_language"] is None


# 2. POST /preferences when logged out (JSON request) returns 401 Unauthorized
def test_preferences_post_logged_out_json(client):
    """Verify POST /preferences returns 401 JSON error when unauthenticated."""
    response = client.post(
        "/preferences",
        json={"mood": "Happy", "language": "Kannada"}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data
    assert "Authentication required" in data["error"]
    assert "login_url" in data


# 3. POST /preferences when logged out (standard form request) redirects to /login
def test_preferences_post_logged_out_form(client):
    """Verify POST /preferences via standard form redirects unauthenticated users to /login."""
    response = client.post(
        "/preferences",
        data={"mood": "Happy", "language": "Kannada"}
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# 4. POST /preferences when logged in with valid mood updates session
def test_preferences_post_logged_in_valid_mood(client, app):
    """Verify authenticated user can set a valid mood and persist it in session."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"mood": "Chill"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["selected_mood"] == "Chill"
        assert session.get("selected_mood") == "Chill"


# 5. POST /preferences when logged in with valid language updates session
def test_preferences_post_logged_in_valid_language(client, app):
    """Verify authenticated user can set a valid language and persist it in session."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"language": "Kannada"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["selected_language"] == "Kannada"
        assert session.get("selected_language") == "Kannada"


# 6. POST /preferences when logged in with both mood and language
def test_preferences_post_logged_in_both(client, app):
    """Verify authenticated user can set both mood and language in a single request."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"mood": "Energetic", "language": "Hindi"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["selected_mood"] == "Energetic"
        assert data["selected_language"] == "Hindi"
        assert session.get("selected_mood") == "Energetic"
        assert session.get("selected_language") == "Hindi"


# 7. POST /preferences with invalid mood returns 400 Bad Request
def test_preferences_post_invalid_mood(client, app):
    """Verify invalid mood choice is rejected with 400."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"mood": "ExtremelyAngry"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid mood" in data["error"]


# 8. POST /preferences with invalid language returns 400 Bad Request
def test_preferences_post_invalid_language(client, app):
    """Verify invalid language choice is rejected with 400."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"language": "Klingon"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid language" in data["error"]


# 9. POST /preferences performs case-insensitive normalization to canonical form
def test_preferences_post_case_insensitivity(client, app):
    """Verify lowercase input values are normalized to canonical title-case."""
    create_and_login_user(client, app)

    with client:
        response = client.post(
            "/preferences",
            json={"mood": "party", "language": "malayalam"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["selected_mood"] == "Party"
        assert data["selected_language"] == "Malayalam"
        assert session.get("selected_mood") == "Party"
        assert session.get("selected_language") == "Malayalam"


# 10. GET / renders saved preferences for logged-in user
def test_homepage_renders_preferences_when_logged_in(client, app):
    """Verify GET / reflects active classes and summary display when preferences are in session."""
    create_and_login_user(client, app)

    with client:
        # Set preferences in session
        client.post(
            "/preferences",
            json={"mood": "Romantic", "language": "Telugu"}
        )

        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Check data attributes and summary values
        assert 'data-selected-mood="Romantic"' in html
        assert 'data-selected-language="Telugu"' in html
        assert "Romantic" in html
        assert "Telugu" in html


# 11. GET / shows lock indicator and no default active selection when logged out
def test_homepage_renders_lock_indicator_when_logged_out(client):
    """Verify GET / shows member lock badge when logged out and does not mark pills active by default."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Member lock badge should be present in DOM
    assert "Member Personalization" in html
    assert "member-lock-badge" in html

    # Auth modal structure should be present
    assert 'id="authModal"' in html
    assert "Your music journey starts here" in html
    assert 'id="findMusicBtn"' in html
