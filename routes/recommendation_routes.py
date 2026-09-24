"""Recommendation routes for MoodTune.

Handles AI music recommendation generation requests for authenticated users.
"""
import logging
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for, flash, render_template
from services.ai_service import (
    generate_music_recommendation,
    validate_inputs,
    AIServiceError,
    AIConfigurationError,
    AIValidationError,
)
from services.youtube_service import (
    search_youtube_query,
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


@recommendation_bp.route("/search-music", methods=["GET", "POST"])
@recommendation_bp.route("/discover-songs", methods=["GET", "POST"])
def search_music():
    """Discover real YouTube music tracks via manual keyword search OR AI recommendation."""
    # Check for manual search query (Part B: Manual YouTube Music Search)
    manual_query = None
    if "q" in request.args:
        manual_query = request.args.get("q")
    elif "query" in request.args:
        manual_query = request.args.get("query")
    elif request.method == "POST":
        if request.is_json:
            body = request.get_json(silent=True) or {}
            if "q" in body:
                manual_query = body.get("q")
            elif "query" in body:
                manual_query = body.get("query")
        elif request.form:
            if "q" in request.form:
                manual_query = request.form.get("q")
            elif "query" in request.form:
                manual_query = request.form.get("query")

    if manual_query is not None:
        # PART B: Manual YouTube Music Search (independent of Gemini AI)
        cleaned_query = manual_query.strip() if isinstance(manual_query, str) else ""

        if not cleaned_query:
            err_msg = "Please enter a song, artist, or music keyword to search."
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": err_msg}), 400
            flash(err_msg, "error")
            return redirect(url_for("main.index"))

        if len(cleaned_query) > 100:
            err_msg = "Search query is too long. Please keep it under 100 characters."
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": err_msg}), 400
            flash(err_msg, "error")
            return redirect(url_for("main.index"))

        try:
            # Single search.list request with videoEmbeddable=true and controlled max_results=12
            raw_videos = search_youtube_query(query=cleaned_query, max_results=12)
        except YouTubeQuotaError as err:
            logger.error(f"YouTube quota limit exceeded during manual search: {err}")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": err.user_message}), 503
            flash(err.user_message, "error")
            return redirect(url_for("main.index"))
        except YouTubeConfigurationError as err:
            logger.warning(f"YouTube configuration error during manual search: {err}")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": err.user_message}), 503
            flash(err.user_message, "error")
            return redirect(url_for("main.index"))
        except YouTubeServiceError as err:
            logger.error(f"YouTube service error during manual search: {err}")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": err.user_message}), 500
            flash(err.user_message, "error")
            return redirect(url_for("main.index"))
        except Exception as exc:
            logger.exception(f"Unexpected error during manual YouTube search: {exc}")
            user_msg = "MoodTune couldn't complete your search right now. Please try again."
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": user_msg}), 500
            flash(user_msg, "error")
            return redirect(url_for("main.index"))

        # Deduplicate results by video_id
        seen_ids = set()
        deduped_videos = []
        for v in raw_videos:
            vid = v.get("video_id")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                deduped_videos.append(v)

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": True,
                "manual_search": True,
                "query": cleaned_query,
                "count": len(deduped_videos),
                "videos": deduped_videos,
            }), 200

        return render_template(
            "index.html",
            youtube_results=deduped_videos,
            search_query=cleaned_query,
        )

    # PART A / Existing: AI recommendation discovery
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
        target_count = current_app.config.get("YOUTUBE_TARGET_RESULTS", 18)
        videos = search_music_for_recommendation(search_queries, max_total_results=target_count)
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
            "mood_quotes": ai_recommendation.get("mood_quotes", []),
        }), 200

    return redirect(url_for("main.index"))

