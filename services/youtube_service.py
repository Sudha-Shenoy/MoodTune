"""YouTube Data API v3 service for MoodTune.

Handles searching public YouTube music videos based on AI-generated search queries,
with quota-conscious controls, duplicate removal, HTML entity decoding, and
compact data structuring suitable for client-side cookies and Module 07 handoff.
"""
import html
import logging
import os
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DEFAULT_TIMEOUT_SECONDS = 10
PLACEHOLDER_KEYS = {
    "",
    "your_youtube_api_key_here",
    "your_actual_key",
    "placeholder",
    "none",
}


# ============================================================================
# Exceptions
# ============================================================================

class YouTubeServiceError(Exception):
    """Base exception for all YouTube service failures."""

    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(message)
        self.user_message = (
            user_message
            or "MoodTune couldn't load music right now. Please try again."
        )


class YouTubeConfigurationError(YouTubeServiceError):
    """Raised when YOUTUBE_API_KEY is missing or contains placeholder values."""

    def __init__(self, message: str = "YouTube API key is missing or invalid"):
        super().__init__(
            message,
            user_message="YouTube search service is not configured. Please check your API key.",
        )


class YouTubeQuotaError(YouTubeServiceError):
    """Raised when the YouTube Data API quota has been exceeded."""

    def __init__(self, message: str = "YouTube API quota exceeded"):
        super().__init__(
            message,
            user_message="Music search is temporarily unavailable. Please try again later.",
        )


class YouTubeAPIError(YouTubeServiceError):
    """Raised when YouTube Data API returns an HTTP 4xx or 5xx error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(
            f"YouTube API error ({status_code}): {message}",
            user_message="MoodTune couldn't load music from YouTube right now. Please try again.",
        )
        self.status_code = status_code


class YouTubeNetworkError(YouTubeServiceError):
    """Raised when network timeouts or connection failures occur."""

    def __init__(self, message: str):
        super().__init__(
            f"YouTube network error: {message}",
            user_message="Network connection to YouTube failed. Please check your connection and try again.",
        )


# ============================================================================
# Helper Functions
# ============================================================================

def get_youtube_api_key() -> str:
    """Retrieve and validate the YouTube Data API key from environment.

    Returns:
        The valid API key string.

    Raises:
        YouTubeConfigurationError: If key is unset or a placeholder.
    """
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key or key.lower() in PLACEHOLDER_KEYS:
        raise YouTubeConfigurationError("Missing or placeholder YOUTUBE_API_KEY.")
    return key


def parse_video_item(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Parse and validate a single YouTube search item into a compact dictionary.

    Excludes full descriptions and raw API metadata to keep Flask session cookie small.

    Args:
        item: Raw item dictionary from YouTube search response.

    Returns:
        Compact video dict or None if invalid.
    """
    if not isinstance(item, dict):
        return None

    video_id_data = item.get("id")
    if not isinstance(video_id_data, dict):
        return None

    video_id = video_id_data.get("videoId")
    if not video_id or not isinstance(video_id, str):
        return None

    snippet = item.get("snippet")
    if not isinstance(snippet, dict):
        return None

    raw_title = snippet.get("title") or "Untitled Track"
    raw_channel = snippet.get("channelTitle") or "Unknown Artist"

    # Decode HTML entities (e.g. &amp;, &#39;, &quot;)
    title = html.unescape(str(raw_title)).strip()
    channel_title = html.unescape(str(raw_channel)).strip()

    # Extract best available thumbnail URL
    thumbnails = snippet.get("thumbnails") or {}
    thumbnail_url = ""
    if isinstance(thumbnails, dict):
        for quality in ("high", "medium", "default"):
            thumb_obj = thumbnails.get(quality)
            if isinstance(thumb_obj, dict) and thumb_obj.get("url"):
                thumbnail_url = thumb_obj["url"]
                break

    # Fallback to standard YouTube thumbnail URL if none in snippet
    if not thumbnail_url:
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return {
        "video_id": video_id,
        "title": title,
        "channel_title": channel_title,
        "thumbnail": thumbnail_url,
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
    }


def search_youtube_query(
    query: str,
    max_results: int = 4,
    api_key: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> List[Dict[str, str]]:
    """Perform a single search.list call against YouTube Data API v3.

    `search.list` costs 1 quota unit per API call.

    Args:
        query: Music search string.
        max_results: Small controlled number of videos to fetch (default 4).
        api_key: Optional explicit API key. Defaults to environment key.
        timeout: HTTP request timeout in seconds.

    Returns:
        List of parsed compact video dictionaries.

    Raises:
        YouTubeConfigurationError: Missing/invalid key.
        YouTubeQuotaError: Quota limit exceeded.
        YouTubeAPIError: HTTP error from YouTube API.
        YouTubeNetworkError: Connection error or timeout.
    """
    if not api_key:
        api_key = get_youtube_api_key()

    if not query or not query.strip():
        return []

    params = {
        "part": "snippet",
        "type": "video",
        "q": query.strip(),
        "maxResults": min(max(1, max_results), 10),
        "key": api_key,
    }

    try:
        response = requests.get(
            YOUTUBE_SEARCH_URL,
            params=params,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
    except (requests.Timeout, requests.exceptions.ConnectTimeout) as exc:
        logger.warning(f"YouTube API request timed out for query '{query}': {exc}")
        raise YouTubeNetworkError("Request to YouTube API timed out.") from exc
    except requests.RequestException as exc:
        logger.warning(f"YouTube network connection error for query '{query}': {exc}")
        raise YouTubeNetworkError("Connection to YouTube API failed.") from exc

    # Handle HTTP error responses
    if response.status_code == 403:
        try:
            error_data = response.json().get("error", {})
            errors = error_data.get("errors", [])
            reasons = {e.get("reason") for e in errors if isinstance(e, dict)}
            if "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons:
                logger.error("YouTube Data API quota exceeded (quotaExceeded).")
                raise YouTubeQuotaError("YouTube API quota exceeded.")
        except YouTubeQuotaError:
            raise
        except Exception:
            pass

        logger.error(f"YouTube API returned 403 Forbidden: {response.status_code}")
        raise YouTubeAPIError("Access forbidden or quota exceeded.", status_code=403)

    if response.status_code in (400, 401):
        logger.error(f"YouTube API authentication/client error ({response.status_code})")
        raise YouTubeConfigurationError("Invalid YouTube API key or request parameters.")

    if not response.ok:
        logger.error(f"YouTube API request failed with status {response.status_code}")
        raise YouTubeAPIError(
            f"API returned status {response.status_code}", status_code=response.status_code
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error(f"Failed to parse JSON response from YouTube API: {exc}")
        raise YouTubeAPIError("Malformed JSON response from YouTube API.") from exc

    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        return []

    results: List[Dict[str, str]] = []
    for item in raw_items:
        parsed = parse_video_item(item)
        if parsed:
            results.append(parsed)

    return results


def search_music_for_recommendation(
    search_queries: List[str],
    max_total_results: int = 6,
    api_key: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Execute a controlled search strategy using Module 05 AI search queries.

    Rules enforced:
    1. Selects only the top 1-2 AI search queries to minimize quota usage.
    2. Fetches 3-4 videos per query.
    3. Merges and deduplicates videos by `video_id`.
    4. Caps final result count at `max_total_results` (default 6, maximum 8).
    5. Returns compact video objects (strictly no descriptions or raw payloads).

    Args:
        search_queries: List of AI-generated search query strings.
        max_total_results: Maximum number of songs to return (default 6).
        api_key: Optional YouTube API key.

    Returns:
        List of unique, compact video dictionaries.
    """
    if not isinstance(search_queries, list) or not search_queries:
        logger.warning("Empty or invalid search_queries provided to search_music_for_recommendation.")
        return []

    # Clean queries and select top 1-2
    candidate_queries = [q.strip() for q in search_queries if isinstance(q, str) and q.strip()][:2]
    if not candidate_queries:
        return []

    if not api_key:
        api_key = get_youtube_api_key()

    target_cap = min(max(1, max_total_results), 8)
    # If 2 queries, fetch 4 per query; if 1 query, fetch up to 6
    per_query_limit = 4 if len(candidate_queries) > 1 else min(target_cap, 6)

    seen_video_ids = set()
    deduped_videos: List[Dict[str, str]] = []

    for query in candidate_queries:
        if len(deduped_videos) >= target_cap:
            break

        query_videos = search_youtube_query(
            query=query,
            max_results=per_query_limit,
            api_key=api_key,
        )

        for video in query_videos:
            vid = video["video_id"]
            if vid not in seen_video_ids:
                seen_video_ids.add(vid)
                deduped_videos.append(video)
                if len(deduped_videos) >= target_cap:
                    break

    return deduped_videos
