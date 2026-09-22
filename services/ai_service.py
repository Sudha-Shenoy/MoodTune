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
- Provide 8 to 12 short, evocative vibe quotes (1 sentence each) that capture this mood and language.

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
  "description": "1-2 sentence description of the vibe.",
  "mood_quotes": [
    "Short vibe quote 1.",
    "Short vibe quote 2.",
    "Short vibe quote 3.",
    "Short vibe quote 4."
  ]
}}

Rules for JSON:
- 'mood' must equal "{mood}"
- 'language' must equal "{language}"
- 'music_style' must be a JSON array containing between 3 and 6 short descriptor strings.
- 'search_queries' must be a JSON array containing between 3 and 5 search query strings tailored to find music in this language and mood.
- 'description' must be a non-empty string of 1 to 2 sentences.
- 'mood_quotes' should be a JSON array of 6 to 12 short evocative vibe captions.
- Do NOT wrap in markdown or backticks (return raw JSON only)."""

    return {
        "system": system_instruction,
        "user": user_instruction,
        "full_text": f"{system_instruction}\n\n{user_instruction}",
    }


FALLBACK_MOOD_QUOTES = {
    "Sad": [
        "Some melodies understand the silence better than words.",
        "Let the quiet strings echo the thoughts you cannot speak.",
        "In the stillness of sound, the heart finds its honest voice.",
        "A tender melody for the solitary hours of reflection.",
        "Gentle chords that accompany the rain within.",
        "Memories drift like gentle notes on an evening breeze.",
        "Music is the quiet companion of a searching soul.",
        "When words fall short, the harmony holds the space.",
        "A soft cadence to soothe a heavy heart.",
        "Echoes of longing woven into timeless acoustic notes.",
    ],
    "Happy": [
        "Bright rhythms that instantly lift your spirit to the sky.",
        "Pure sonic sunshine for a radiant state of mind.",
        "Let the joy in every chord light up your day.",
        "An infectious tempo of pure positive vibrations.",
        "Celebrate the simple happiness of right now.",
        "Golden melodies that make your soul smile.",
        "Dance to the bright beat of an uplifting moment.",
        "Every rhythm brings a fresh spark of optimism.",
        "A burst of musical sunlight through every melody.",
        "Joyful chords for an unforgettable, cheerful day.",
    ],
    "Chill": [
        "Slow down. Let the music carry the weight of the moment.",
        "Unwind and let the smooth frequencies settle in.",
        "Soft acoustics for an unhurried, peaceful state of mind.",
        "Breathe in peace, exhale tension to the tempo.",
        "Mellow beats for quiet corners and twilight thoughts.",
        "Let the tempo drift gently like clouds across the sky.",
        "A calming pulse to ease your thoughts into tranquility.",
        "Gentle soundscapes for resting your mind.",
        "Subtle chords designed for late night serenity.",
        "Peaceful vibrations that turn the noise into calm.",
    ],
    "Romantic": [
        "Some feelings sound sweeter when they become a melody.",
        "A heartfelt cadence where every lyric feels intimate.",
        "Warm acoustic melodies that speak directly to the heart.",
        "Two souls dancing in harmony with the rhythm.",
        "A tender frequency designed for romantic evenings.",
        "Let every chord remind you of a beautiful memory.",
        "Soft harmonies that whisper what love cannot write.",
        "A soundtrack for shared glances and gentle warmth.",
        "Love is a melody that echoes long after the music ends.",
        "Warm strings and sweet cadences woven with devotion.",
    ],
    "Relaxed": [
        "Peaceful ambient tones that wash away the day's noise.",
        "Serenity captured in delicate musical frequencies.",
        "Calm waves of soothing acoustic harmony.",
        "Let the soothing rhythm steady your breathing.",
        "A gentle sanctuary crafted out of quiet notes.",
        "Rest your mind within the warmth of smooth melodies.",
        "Stillness made audible through peaceful soundscapes.",
        "Unclutter your day with soft, tranquil vibrations.",
        "A mindful interlude of serene relaxation.",
        "Gentle acoustic warmth that cradles the evening.",
    ],
    "Energetic": [
        "Feel the electric pulse and let the bass fuel your fire.",
        "High-octane soundscapes built for unstoppable drive.",
        "Turn up the volume and charge your spirit with power.",
        "Unleash pure momentum with every rising beat.",
        "A rush of adrenaline surging through every track.",
        "Feel the sonic velocity pushing you forward.",
        "Electric frequencies designed to ignite your energy.",
        "Explosive rhythms that demand you move.",
        "High voltage tempo for peak performance and thrill.",
        "Unstoppable energy woven into heavy basslines.",
    ],
    "Motivated": [
        "Every beat is another step forward towards your summit.",
        "Rise above the doubts with conviction in every note.",
        "Determination set to an unstoppable, driving rhythm.",
        "Turn ambition into action with powerful musical cues.",
        "Focus your mind and conquer the challenge ahead.",
        "A triumphant anthem for those who refuse to stop.",
        "Strength and grit distilled into driving percussion.",
        "Let the melody remind you of the strength you carry.",
        "Unwavering focus powered by an energetic cadence.",
        "Your journey, your triumph, scored by epic sound.",
    ],
    "Party": [
        "Celebrate the night with beats that never stop moving.",
        "Electrifying rhythms made for losing track of time.",
        "Turn the room into a festival of pure sound.",
        "Feel the bass vibrate through the entire dance floor.",
        "Unfiltered celebration captured in high-tempo grooves.",
        "Drop the beat and let the good times take over.",
        "Loud, proud, and unapologetically festive music.",
        "Non-stop dance energy from the first note to the last.",
        "A celebration of rhythm, friends, and late night memories.",
        "Electric party vibes that keep the night alive.",
    ],
}


def get_fallback_mood_quotes(mood: str, language: str) -> list[str]:
    """Provide a rich, curated list of mood quotes tailored to mood and language."""
    base_quotes = FALLBACK_MOOD_QUOTES.get(mood) or FALLBACK_MOOD_QUOTES["Chill"]
    return [f"{q}" for q in base_quotes]


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

    # Validate or fallback mood_quotes
    raw_quotes = data.get("mood_quotes")
    clean_quotes = []
    if isinstance(raw_quotes, list):
        for q in raw_quotes:
            if isinstance(q, str) and q.strip():
                clean_quotes.append(q.strip())

    if len(clean_quotes) < 4:
        clean_quotes = get_fallback_mood_quotes(expected_mood, expected_language)

    return {
        "mood": expected_mood,
        "language": expected_language,
        "music_style": clean_styles,
        "search_queries": clean_queries,
        "description": desc.strip(),
        "mood_quotes": clean_quotes,
    }


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]


def call_gemini_api(api_key: str, model: str, prompt_data: dict, timeout: int = 15) -> str:
    """Invoke Google Gemini generateContent using official google-genai SDK with REST fallback and multi-model failover."""
    # Build candidate model list prioritizing user/configured model
    candidate_models = [model]
    for fb_model in GEMINI_FALLBACK_MODELS:
        if fb_model not in candidate_models:
            candidate_models.append(fb_model)

    last_status = None
    last_error_text = None

    for current_model in candidate_models:
        # 1. Attempt generation using the official google-genai SDK
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=current_model,
                contents=prompt_data["full_text"],
            )
            if response and response.text:
                return response.text
        except Exception as sdk_err:
            logger.warning(
                f"google-genai SDK call error for model '{current_model}' ({sdk_err}), trying REST fallback."
            )

        # 2. Fallback to direct REST API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
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

        if response.status_code == 200:
            try:
                res_json = response.json()
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                return raw_text
            except Exception as exc:
                logger.error(f"Failed to extract candidate text from Gemini response: {exc}")
                raise AIValidationError("Unexpected response structure from AI provider.") from exc

        if response.status_code in (401, 403):
            logger.error(f"Gemini API authentication failed ({response.status_code}).")
            raise AIProviderError("AI authentication failed. Check API key configuration.")
        elif response.status_code == 400:
            logger.error(f"Gemini API 400 Bad Request for model '{current_model}': {response.text}")
            raise AIProviderError("Invalid request to AI service.")
        elif response.status_code in (404, 429, 503):
            logger.warning(
                f"Gemini model '{current_model}' unavailable (status {response.status_code}). Trying next fallback model if available..."
            )
            last_status = response.status_code
            last_error_text = response.text
            continue
        elif not response.ok:
            logger.error(f"Gemini API error {response.status_code} for model '{current_model}': {response.text}")
            last_status = response.status_code
            last_error_text = response.text
            continue

    # If all models in the candidate list failed
    if last_status == 503:
        raise AIProviderError("AI service is currently experiencing high demand. Please try again shortly.")
    elif last_status == 429:
        raise AIProviderError("AI service rate limit reached. Please wait a moment.")
    elif last_status == 404:
        raise AIProviderError(f"Configured Gemini model '{model}' was not found or is unavailable.")
    elif last_status:
        raise AIProviderError(f"AI service error (status {last_status}).")

    raise AIProviderError("Failed to obtain recommendation from AI service.")


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
        model = current_app.config.get("AI_MODEL") or os.environ.get("AI_MODEL", DEFAULT_GEMINI_MODEL)
        base_url = current_app.config.get("AI_BASE_URL") or os.environ.get("AI_BASE_URL")
    else:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AI_API_KEY")
        provider = os.environ.get("AI_PROVIDER", "gemini")
        model = os.environ.get("AI_MODEL", DEFAULT_GEMINI_MODEL)
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
