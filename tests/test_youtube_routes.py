"""Route tests for YouTube music discovery in MoodTune.

Tests endpoint authentication, session validation, quota error handling,
compact session persistence, and homepage rendering of discovered tracks.
"""
import pytest
from unittest.mock import patch
from app import create_app
from config.config import TestingConfig
from models import db
from services.youtube_service import (
    YouTubeQuotaError,
    YouTubeConfigurationError,
    YouTubeServiceError,
)


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


SAMPLE_AI_RECOMMENDATION = {
    "mood": "Happy",
    "language": "Kannada",
    "music_style": ["Upbeat", "Folk", "Celebration", "Melodic"],
    "search_queries": [
        "Kannada happy songs",
        "Kannada upbeat melodies",
        "Kannada feel good celebration tracks",
    ],
    "description": "A vibrant celebration of joyful rhythms and warm acoustic strings.",
}

SAMPLE_VIDEOS = [
    {
        "video_id": "vid_kannada_01",
        "title": "Belakina Kavithe",
        "channel_title": "Sandalwood Hits",
        "thumbnail": "https://i.ytimg.com/vi/vid_kannada_01/hqdefault.jpg",
        "youtube_url": "https://www.youtube.com/watch?v=vid_kannada_01",
    },
    {
        "video_id": "vid_kannada_02",
        "title": "Ra Ra Rakkamma",
        "channel_title": "Anand Audio",
        "thumbnail": "https://i.ytimg.com/vi/vid_kannada_02/hqdefault.jpg",
        "youtube_url": "https://www.youtube.com/watch?v=vid_kannada_02",
    },
]


def test_search_music_unauthenticated(client):
    """Test unauthenticated POST /search-music returns 401 with login URL."""
    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 401
    data = res.get_json()
    assert "error" in data
    assert "login" in data.get("login_url", "")


def test_discover_songs_alias_unauthenticated(client):
    """Test unauthenticated POST /discover-songs alias returns 401."""
    res = client.post("/discover-songs", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 401


def test_search_music_missing_recommendation(client):
    """Test authenticated request without prior AI recommendation returns 400."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Sudharshan"

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 400
    data = res.get_json()
    assert "generate an AI vibe first" in data.get("error", "")


def test_search_music_missing_queries_in_recommendation(client):
    """Test recommendation without search_queries returns 400."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["ai_recommendation"] = {"mood": "Happy", "language": "Kannada"}

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 400
    data = res.get_json()
    assert "search queries" in data.get("error", "").lower()


@patch("routes.recommendation_routes.search_music_for_recommendation")
def test_search_music_authenticated_success(mock_search, client):
    """Test successful music search returns 200 JSON and saves compact results in session."""
    mock_search.return_value = SAMPLE_VIDEOS

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Sudharshan"
        sess["ai_recommendation"] = SAMPLE_AI_RECOMMENDATION

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] == 2
    assert len(data["videos"]) == 2
    assert data["videos"][0]["video_id"] == "vid_kannada_01"

    # Verify session contains compact results
    with client.session_transaction() as sess:
        assert sess.get("youtube_results") == SAMPLE_VIDEOS


@patch("routes.recommendation_routes.search_music_for_recommendation")
def test_search_music_quota_error(mock_search, client):
    """Test YouTube quota error returns 503 with friendly message."""
    mock_search.side_effect = YouTubeQuotaError("Quota exceeded")

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["ai_recommendation"] = SAMPLE_AI_RECOMMENDATION

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 503
    data = res.get_json()
    assert "temporarily unavailable" in data.get("error", "").lower()


@patch("routes.recommendation_routes.search_music_for_recommendation")
def test_search_music_config_error(mock_search, client):
    """Test YouTube configuration error returns 503 with friendly message."""
    mock_search.side_effect = YouTubeConfigurationError("Missing API key")

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["ai_recommendation"] = SAMPLE_AI_RECOMMENDATION

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 503
    data = res.get_json()
    assert "not configured" in data.get("error", "").lower()


@patch("routes.recommendation_routes.search_music_for_recommendation")
def test_search_music_service_error(mock_search, client):
    """Test YouTube service error returns 500 with friendly message."""
    mock_search.side_effect = YouTubeServiceError("Unknown failure")

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["ai_recommendation"] = SAMPLE_AI_RECOMMENDATION

    res = client.post("/search-music", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 500
    data = res.get_json()
    assert "couldn't load music" in data.get("error", "").lower()


def test_homepage_renders_session_youtube_results(client):
    """Test GET / renders music cards directly from session without making API calls."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Sudharshan"
        sess["selected_mood"] = "Happy"
        sess["selected_language"] = "Kannada"
        sess["ai_recommendation"] = SAMPLE_AI_RECOMMENDATION
        sess["youtube_results"] = SAMPLE_VIDEOS

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Your MoodTune Picks" in html
    assert "Belakina Kavithe" in html
    assert "Ra Ra Rakkamma" in html
    assert "Sandalwood Hits" in html
    assert "vid_kannada_01" in html
