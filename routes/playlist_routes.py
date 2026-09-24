"""Playlist routes for MoodTune (Module 08).

Provides full lifecycle management for user-specific playlists:
listing, creation, viewing, song addition, song removal, and playlist deletion.
Enforces strict server-side ownership verification on all operations.
Zero YouTube API quota consumption.
"""
import logging
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    redirect,
    url_for,
    flash,
)
from models import db, Playlist, PlaylistSong

logger = logging.getLogger(__name__)

playlist_bp = Blueprint("playlist", __name__, url_prefix="/playlists")


@playlist_bp.before_request
def require_login():
    """Ensure user is authenticated for all playlist endpoints."""
    if not session.get("user_id"):
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "error": "Authentication required. Please log in to manage playlists.",
                "login_url": url_for("auth.login"),
            }), 401
        flash("Please log in to manage playlists.", "info")
        return redirect(url_for("auth.login"))


@playlist_bp.route("", methods=["GET"])
def list_playlists():
    """Display or return all playlists belonging to the logged-in user."""
    user_id = session.get("user_id")
    user_playlists = (
        Playlist.query.filter_by(user_id=user_id)
        .order_by(Playlist.created_at.desc())
        .all()
    )

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "playlists": [p.to_dict() for p in user_playlists],
        }), 200

    return render_template(
        "playlists.html",
        playlists=user_playlists,
    )


@playlist_bp.route("/create", methods=["POST"])
def create_playlist():
    """Create a new playlist for the logged-in user."""
    user_id = session.get("user_id")

    if request.is_json:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
    else:
        name = request.form.get("name", "")

    # Clean and validate name
    cleaned_name = name.strip() if isinstance(name, str) else ""

    if not cleaned_name:
        err_msg = "Playlist name cannot be empty."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err_msg}), 400
        flash(err_msg, "error")
        return redirect(url_for("playlist.list_playlists")), 400

    if len(cleaned_name) > 100:
        err_msg = "Playlist name must be 100 characters or fewer."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": err_msg}), 400
        flash(err_msg, "error")
        return redirect(url_for("playlist.list_playlists")), 400

    new_playlist = Playlist(user_id=user_id, name=cleaned_name)
    db.session.add(new_playlist)
    db.session.commit()

    logger.info("Created playlist id=%d %r for user_id=%d", new_playlist.id, cleaned_name, user_id)

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "message": f'Playlist "{cleaned_name}" created successfully.',
            "playlist": new_playlist.to_dict(),
        }), 201

    flash(f'Playlist "{cleaned_name}" created!', "success")
    return redirect(url_for("playlist.get_playlist", playlist_id=new_playlist.id))


@playlist_bp.route("/<int:playlist_id>", methods=["GET"])
def get_playlist(playlist_id: int):
    """View details and songs of a specific playlist owned by current user."""
    user_id = session.get("user_id")
    # Strict ownership check: query filters by both id and current user's id
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user_id).first()

    if not playlist:
        logger.warning(
            "Access denied or playlist not found: playlist_id=%d, requested_by user_id=%s",
            playlist_id,
            user_id,
        )
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Playlist not found."}), 404
        flash("Playlist not found.", "error")
        return redirect(url_for("playlist.list_playlists")), 404

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "playlist": playlist.to_dict(),
        }), 200

    return render_template(
        "playlist_detail.html",
        playlist=playlist,
        songs=playlist.songs,
    )


@playlist_bp.route("/<int:playlist_id>/add", methods=["POST"])
def add_song(playlist_id: int):
    """Add a song to a playlist owned by current user (zero YouTube API calls)."""
    user_id = session.get("user_id")
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user_id).first()

    if not playlist:
        return jsonify({"error": "Playlist not found."}), 404

    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    video_id = (data.get("video_id") or "").strip()
    title = (data.get("title") or "").strip()
    channel_title = (data.get("channel_title") or "").strip()
    thumbnail = (data.get("thumbnail") or "").strip()
    youtube_url = (data.get("youtube_url") or "").strip()

    if not video_id:
        return jsonify({"error": "Video ID is required."}), 400
    if not title:
        return jsonify({"error": "Song title is required."}), 400

    if not youtube_url:
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # Check for duplicate in the same playlist
    existing = PlaylistSong.query.filter_by(
        playlist_id=playlist.id,
        video_id=video_id
    ).first()

    if existing:
        return jsonify({
            "error": "This song is already in this playlist.",
            "already_exists": True,
        }), 409

    # Determine next position
    max_position = (
        db.session.query(db.func.max(PlaylistSong.position))
        .filter_by(playlist_id=playlist.id)
        .scalar()
        or 0
    )
    new_position = max_position + 1

    playlist_song = PlaylistSong(
        playlist_id=playlist.id,
        video_id=video_id,
        title=title,
        channel_title=channel_title,
        thumbnail=thumbnail,
        youtube_url=youtube_url,
        position=new_position,
    )

    db.session.add(playlist_song)
    db.session.commit()

    logger.info(
        "Added song %r (video_id=%s) to playlist id=%d at position %d",
        title,
        video_id,
        playlist.id,
        new_position,
    )

    return jsonify({
        "success": True,
        "message": f'Added "{title}" to playlist "{playlist.name}".',
        "song": playlist_song.to_dict(),
        "song_count": playlist.song_count,
    }), 201


@playlist_bp.route("/<int:playlist_id>/remove/<int:song_id>", methods=["POST"])
def remove_song(playlist_id: int, song_id: int):
    """Remove a song from a playlist owned by current user."""
    user_id = session.get("user_id")
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user_id).first()

    if not playlist:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Playlist not found."}), 404
        flash("Playlist not found.", "error")
        return redirect(url_for("playlist.list_playlists")), 404

    song = PlaylistSong.query.filter_by(id=song_id, playlist_id=playlist.id).first()
    if not song:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Song not found in playlist."}), 404
        flash("Song not found in playlist.", "error")
        return redirect(url_for("playlist.get_playlist", playlist_id=playlist.id)), 404

    song_title = song.title
    db.session.delete(song)
    db.session.commit()

    # Normalize remaining positions
    remaining = (
        PlaylistSong.query.filter_by(playlist_id=playlist.id)
        .order_by(PlaylistSong.position)
        .all()
    )
    for idx, s in enumerate(remaining, start=1):
        s.position = idx
    db.session.commit()

    logger.info("Removed song id=%d %r from playlist id=%d", song_id, song_title, playlist.id)

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "message": f'Removed "{song_title}" from playlist.',
            "song_count": playlist.song_count,
        }), 200

    flash(f'Removed "{song_title}" from playlist.', "success")
    return redirect(url_for("playlist.get_playlist", playlist_id=playlist.id))


@playlist_bp.route("/<int:playlist_id>/delete", methods=["POST"])
def delete_playlist(playlist_id: int):
    """Delete an entire playlist owned by current user (cascades to all songs)."""
    user_id = session.get("user_id")
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user_id).first()

    if not playlist:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Playlist not found."}), 404
        flash("Playlist not found.", "error")
        return redirect(url_for("playlist.list_playlists")), 404

    playlist_name = playlist.name
    db.session.delete(playlist)
    db.session.commit()

    logger.info("Deleted playlist id=%d %r for user_id=%d", playlist_id, playlist_name, user_id)

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "message": f'Playlist "{playlist_name}" deleted.',
        }), 200

    flash(f'Playlist "{playlist_name}" deleted.', "info")
    return redirect(url_for("playlist.list_playlists"))
