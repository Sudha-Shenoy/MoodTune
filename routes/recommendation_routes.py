"""Recommendation routes for MoodTune.

Handles AI music recommendation generation requests for authenticated users.
"""
import logging
from flask import Blueprint, jsonify, redirect, request, session, url_for, flash
from services.ai_service import (
    generate_music_recommendation,
    validate_inputs,
    AIServiceError,
    AIConfigurationError,
    AIValidationError,
)
from services.youtube_service import (
    search_music_for_recommendation,
    YouTubeServiceError,
    YouTubeConfigurationError,
    YouTubeQuotaError,
    YouTubeAPIError,
    YouTubeNetworkError,
)

logger = logging.getLogger(__name__)

recommendation_bp = Blueprint("recommendation", __name__)


@recommendation_bp.route("/generate-recommendation", methods=["POST"])
def generate_recommendation():
    """Generate structured AI music recommendations based on user session preferences."""
    # 1. Require authenticated session
    if not session.get("user_id"):
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "error": "Authentication required to generate recommendations.",
                "login_url": url_for("auth.login"),
            }), 401
        flash("Please log in to generate recommendations.", "error")
        return redirect(url_for("auth.login"))

    # 2. Retrieve preferences from authenticated session
    mood = session.get("selected_mood")
    language = session.get("selected_language")

    if not mood or not language:
        msg = "Please select a mood and language first."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 400
        flash(msg, "info")
        return redirect(url_for("main.index"))

    # 3. Validate against allowed whitelists
    try:
        canonical_mood, canonical_language = validate_inputs(mood, language)
    except AIValidationError as err:
        msg = str(err.user_message)
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 400
        flash(msg, "error")
        return redirect(url_for("main.index"))

    # 4. Invoke AI recommendation service
    try:
        recommendation = generate_music_recommendation(canonical_mood, canonical_language)
    except AIConfigurationError as err:
        logger.warning(f"AI configuration error: {err}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err.user_message}), 503
        flash(err.user_message, "error")
        return redirect(url_for("main.index"))
    except AIServiceError as err:
        logger.error(f"AI service error during recommendation generation: {err}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err.user_message}), 500
        flash(err.user_message, "error")
        return redirect(url_for("main.index"))
    except Exception as exc:
        logger.exception(f"Unexpected error during recommendation generation: {exc}")
        user_msg = "Sorry, MoodTune couldn't create your recommendation right now. Please try again."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": user_msg}), 500
        flash(user_msg, "error")
        return redirect(url_for("main.index"))

    # 5. Persist the recommendation in session
    session["ai_recommendation"] = recommendation
    session.modified = True

    # 6. Return response
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "recommendation": recommendation,
        }), 200

    return redirect(url_for("main.index"))


@recommendation_bp.route("/search-music", methods=["POST"])
@recommendation_bp.route("/discover-songs", methods=["POST"])
def search_music():
    """Discover real YouTube music tracks using AI recommendation search queries."""
    # 1. Require authenticated session
    if not session.get("user_id"):
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "error": "Authentication required to discover music.",
                "login_url": url_for("auth.login"),
            }), 401
        flash("Please log in to discover music.", "error")
        return redirect(url_for("auth.login"))

    # 2. Retrieve AI recommendation from session
    ai_recommendation = session.get("ai_recommendation")
    if not ai_recommendation or not isinstance(ai_recommendation, dict):
        msg = "Please generate an AI vibe first."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 400
        flash(msg, "info")
        return redirect(url_for("main.index"))

    search_queries = ai_recommendation.get("search_queries")
    if not search_queries or not isinstance(search_queries, list):
        msg = "No search queries available in your recommendation. Please regenerate your vibe."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 400
        flash(msg, "info")
        return redirect(url_for("main.index"))

    # 3. Call YouTube service with controlled quota limits
    try:
        videos = search_music_for_recommendation(search_queries, max_total_results=6)
    except YouTubeQuotaError as err:
        logger.error(f"YouTube quota limit exceeded: {err}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err.user_message}), 503
        flash(err.user_message, "error")
        return redirect(url_for("main.index"))
    except YouTubeConfigurationError as err:
        logger.warning(f"YouTube configuration error: {err}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err.user_message}), 503
        flash(err.user_message, "error")
        return redirect(url_for("main.index"))
    except YouTubeServiceError as err:
        logger.error(f"YouTube service error during music search: {err}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err.user_message}), 500
        flash(err.user_message, "error")
        return redirect(url_for("main.index"))
    except Exception as exc:
        logger.exception(f"Unexpected error during YouTube search: {exc}")
        user_msg = "MoodTune couldn't load music right now. Please try again."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": user_msg}), 500
        flash(user_msg, "error")
        return redirect(url_for("main.index"))

    # 4. Store compact metadata in session cookie (keeping cookie payload tiny)
    session["youtube_results"] = videos
    session.modified = True

    # 5. Return JSON directly to frontend
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "count": len(videos),
            "videos": videos,
        }), 200

    return redirect(url_for("main.index"))

