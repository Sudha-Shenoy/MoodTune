"""AI Recommendation Service for MoodTune.

Handles prompt building, interaction with external LLM APIs (Gemini & OpenAI-compatible),
strict output schema validation, and safe error handling without exposing secrets.
"""
import json
import logging
import os
import re
import requests
from flask import current_app

logger = logging.getLogger(__name__)

ALLOWED_MOODS = [
    "Happy",
    "Sad",
    "Energetic",
    "Relaxed",
    "Romantic",
    "Chill",
    "Motivated",
    "Party",
]

ALLOWED_LANGUAGES = [
    "Kannada",
    "Hindi",
    "English",
    "Tamil",
    "Telugu",
    "Malayalam",
    "Marathi",
    "Bengali",
    "Punjabi",
]

MOOD_LOOKUP = {m.lower(): m for m in ALLOWED_MOODS}
LANG_LOOKUP = {l.lower(): l for l in ALLOWED_LANGUAGES}

PLACEHOLDER_KEYS = {
    "",
    "your_ai_api_key_here",
    "your_actual_ai_api_key_here",
    "placeholder",
    "none",
}


class AIServiceError(Exception):
    """Base exception for AI recommendation engine errors."""

    def __init__(self, message, user_message=None):
        super().__init__(message)
        self.user_message = user_message or "Sorry, MoodTune couldn't create your recommendation right now. Please try again."


class AIConfigurationError(AIServiceError):
    """Raised when the AI API key or configuration is missing or placeholder."""

    def __init__(self, message="AI API key is not configured.", user_message=None):
        user_msg = user_message or "AI recommendation engine is not configured. Please set AI_API_KEY in your .env file."
        super().__init__(message, user_message=user_msg)


class AIValidationError(AIServiceError):
    """Raised when input parameters or AI response fails schema validation."""

    def __init__(self, message="Invalid AI recommendation format.", user_message=None):
        user_msg = user_message or "Sorry, MoodTune couldn't create your recommendation right now. Please try again."
        super().__init__(message, user_message=user_msg)


class AITimeoutError(AIServiceError):
    """Raised when the API request exceeds the configured timeout."""

    def __init__(self, message="AI recommendation request timed out.", user_message=None):
        user_msg = user_message or "AI recommendation request timed out. Please try again."
        super().__init__(message, user_message=user_msg)


class AIProviderError(AIServiceError):
    """Raised when upstream AI service fails or returns an error response."""

    def __init__(self, message="AI provider error occurred.", user_message=None):
        user_msg = user_message or "Sorry, MoodTune couldn't create your recommendation right now. Please try again."
        super().__init__(message, user_message=user_msg)


def validate_inputs(mood: str, language: str) -> tuple[str, str]:
    """Validate mood and language against allowed canonical lists.

    Raises AIValidationError if either value is unsupported or empty.
    """
    if not mood or not isinstance(mood, str):
        raise AIValidationError(f"Invalid mood value: {mood!r}")
    if not language or not isinstance(language, str):
        raise AIValidationError(f"Invalid language value: {language!r}")

    clean_mood = mood.strip().lower()
    clean_lang = language.strip().lower()

    if clean_mood not in MOOD_LOOKUP:
        raise AIValidationError(
            f"Unsupported mood '{mood}'. Must be one of: {', '.join(ALLOWED_MOODS)}"
        )
    if clean_lang not in LANG_LOOKUP:
        raise AIValidationError(
            f"Unsupported language '{language}'. Must be one of: {', '.join(ALLOWED_LANGUAGES)}"
        )

    return MOOD_LOOKUP[clean_mood], LANG_LOOKUP[clean_lang]


def build_prompt(mood: str, language: str) -> dict:
    """Construct controlled developer instructions and user prompt for the LLM."""
    system_instruction = (
        "You are MoodTune's music recommendation assistant. Your task is to analyze a listener's "
        "selected mood and language, then suggest musical characteristics, vibes, and search intent for music discovery."
    )

    user_instruction = f"""Selected Mood: {mood}
Selected Language: {language}

Task:
- Identify suitable musical characteristics and style attributes that match this mood in this language.
- Formulate search queries optimized for finding music in the given language matching this mood.
- Write a brief, inspiring description (1-2 sentences) summarizing the musical vibe.

Strict Constraints:
- DO NOT invent specific songs, track titles, or artist names.
- DO NOT claim that specific songs exist.
- DO NOT provide YouTube or other web links/URLs.
- DO NOT search the internet or output executable code.
- Focus strictly on musical search intent and style characteristics.

You MUST respond ONLY with a single valid JSON object following this exact schema:
{{
  "mood": "{mood}",
  "language": "{language}",
  "music_style": ["style1", "style2", "style3", "style4"],
  "search_queries": ["query1", "query2", "query3", "query4"],
  "description": "1-2 sentence description of the vibe."
}}

Rules for JSON:
- 'mood' must equal "{mood}"
- 'language' must equal "{language}"
- 'music_style' must be a JSON array containing between 3 and 6 short descriptor strings.
- 'search_queries' must be a JSON array containing between 3 and 5 search query strings tailored to find music in this language and mood.
- 'description' must be a non-empty string of 1 to 2 sentences.
- Do NOT wrap in markdown or backticks (return raw JSON only)."""

    return {
        "system": system_instruction,
        "user": user_instruction,
        "full_text": f"{system_instruction}\n\n{user_instruction}",
    }


def parse_and_validate_response(raw_text: str, expected_mood: str, expected_language: str) -> dict:
    """Parse raw LLM text into JSON and strictly enforce the output schema.

    Raises AIValidationError if parsing fails or fields are missing/malformed.
    """
    if not raw_text or not isinstance(raw_text, str):
        raise AIValidationError("Empty or non-string response received from AI service.")

    # Strip markdown code fences if present (e.g. ```json ... ```)
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        # Remove closing fence
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except Exception as exc:
        logger.error(f"Failed to parse AI JSON response: {exc}. Raw: {raw_text[:200]}")
        raise AIValidationError("Failed to parse AI response as valid JSON.") from exc

    if not isinstance(data, dict):
        raise AIValidationError(f"Expected JSON object, got {type(data).__name__}.")

    # Verify required keys
    required_keys = {"mood", "language", "music_style", "search_queries", "description"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise AIValidationError(f"Missing required fields in AI output: {', '.join(sorted(missing_keys))}")

    # Validate mood
    raw_mood = str(data.get("mood", "")).strip().lower()
    if raw_mood != expected_mood.lower():
        raise AIValidationError(f"AI returned mood '{data.get('mood')}', expected '{expected_mood}'.")

    # Validate language
    raw_lang = str(data.get("language", "")).strip().lower()
    if raw_lang != expected_language.lower():
        raise AIValidationError(f"AI returned language '{data.get('language')}', expected '{expected_language}'.")

    # Validate music_style array (3 to 6 non-empty strings)
    styles = data.get("music_style")
    if not isinstance(styles, list):
        raise AIValidationError("Field 'music_style' must be a list of strings.")
    if len(styles) < 3 or len(styles) > 6:
        raise AIValidationError(f"Field 'music_style' must contain 3 to 6 items, got {len(styles)}.")
    clean_styles = []
    for item in styles:
        if not isinstance(item, str) or not item.strip():
            raise AIValidationError("All items in 'music_style' must be non-empty strings.")
        clean_styles.append(item.strip())

    # Validate search_queries array (3 to 5 non-empty strings)
    queries = data.get("search_queries")
    if not isinstance(queries, list):
        raise AIValidationError("Field 'search_queries' must be a list of strings.")
    if len(queries) < 3 or len(queries) > 5:
        raise AIValidationError(f"Field 'search_queries' must contain 3 to 5 items, got {len(queries)}.")
    clean_queries = []
    for item in queries:
        if not isinstance(item, str) or not item.strip():
            raise AIValidationError("All items in 'search_queries' must be non-empty strings.")
        clean_queries.append(item.strip())

    # Validate description
    desc = data.get("description")
    if not isinstance(desc, str) or not desc.strip():
        raise AIValidationError("Field 'description' must be a non-empty string.")

    return {
        "mood": expected_mood,
        "language": expected_language,
        "music_style": clean_styles,
        "search_queries": clean_queries,
        "description": desc.strip(),
    }


def call_gemini_api(api_key: str, model: str, prompt_data: dict, timeout: int = 15) -> str:
    """Invoke Google Gemini generateContent using official google-genai SDK with REST fallback."""
    # 1. Attempt generation using the official google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt_data["full_text"],
        )
        if response and response.text:
            return response.text
    except Exception as sdk_err:
        logger.warning(f"google-genai SDK call error ({sdk_err}), falling back to direct REST request.")

    # 2. Fallback to direct REST API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt_data["full_text"]}]
        }],
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        logger.error("Gemini API request timed out.")
        raise AITimeoutError() from exc
    except requests.exceptions.RequestException as exc:
        logger.error(f"Gemini API connection error: {exc}")
        raise AIProviderError("Failed to connect to AI service.") from exc

    if response.status_code == 400:
        logger.error(f"Gemini API 400 Bad Request: {response.text}")
        raise AIProviderError("Invalid request to AI service.")
    elif response.status_code in (401, 403):
        logger.error(f"Gemini API authentication failed ({response.status_code}).")
        raise AIProviderError("AI authentication failed. Check API key configuration.")
    elif response.status_code == 404:
        logger.error(f"Gemini API 404 Not Found for model '{model}': {response.text}")
        raise AIProviderError(f"Configured Gemini model '{model}' was not found or is unavailable.")
    elif response.status_code == 429:
        logger.error("Gemini API rate limit exceeded.")
        raise AIProviderError("AI service is currently busy. Please try again in a moment.")
    elif not response.ok:
        logger.error(f"Gemini API error {response.status_code}: {response.text}")
        raise AIProviderError(f"AI service error (status {response.status_code}).")

    try:
        res_json = response.json()
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        return raw_text
    except Exception as exc:
        logger.error(f"Failed to extract candidate text from Gemini response: {exc}")
        raise AIValidationError("Unexpected response structure from AI provider.") from exc


def call_openai_api(api_key: str, model: str, prompt_data: dict, base_url: str = None, timeout: int = 15) -> str:
    """Invoke OpenAI or OpenAI-compatible Chat Completions API."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt_data["system"]},
            {"role": "user", "content": prompt_data["user"]},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        logger.error("OpenAI-compatible API request timed out.")
        raise AITimeoutError() from exc
    except requests.exceptions.RequestException as exc:
        logger.error(f"OpenAI-compatible API connection error: {exc}")
        raise AIProviderError("Failed to connect to AI service.") from exc

    if response.status_code in (401, 403):
        logger.error(f"OpenAI-compatible API authentication failed ({response.status_code}).")
        raise AIProviderError("AI authentication failed. Check API key configuration.")
    elif response.status_code == 429:
        logger.error("OpenAI-compatible API rate limit exceeded.")
        raise AIProviderError("AI service rate limit reached. Please wait a moment.")
    elif not response.ok:
        logger.error(f"OpenAI-compatible API error {response.status_code}: {response.text}")
        raise AIProviderError(f"AI service error (status {response.status_code}).")

    try:
        res_json = response.json()
        raw_text = res_json["choices"][0]["message"]["content"]
        return raw_text
    except Exception as exc:
        logger.error(f"Failed to extract message content from OpenAI response: {exc}")
        raise AIValidationError("Unexpected response structure from AI provider.") from exc


def get_ai_config() -> tuple[str, str, str, str]:
    """Retrieve AI configuration safely from Flask config or environment.

    Returns (api_key, provider, model, base_url).
    """
    if current_app:
        api_key = (
            current_app.config.get("GEMINI_API_KEY")
            or current_app.config.get("AI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("AI_API_KEY")
        )
        provider = current_app.config.get("AI_PROVIDER") or os.environ.get("AI_PROVIDER", "gemini")
        model = current_app.config.get("AI_MODEL") or os.environ.get("AI_MODEL", "gemini-flash-lite-latest")
        base_url = current_app.config.get("AI_BASE_URL") or os.environ.get("AI_BASE_URL")
    else:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AI_API_KEY")
        provider = os.environ.get("AI_PROVIDER", "gemini")
        model = os.environ.get("AI_MODEL", "gemini-flash-lite-latest")
        base_url = os.environ.get("AI_BASE_URL")

    # Clean provider and key
    provider = str(provider).strip().lower() if provider else "gemini"
    api_key = str(api_key).strip() if api_key else ""

    # Auto-detect provider if key has unmistakable prefix
    if api_key.startswith("AIza") or api_key.startswith("AQ."):
        provider = "gemini"
    elif api_key.startswith("sk-") and provider not in ("openai", "openrouter", "groq"):
        provider = "openai"

    return api_key, provider, str(model).strip(), (str(base_url).strip() if base_url else None)


def generate_music_recommendation(mood: str, language: str) -> dict:
    """Generate structured music recommendations for a given mood and language.

    Validates inputs, contacts the configured LLM, parses the response,
    and returns a clean, validated Python dictionary.
    """
    # 1. Validate inputs
    canonical_mood, canonical_language = validate_inputs(mood, language)

    # 2. Retrieve and validate credentials
    api_key, provider, model, base_url = get_ai_config()
    if not api_key or api_key.lower() in PLACEHOLDER_KEYS:
        logger.warning("AI recommendation requested but AI_API_KEY is not configured.")
        raise AIConfigurationError()

    # 3. Build controlled prompt
    prompt_data = build_prompt(canonical_mood, canonical_language)

    # 4. Call external LLM provider
    if provider == "gemini":
        raw_output = call_gemini_api(api_key, model, prompt_data)
    else:
        raw_output = call_openai_api(api_key, model, prompt_data, base_url=base_url)

    # 5. Parse and strictly validate returned JSON schema
    recommendation = parse_and_validate_response(
        raw_output,
        expected_mood=canonical_mood,
        expected_language=canonical_language,
    )

    return recommendation
