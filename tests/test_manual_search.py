"""Unit and integration tests for MoodTune Module 08 Part B: Manual YouTube Music Search.

Tests direct keyword music searching, single-request quota safety (maxResults=12),
deduplication, zero Gemini AI calls, input validation, and YouTube error handling.
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


MOCK_MANUAL_SEARCH_RESULTS = [
    {
        "video_id": "vid_manual_01",
        "title": "Arijit Singh Melody Mashup",
        "channel_title": "T-Series",
        "thumbnail": "https://i.ytimg.com/vi/vid_manual_01/hqdefault.jpg",
        "youtube_url": "https://www.youtube.com/watch?v=vid_manual_01",
    },
    {
        "video_id": "vid_manual_02",
        "title": "Tum Hi Ho Official Video",
        "channel_title": "T-Series",
        "thumbnail": "https://i.ytimg.com/vi/vid_manual_02/hqdefault.jpg",
        "youtube_url": "https://www.youtube.com/watch?v=vid_manual_02",
    },
    {
        "video_id": "vid_manual_03",
        "title": "Kesariya Audio Track",
        "channel_title": "Sony Music India",
        "thumbnail": "https://i.ytimg.com/vi/vid_manual_03/hqdefault.jpg",
        "youtube_url": "https://www.youtube.com/watch?v=vid_manual_03",
    },
]


# =========================================================================
# 1. Search Query Handling & Input Validation
# =========================================================================

def test_manual_search_empty_query_rejected(client):
    """Verify empty search query returns 400 with helpful error message."""
    resp = client.get("/search-music?q=", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    post_resp = client.post("/search-music", json={"query": ""})
    assert post_resp.status_code == 400
    assert "error" in post_resp.get_json()


def test_manual_search_whitespace_query_rejected(client):
    """Verify whitespace-only query returns 400."""
    resp = client.get("/search-music?q=%20%20%20", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_manual_search_too_long_query_rejected(client):
    """Verify query exceeding 100 characters returns 400."""
    long_query = "kannada " * 20
    resp = client.get(f"/search-music?q={long_query}", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 400
    assert "too long" in resp.get_json()["error"].lower()


# =========================================================================
# 2. Execution & Quota Safety
# =========================================================================

def test_manual_search_single_youtube_request_and_max_results_12(client):
    """Verify manual search executes exactly ONE YouTube search.list request with max_results=12."""
    with patch("routes.recommendation_routes.search_youtube_query", return_value=MOCK_MANUAL_SEARCH_RESULTS) as mock_search:
        resp = client.get(
            "/search-music?q=arijit+singh",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["manual_search"] is True
        assert data["query"] == "arijit singh"
        assert len(data["videos"]) == 3

        # Critical Quota Assertion: EXACTLY 1 request, max_results=12
        assert mock_search.call_count == 1
        call_kwargs = mock_search.call_args[1] if mock_search.call_args[1] else {}
        call_args = mock_search.call_args[0]
        query_arg = call_kwargs.get("query") or (call_args[0] if call_args else None)
        max_results_arg = call_kwargs.get("max_results") or (call_args[1] if len(call_args) > 1 else 12)

        assert query_arg == "arijit singh"
        assert max_results_arg == 12


def test_manual_search_post_json_payload(client):
    """Verify manual search works via POST JSON with query field."""
    with patch("routes.recommendation_routes.search_youtube_query", return_value=MOCK_MANUAL_SEARCH_RESULTS):
        resp = client.post(
            "/search-music",
            json={"query": "kannada bhavageethe"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["query"] == "kannada bhavageethe"
        assert len(data["videos"]) == 3


def test_manual_search_deduplicates_by_video_id(client):
    """Verify duplicate results from YouTube are deduplicated by video_id."""
    duplicate_results = [
        MOCK_MANUAL_SEARCH_RESULTS[0],
        MOCK_MANUAL_SEARCH_RESULTS[0],  # Duplicate
        MOCK_MANUAL_SEARCH_RESULTS[1],
        MOCK_MANUAL_SEARCH_RESULTS[1],  # Duplicate
    ]

    with patch("routes.recommendation_routes.search_youtube_query", return_value=duplicate_results):
        resp = client.get(
            "/search-music?q=test+query",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["videos"]) == 2
        assert data["videos"][0]["video_id"] == "vid_manual_01"
        assert data["videos"][1]["video_id"] == "vid_manual_02"


def test_manual_search_preserves_required_fields(client):
    """Verify search results preserve video_id, title, channel_title, thumbnail, and youtube_url."""
    with patch("routes.recommendation_routes.search_youtube_query", return_value=MOCK_MANUAL_SEARCH_RESULTS):
        resp = client.get("/search-music?q=test", headers={"X-Requested-With": "XMLHttpRequest"})
        data = resp.get_json()
        for v in data["videos"]:
            assert "video_id" in v
            assert "title" in v
            assert "channel_title" in v
            assert "thumbnail" in v
            assert "youtube_url" in v


def test_manual_search_never_invokes_gemini_ai(client):
    """Verify manual search NEVER invokes Gemini AI recommendation engine."""
    with patch("routes.recommendation_routes.search_youtube_query", return_value=MOCK_MANUAL_SEARCH_RESULTS), \
         patch("services.ai_service.generate_music_recommendation") as mock_ai:

        resp = client.get(
            "/search-music?q=folk+songs",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert resp.status_code == 200
        assert mock_ai.call_count == 0, "Gemini AI must never be called during manual YouTube search"


# =========================================================================
# 3. Error Handling & Full Page Rendering
# =========================================================================

def test_manual_search_quota_error(client):
    """Verify YouTubeQuotaError returns 503 with user-friendly message."""
    with patch("routes.recommendation_routes.search_youtube_query", side_effect=YouTubeQuotaError("Exceeded")):
        resp = client.get("/search-music?q=query", headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 503
        err_msg = resp.get_json()["error"].lower()
        assert "unavailable" in err_msg or "quota" in err_msg


def test_manual_search_service_error(client):
    """Verify YouTubeServiceError returns 500 with user-friendly message."""
    with patch("routes.recommendation_routes.search_youtube_query", side_effect=YouTubeServiceError("Down")):
        resp = client.get("/search-music?q=query", headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 500
        assert "error" in resp.get_json()


def test_manual_search_full_page_get_renders_index(client):
    """Verify full-page browser GET /search-music?q=... renders index.html with results."""
    with patch("routes.recommendation_routes.search_youtube_query", return_value=MOCK_MANUAL_SEARCH_RESULTS):
        resp = client.get("/search-music?q=Arijit")
        assert resp.status_code == 200
        assert b"Arijit Singh Melody Mashup" in resp.data
        assert b"Search Results for" in resp.data
