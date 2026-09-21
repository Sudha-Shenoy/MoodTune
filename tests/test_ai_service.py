"""Unit tests for services/ai_service.py with mocked external calls."""
import json
from unittest.mock import patch, MagicMock
import pytest
import requests

from services.ai_service import (
    validate_inputs,
    build_prompt,
    parse_and_validate_response,
    generate_music_recommendation,
    AIServiceError,
    AIConfigurationError,
    AIValidationError,
    AITimeoutError,
    AIProviderError,
    ALLOWED_MOODS,
    ALLOWED_LANGUAGES,
)


# 1. Valid mood & language accepted and normalized
def test_validate_inputs_valid():
    """Verify supported mood and language are accepted and returned with canonical casing."""
    mood, lang = validate_inputs("happy", "kannada")
    assert mood == "Happy"
    assert lang == "Kannada"

    mood2, lang2 = validate_inputs("RELAXED", "Hindi")
    assert mood2 == "Relaxed"
    assert lang2 == "Hindi"


# 2. Invalid mood rejected
def test_validate_inputs_invalid_mood():
    """Verify invalid/unsupported mood raises AIValidationError."""
    with pytest.raises(AIValidationError) as exc_info:
        validate_inputs("Furious", "Kannada")
    assert "Unsupported mood" in str(exc_info.value)


# 3. Invalid language rejected
def test_validate_inputs_invalid_language():
    """Verify invalid/unsupported language raises AIValidationError."""
    with pytest.raises(AIValidationError) as exc_info:
        validate_inputs("Happy", "Latin")
    assert "Unsupported language" in str(exc_info.value)


# 4. Empty or non-string inputs rejected
def test_validate_inputs_empty_or_none():
    """Verify None or empty strings are rejected."""
    with pytest.raises(AIValidationError):
        validate_inputs("", "Kannada")
    with pytest.raises(AIValidationError):
        validate_inputs("Happy", None)


# 5. Prompt construction includes constraints and schema
def test_build_prompt_structure():
    """Verify the prompt contains role, constraints, search intent, and schema."""
    prompt = build_prompt("Happy", "Kannada")
    assert "system" in prompt
    assert "user" in prompt
    assert "full_text" in prompt

    full = prompt["full_text"]
    assert "MoodTune's music recommendation assistant" in full
    assert "Happy" in full
    assert "Kannada" in full
    assert "DO NOT invent specific songs" in full
    assert "DO NOT provide YouTube" in full
    assert "music_style" in full
    assert "search_queries" in full


# 6. Valid JSON response parsed and schema enforced
def test_parse_and_validate_response_valid():
    """Verify raw JSON with valid fields passes validation."""
    raw = json.dumps({
        "mood": "Happy",
        "language": "Kannada",
        "music_style": ["upbeat", "positive", "energetic", "feel-good"],
        "search_queries": [
            "Kannada happy songs",
            "Kannada upbeat melodies",
            "Kannada celebration music"
        ],
        "description": "Bright and uplifting Kannada music with high energy."
    })

    result = parse_and_validate_response(raw, "Happy", "Kannada")
    assert result["mood"] == "Happy"
    assert result["language"] == "Kannada"
    assert len(result["music_style"]) == 4
    assert len(result["search_queries"]) == 3
    assert "uplifting" in result["description"]


# 7. Strips markdown fences if wrapped
def test_parse_and_validate_response_markdown_wrapped():
    """Verify markdown code fences like ```json ... ``` are cleanly stripped."""
    raw = """```json
    {
        "mood": "Chill",
        "language": "English",
        "music_style": ["lo-fi", "mellow", "acoustic"],
        "search_queries": [
            "English chill beats",
            "English relaxing indie",
            "English acoustic calm"
        ],
        "description": "Laid-back acoustic indie beats for relaxation."
    }
    ```"""

    result = parse_and_validate_response(raw, "Chill", "English")
    assert result["mood"] == "Chill"
    assert result["language"] == "English"
    assert len(result["music_style"]) == 3


# 8. Malformed JSON raises AIValidationError
def test_parse_and_validate_response_malformed_json():
    """Verify unparseable JSON text raises AIValidationError."""
    with pytest.raises(AIValidationError) as exc_info:
        parse_and_validate_response("This is not JSON at all!", "Happy", "Kannada")
    assert "Failed to parse AI response" in str(exc_info.value)


# 9. Missing required fields raises AIValidationError
def test_parse_and_validate_response_missing_keys():
    """Verify missing required key raises AIValidationError."""
    raw = json.dumps({
        "mood": "Happy",
        "language": "Kannada",
        "music_style": ["upbeat", "positive", "energetic"],
        # Missing "search_queries" and "description"
    })
    with pytest.raises(AIValidationError) as exc_info:
        parse_and_validate_response(raw, "Happy", "Kannada")
    assert "Missing required fields" in str(exc_info.value)


# 10. Bounds check: music_style requires 3 to 6 items
def test_parse_and_validate_response_music_style_bounds():
    """Verify music_style with fewer than 3 or more than 6 items is rejected."""
    # Too few (2 items)
    too_few = json.dumps({
        "mood": "Sad",
        "language": "Tamil",
        "music_style": ["melancholic", "slow"],
        "search_queries": ["Tamil sad songs", "Tamil emotional melody", "Tamil sorrow music"],
        "description": "Slow and soulful Tamil melodies."
    })
    with pytest.raises(AIValidationError):
        parse_and_validate_response(too_few, "Sad", "Tamil")

    # Too many (7 items)
    too_many = json.dumps({
        "mood": "Sad",
        "language": "Tamil",
        "music_style": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"],
        "search_queries": ["Tamil sad songs", "Tamil emotional melody", "Tamil sorrow music"],
        "description": "Slow and soulful Tamil melodies."
    })
    with pytest.raises(AIValidationError):
        parse_and_validate_response(too_many, "Sad", "Tamil")


# 11. Bounds check: search_queries requires 3 to 5 items
def test_parse_and_validate_response_search_queries_bounds():
    """Verify search_queries with fewer than 3 or more than 5 items is rejected."""
    too_few = json.dumps({
        "mood": "Energetic",
        "language": "Punjabi",
        "music_style": ["bhangra", "bass", "loud"],
        "search_queries": ["Punjabi bhangra", "Punjabi dance"],  # Only 2
        "description": "High-octane Punjabi dance beats."
    })
    with pytest.raises(AIValidationError):
        parse_and_validate_response(too_few, "Energetic", "Punjabi")


# 12. Mismatched mood raises AIValidationError
def test_parse_and_validate_response_mismatched_mood():
    """Verify AI returning a different mood than requested is rejected."""
    raw = json.dumps({
        "mood": "Sad",  # Requested "Happy"
        "language": "Kannada",
        "music_style": ["upbeat", "positive", "energetic"],
        "search_queries": ["Kannada songs 1", "Kannada songs 2", "Kannada songs 3"],
        "description": "Vibe summary."
    })
    with pytest.raises(AIValidationError):
        parse_and_validate_response(raw, "Happy", "Kannada")


# 13. Missing API key raises AIConfigurationError
@patch("services.ai_service.get_ai_config")
def test_generate_recommendation_missing_key(mock_config):
    """Verify AIConfigurationError is raised when API key is missing or placeholder."""
    mock_config.return_value = ("", "gemini", "gemini-1.5-flash", None)
    with pytest.raises(AIConfigurationError):
        generate_music_recommendation("Happy", "Kannada")


# 14. Mocked Gemini API call success
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_gemini_success(mock_post, mock_config):
    """Verify successful Gemini API response is properly parsed and returned."""
    mock_config.return_value = ("AIzaFakeGeminiKey123", "gemini", "gemini-1.5-flash", None)

    mock_gemini_response = MagicMock()
    mock_gemini_response.ok = True
    mock_gemini_response.status_code = 200
    mock_gemini_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "mood": "Happy",
                        "language": "Kannada",
                        "music_style": ["upbeat", "energetic", "celebratory", "melodic"],
                        "search_queries": [
                            "Kannada upbeat hit songs",
                            "Kannada happy melodies",
                            "Kannada party dance songs"
                        ],
                        "description": "Uplifting Kannada songs full of celebration and joy."
                    })
                }]
            }
        }]
    }
    mock_post.return_value = mock_gemini_response

    result = generate_music_recommendation("Happy", "Kannada")
    assert result["mood"] == "Happy"
    assert result["language"] == "Kannada"
    assert len(result["music_style"]) == 4
    assert len(result["search_queries"]) == 3
    assert "Uplifting" in result["description"]
    mock_post.assert_called_once()


# 15. Mocked OpenAI API call success
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_openai_success(mock_post, mock_config):
    """Verify successful OpenAI-compatible API response is properly parsed and returned."""
    mock_config.return_value = ("sk-FakeOpenAIKey123", "openai", "gpt-4o-mini", None)

    mock_openai_response = MagicMock()
    mock_openai_response.ok = True
    mock_openai_response.status_code = 200
    mock_openai_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "mood": "Chill",
                    "language": "Hindi",
                    "music_style": ["acoustic", "lo-fi", "soothing"],
                    "search_queries": [
                        "Hindi chill acoustic songs",
                        "Hindi lo-fi soothing tracks",
                        "Hindi calm evening playlist"
                    ],
                    "description": "Relaxed Hindi acoustic tracks with gentle melodies."
                })
            }
        }]
    }
    mock_post.return_value = mock_openai_response

    result = generate_music_recommendation("Chill", "Hindi")
    assert result["mood"] == "Chill"
    assert result["language"] == "Hindi"
    assert len(result["music_style"]) == 3
    assert len(result["search_queries"]) == 3


# 16. API Timeout raises AITimeoutError
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_timeout(mock_post, mock_config):
    """Verify requests.exceptions.Timeout raises AITimeoutError."""
    mock_config.return_value = ("AIzaFakeKey", "gemini", "gemini-1.5-flash", None)
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    with pytest.raises(AITimeoutError):
        generate_music_recommendation("Relaxed", "English")


# 17. Connection Error raises AIProviderError
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_connection_error(mock_post, mock_config):
    """Verify network connection failures raise AIProviderError."""
    mock_config.return_value = ("AIzaFakeKey", "gemini", "gemini-1.5-flash", None)
    mock_post.side_effect = requests.exceptions.ConnectionError("DNS failure")

    with pytest.raises(AIProviderError):
        generate_music_recommendation("Relaxed", "English")


# 18. Provider HTTP 500 raises AIProviderError
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_http_500(mock_post, mock_config):
    """Verify HTTP 500 error from upstream provider raises AIProviderError."""
    mock_config.return_value = ("AIzaFakeKey", "gemini", "gemini-1.5-flash", None)
    mock_res = MagicMock()
    mock_res.ok = False
    mock_res.status_code = 500
    mock_res.text = "Internal Server Error"
    mock_post.return_value = mock_res

    with pytest.raises(AIProviderError):
        generate_music_recommendation("Party", "Punjabi")


# 19. Provider Auth Failure (HTTP 401) raises AIProviderError
@patch("services.ai_service.get_ai_config")
@patch("requests.post")
def test_generate_recommendation_auth_failure(mock_post, mock_config):
    """Verify HTTP 401 Unauthorized from upstream raises AIProviderError without exposing key."""
    mock_config.return_value = ("AIzaBadKey", "gemini", "gemini-1.5-flash", None)
    mock_res = MagicMock()
    mock_res.ok = False
    mock_res.status_code = 401
    mock_res.text = "API_KEY_INVALID"
    mock_post.return_value = mock_res

    with pytest.raises(AIProviderError) as exc_info:
        generate_music_recommendation("Party", "Punjabi")
    assert "AIzaBadKey" not in str(exc_info.value)
