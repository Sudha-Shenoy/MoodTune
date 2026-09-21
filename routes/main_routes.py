"""Main application routes and preference endpoints."""
from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for

main_bp = Blueprint("main", __name__)

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


@main_bp.route("/")
def index():
    """Render the homepage with current session preferences and AI recommendation."""
    return render_template(
        "index.html",
        selected_mood=session.get("selected_mood"),
        selected_language=session.get("selected_language"),
        ai_recommendation=session.get("ai_recommendation"),
        youtube_results=session.get("youtube_results"),
    )


@main_bp.route("/preferences", methods=["GET", "POST"])
def preferences():
    """Get or update user mood and language preferences in session."""
    # Handle GET: return current preferences
    if request.method == "GET":
        return jsonify({
            "authenticated": bool(session.get("user_id")),
            "selected_mood": session.get("selected_mood"),
            "selected_language": session.get("selected_language"),
        }), 200

    # Handle POST: require authenticated session
    if not session.get("user_id"):
        # For JSON / XHR requests, return 401 Unauthorized
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "error": "Authentication required to personalize music.",
                "login_url": url_for("auth.login"),
            }), 401
        # For standard browser submissions, redirect to login
        return redirect(url_for("auth.login"))

    # Extract data from JSON or form
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    raw_mood = data.get("mood")
    raw_language = data.get("language")

    # Validate and update mood if provided
    if raw_mood is not None:
        clean_mood = str(raw_mood).strip().lower()
        if clean_mood not in MOOD_LOOKUP:
            return jsonify({"error": f"Invalid mood '{raw_mood}'. Must be one of: {', '.join(ALLOWED_MOODS)}"}), 400
        session["selected_mood"] = MOOD_LOOKUP[clean_mood]

    # Validate and update language if provided
    if raw_language is not None:
        clean_lang = str(raw_language).strip().lower()
        if clean_lang not in LANG_LOOKUP:
            return jsonify({"error": f"Invalid language '{raw_language}'. Must be one of: {', '.join(ALLOWED_LANGUAGES)}"}), 400
        session["selected_language"] = LANG_LOOKUP[clean_lang]

    return jsonify({
        "success": True,
        "selected_mood": session.get("selected_mood"),
        "selected_language": session.get("selected_language"),
    }), 200
