"""Unit tests for YouTube Data API service in MoodTune.

Tests all service functionality with mocked responses (no real YouTube API calls).
"""
import pytest
from unittest.mock import patch, MagicMock
import requests

from services.youtube_service import (
    parse_video_item,
    get_youtube_api_key,
    search_youtube_query,
    search_music_for_recommendation,
    YouTubeServiceError,
    YouTubeConfigurationError,
    YouTubeQuotaError,
    YouTubeAPIError,
    YouTubeNetworkError,
)


# Sample mock YouTube search items
MOCK_ITEM_1 = {
    "kind": "youtube#searchResult",
    "id": {"kind": "youtube#video", "videoId": "vid_kannada_01"},
    "snippet": {
        "publishedAt": "2024-01-15T12:00:00Z",
        "channelTitle": "Sandalwood Hits &amp; Music",
        "title": "Belakina Kavithe &bull; Superhit Kannada Song",
        "description": "Listen to the happiest Kannada song ever produced.",
        "thumbnails": {
            "default": {"url": "https://i.ytimg.com/vi/vid_kannada_01/default.jpg"},
            "medium": {"url": "https://i.ytimg.com/vi/vid_kannada_01/mqdefault.jpg"},
            "high": {"url": "https://i.ytimg.com/vi/vid_kannada_01/hqdefault.jpg"},
        },
    },
}

MOCK_ITEM_2 = {
    "kind": "youtube#searchResult",
    "id": {"kind": "youtube#video", "videoId": "vid_kannada_02"},
    "snippet": {
        "publishedAt": "2024-02-10T15:30:00Z",
        "channelTitle": "Anand Audio",
        "title": "Ra Ra Rakkamma &#39;Feat. Kiccha&#39; &amp; Party",
        "description": "High voltage Kannada dance track.",
        "thumbnails": {
            "high": {"url": "https://i.ytimg.com/vi/vid_kannada_02/hqdefault.jpg"},
        },
    },
}

MOCK_ITEM_3 = {
    "kind": "youtube#searchResult",
    "id": {"kind": "youtube#video", "videoId": "vid_kannada_03"},
    "snippet": {
        "publishedAt": "2024-03-01T08:00:00Z",
        "channelTitle": "Lahari Music",
        "title": "Tagaru Banthu Tagaru",
        "description": "Energetic Kannada track.",
        "thumbnails": {},
    },
}


def test_parse_video_item_valid():
    """Test parsing a well-formed video item extracts clean, unescaped, compact data."""
    parsed = parse_video_item(MOCK_ITEM_1)
    assert parsed is not None
    assert parsed["video_id"] == "vid_kannada_01"
    # Verify HTML entities decoded: &bull; -> •
    assert "•" in parsed["title"]
    # Verify HTML entities decoded: &amp; -> &
    assert parsed["channel_title"] == "Sandalwood Hits & Music"
    assert parsed["thumbnail"] == "https://i.ytimg.com/vi/vid_kannada_01/hqdefault.jpg"
    assert parsed["youtube_url"] == "https://www.youtube.com/watch?v=vid_kannada_01"
    # Ensure description and raw response metadata are excluded to keep session cookie small
    assert "description" not in parsed
    assert "raw" not in parsed


def test_parse_video_item_html_entities():
    """Test unescaping of single quotes and ampersands."""
    parsed = parse_video_item(MOCK_ITEM_2)
    assert parsed is not None
    assert "'Feat. Kiccha'" in parsed["title"]
    assert "& Party" in parsed["title"]


def test_parse_video_item_thumbnail_fallback():
    """Test fallback thumbnail URL generated when thumbnail object is empty."""
    parsed = parse_video_item(MOCK_ITEM_3)
    assert parsed is not None
    assert parsed["thumbnail"] == "https://i.ytimg.com/vi/vid_kannada_03/hqdefault.jpg"


def test_parse_video_item_missing_video_id():
    """Test rejection of items without a videoId."""
    item_no_id = {"snippet": {"title": "No ID Track"}}
    assert parse_video_item(item_no_id) is None

    item_channel = {"id": {"channelId": "UC12345"}, "snippet": {"title": "Channel"}}
    assert parse_video_item(item_channel) is None


def test_parse_video_item_missing_snippet():
    """Test handling of items without a snippet."""
    item_no_snippet = {"id": {"videoId": "vid_test"}}
    assert parse_video_item(item_no_snippet) is None


def test_get_youtube_api_key_missing():
    """Test YouTubeConfigurationError raised when key is missing or placeholder."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(YouTubeConfigurationError):
            get_youtube_api_key()

    with patch.dict("os.environ", {"YOUTUBE_API_KEY": "your_youtube_api_key_here"}):
        with pytest.raises(YouTubeConfigurationError):
            get_youtube_api_key()


def test_get_youtube_api_key_valid():
    """Test valid API key is returned."""
    with patch.dict("os.environ", {"YOUTUBE_API_KEY": "AIzaSyTestValidKey123"}):
        key = get_youtube_api_key()
        assert key == "AIzaSyTestValidKey123"


@patch("requests.get")
def test_search_youtube_query_success(mock_get):
    """Test successful search.list call returns parsed compact videos."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [MOCK_ITEM_1, MOCK_ITEM_2]
    }
    mock_get.return_value = mock_response

    results = search_youtube_query("Kannada happy songs", max_results=4, api_key="dummy_key")
    assert len(results) == 2
    assert results[0]["video_id"] == "vid_kannada_01"
    assert results[1]["video_id"] == "vid_kannada_02"
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["q"] == "Kannada happy songs"
    assert call_kwargs["params"]["part"] == "snippet"
    assert call_kwargs["params"]["type"] == "video"
    assert call_kwargs["params"]["videoEmbeddable"] == "true"


@patch("requests.get")
def test_search_youtube_query_quota_error(mock_get):
    """Test HTTP 403 quotaExceeded raises YouTubeQuotaError."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {
            "errors": [{"reason": "quotaExceeded", "message": "Quota exceeded"}],
            "code": 403,
            "message": "Quota exceeded",
        }
    }
    mock_get.return_value = mock_response

    with pytest.raises(YouTubeQuotaError) as exc_info:
        search_youtube_query("Kannada songs", api_key="dummy_key")
    assert "quota" in str(exc_info.value).lower()
    assert "temporarily unavailable" in exc_info.value.user_message.lower()


@patch("requests.get")
def test_search_youtube_query_auth_error(mock_get):
    """Test HTTP 400/401 raises YouTubeConfigurationError."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": {"message": "API key not valid."}}
    mock_get.return_value = mock_response

    with pytest.raises(YouTubeConfigurationError):
        search_youtube_query("Kannada songs", api_key="invalid_key")


@patch("requests.get")
def test_search_youtube_query_network_timeout(mock_get):
    """Test request timeout raises YouTubeNetworkError."""
    mock_get.side_effect = requests.Timeout("Connection timed out")

    with pytest.raises(YouTubeNetworkError) as exc_info:
        search_youtube_query("Kannada songs", api_key="dummy_key")
    assert "timed out" in str(exc_info.value).lower()


@patch("requests.get")
def test_search_youtube_query_empty_response(mock_get):
    """Test empty search results return empty list without error."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    results = search_youtube_query("NonExistentGenreSong12345", api_key="dummy_key")
    assert results == []


@patch("services.youtube_service.search_youtube_query")
def test_search_music_for_recommendation_deduplication(mock_search_query):
    """Test that duplicate video IDs across multiple AI search queries are deduplicated."""
    # Query 1 returns MOCK_ITEM_1 and MOCK_ITEM_2
    # Query 2 returns MOCK_ITEM_2 (duplicate!) and MOCK_ITEM_3
    mock_search_query.side_effect = [
        [parse_video_item(MOCK_ITEM_1), parse_video_item(MOCK_ITEM_2)],
        [parse_video_item(MOCK_ITEM_2), parse_video_item(MOCK_ITEM_3)],
    ]

    queries = ["Kannada happy songs", "Kannada upbeat melodies", "Kannada celebration tracks"]
    results = search_music_for_recommendation(queries, max_total_results=6, api_key="dummy_key")

    # Only top 2 queries should be executed to protect quota
    assert mock_search_query.call_count == 2
    # Total results should be 3 unique items (MOCK_ITEM_2 deduplicated)
    assert len(results) == 3
    video_ids = [v["video_id"] for v in results]
    assert video_ids == ["vid_kannada_01", "vid_kannada_02", "vid_kannada_03"]


@patch("services.youtube_service.search_youtube_query")
def test_search_music_for_recommendation_result_limit(mock_search_query):
    """Test that result count respects max_total_results cap."""
    items = []
    for i in range(10):
        items.append({
            "video_id": f"vid_{i}",
            "title": f"Song {i}",
            "channel_title": "Artist",
            "thumbnail": "https://i.ytimg.com/thumb.jpg",
            "youtube_url": f"https://www.youtube.com/watch?v=vid_{i}",
        })
    mock_search_query.return_value = items

    results = search_music_for_recommendation(["Query 1"], max_total_results=4, api_key="dummy_key")
    assert len(results) == 4


def test_search_music_for_recommendation_empty_queries():
    """Test handling of empty or invalid query lists."""
    assert search_music_for_recommendation([]) == []
    assert search_music_for_recommendation(["", "   "]) == []
    assert search_music_for_recommendation(None) == []


@patch("services.youtube_service.search_youtube_query")
def test_search_music_for_recommendation_target_18(mock_search_query):
    """Test that search_music_for_recommendation can collect up to 18 songs across queries with early stopping."""
    def fake_search(query, max_results=10, api_key=None):
        return [
            {
                "video_id": f"{query}_vid_{i}",
                "title": f"Song {query} {i}",
                "channel_title": "Artist",
                "thumbnail": "https://i.ytimg.com/thumb.jpg",
                "youtube_url": f"https://www.youtube.com/watch?v={query}_vid_{i}",
            }
            for i in range(max_results)
        ]

    mock_search_query.side_effect = fake_search
    queries = ["Kannada sad melodies", "Kannada emotional hits", "Kannada slow acoustic", "Kannada soulful vibes"]
    results = search_music_for_recommendation(queries, max_total_results=18, api_key="dummy_key")
    assert len(results) == 18
    unique_ids = {r["video_id"] for r in results}
    assert len(unique_ids) == 18
    # Quota safety: stopped immediately after 2 queries reached 18 songs
    assert mock_search_query.call_count == 2


@patch("services.youtube_service.search_youtube_query")
def test_search_music_early_stop_user_example(mock_search_query):
    """Test exact user scenario: Query 1 (10 unique), Query 2 (8 new), Total 18 -> STOP."""
    # Query 1 returns 10 unique videos
    q1_videos = [
        {"video_id": f"q1_vid_{i}", "title": f"Song 1-{i}", "channel_title": "A", "thumbnail": "", "youtube_url": ""}
        for i in range(10)
    ]
    # Query 2 returns 8 new videos and 2 duplicate videos from Query 1
    q2_videos = [
        {"video_id": f"q2_vid_{i}", "title": f"Song 2-{i}", "channel_title": "A", "thumbnail": "", "youtube_url": ""}
        for i in range(8)
    ] + [q1_videos[0], q1_videos[1]]

    mock_search_query.side_effect = [q1_videos, q2_videos]

    queries = ["Query 1", "Query 2", "Query 3", "Query 4"]
    results = search_music_for_recommendation(queries, max_total_results=18, api_key="dummy_key")

    assert len(results) == 18
    assert mock_search_query.call_count == 2
    # Ensure Queries 3 and 4 were never called
    called_queries = [call.kwargs.get("query") or call.args[0] if call.args else call.kwargs.get("query") for call in mock_search_query.call_args_list]
    assert "Query 3" not in called_queries
    assert "Query 4" not in called_queries


@patch("services.youtube_service.search_youtube_query")
def test_search_music_no_fabrication_when_under_target(mock_search_query):
    """Test that if fewer than 18 unique items exist, only real items are returned without fabrication."""
    mock_search_query.side_effect = [
        [{"video_id": f"q{q}_vid_{i}", "title": f"S{q}{i}", "channel_title": "A", "thumbnail": "", "youtube_url": ""} for i in range(3)]
        for q in range(1, 5)
    ]

    queries = ["Query 1", "Query 2", "Query 3", "Query 4"]
    results = search_music_for_recommendation(queries, max_total_results=18, api_key="dummy_key")

    # All 4 queries were attempted because 18 was never reached
    assert mock_search_query.call_count == 4
    # Returned exactly 12 unique real items without padding or fake IDs
    assert len(results) == 12
    video_ids = [r["video_id"] for r in results]
    assert len(set(video_ids)) == 12


@patch("requests.get")
def test_search_youtube_query_enforces_video_embeddable_and_type(mock_get):
    """Verify search_youtube_query strictly enforces videoEmbeddable=true and type=video."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    search_youtube_query("Sample Query", max_results=5, api_key="dummy_key")

    mock_get.assert_called_once()
    params = mock_get.call_args[1]["params"]
    assert params["videoEmbeddable"] == "true"
    assert params["type"] == "video"


