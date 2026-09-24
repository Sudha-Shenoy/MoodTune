"""Unit and integration tests for MoodTune Module 08 Part A: User Playlists.

Tests playlist creation, view, song addition, duplicate prevention, song removal,
position normalization, ownership security isolation, cascade deletion, and
guarantees ZERO YouTube Data API calls during all playlist operations.
"""
import pytest
from unittest.mock import patch
from app import create_app
from config.config import TestingConfig
from models import db, User, Playlist, PlaylistSong
from sqlalchemy.exc import IntegrityError


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


def create_and_login_user(client, app, name="Playlist User", email="user@example.com", password="Password@123"):
    """Helper function to create a test user and log them in."""
    with app.app_context():
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client.post(
        "/login",
        data={"email": email, "password": password}
    )
    return user_id


# =========================================================================
# 1. Model & Database Constraint Tests
# =========================================================================

def test_playlist_models_and_attributes(app):
    """Verify Playlist and PlaylistSong models, fields, to_dict, and relationships."""
    with app.app_context():
        user = User(name="Alex", email="alex@example.com")
        user.set_password("Pass@1234")
        db.session.add(user)
        db.session.commit()

        playlist = Playlist(name="Chill Waves", user_id=user.id)
        db.session.add(playlist)
        db.session.commit()

        song = PlaylistSong(
            playlist_id=playlist.id,
            video_id="vid_test_123",
            title="Calm Night",
            channel_title="Lofi Girl",
            thumbnail="https://example.com/thumb.jpg",
            youtube_url="https://youtube.com/watch?v=vid_test_123",
            position=1
        )
        db.session.add(song)
        db.session.commit()

        assert playlist.song_count == 1
        p_dict = playlist.to_dict()
        assert p_dict["name"] == "Chill Waves"
        assert p_dict["song_count"] == 1
        assert len(p_dict["songs"]) == 1
        assert p_dict["songs"][0]["video_id"] == "vid_test_123"


def test_playlist_user_cascade_delete(app):
    """Verify deleting a User cascades to delete all their Playlists and PlaylistSongs."""
    with app.app_context():
        user = User(name="Sam", email="sam@example.com")
        user.set_password("Pass@1234")
        playlist = Playlist(name="To Delete", user=user)
        song = PlaylistSong(playlist=playlist, video_id="vid_cascade", title="Title", position=1)
        db.session.add(user)
        db.session.commit()

        user_id = user.id
        playlist_id = playlist.id

        # Delete user
        db.session.delete(user)
        db.session.commit()

        assert Playlist.query.filter_by(id=playlist_id).count() == 0
        assert PlaylistSong.query.filter_by(playlist_id=playlist_id).count() == 0


def test_playlist_delete_cascade_songs(app):
    """Verify deleting a Playlist cascades to delete its PlaylistSongs."""
    with app.app_context():
        user = User(name="Jordan", email="jordan@example.com")
        user.set_password("Pass@1234")
        playlist = Playlist(name="Solo Playlist", user=user)
        song = PlaylistSong(playlist=playlist, video_id="vid_song_01", title="Title", position=1)
        db.session.add(user)
        db.session.commit()

        playlist_id = playlist.id

        db.session.delete(playlist)
        db.session.commit()

        assert Playlist.query.filter_by(id=playlist_id).count() == 0
        assert PlaylistSong.query.filter_by(playlist_id=playlist_id).count() == 0


def test_playlist_duplicate_song_unique_constraint(app):
    """Verify unique constraint uq_playlist_video raises IntegrityError on duplicate."""
    with app.app_context():
        user = User(name="Taylor", email="taylor@example.com")
        user.set_password("Pass@1234")
        db.session.add(user)
        db.session.commit()

        playlist = Playlist(name="Constraint Test", user_id=user.id)
        db.session.add(playlist)
        db.session.commit()

        song1 = PlaylistSong(
            playlist_id=playlist.id,
            video_id="same_vid",
            title="Track 1",
            youtube_url="https://youtube.com/watch?v=same_vid",
            position=1
        )
        db.session.add(song1)
        db.session.commit()

        song2 = PlaylistSong(
            playlist_id=playlist.id,
            video_id="same_vid",
            title="Track 2",
            youtube_url="https://youtube.com/watch?v=same_vid",
            position=2
        )
        db.session.add(song2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# =========================================================================
# 2. Lifecycle & Route Tests
# =========================================================================

def test_get_playlists_logged_out(client):
    """Verify GET /playlists requires authentication."""
    response = client.get("/playlists")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    # AJAX request returns 401 JSON
    ajax_resp = client.get("/playlists", headers={"X-Requested-With": "XMLHttpRequest"})
    assert ajax_resp.status_code == 401
    assert "error" in ajax_resp.get_json()


def test_get_playlists_empty(client, app):
    """Verify logged-in user with no playlists receives empty list."""
    create_and_login_user(client, app)
    response = client.get("/playlists")
    assert response.status_code == 200

    ajax_resp = client.get("/playlists", headers={"X-Requested-With": "XMLHttpRequest"})
    assert ajax_resp.status_code == 200
    data = ajax_resp.get_json()
    assert data["success"] is True
    assert data["playlists"] == []


def test_create_playlist_success(client, app):
    """Verify creating a playlist returns 201 and stores in database."""
    create_and_login_user(client, app)
    response = client.post(
        "/playlists/create",
        json={"name": "Kannada Melody Hits"}
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["playlist"]["name"] == "Kannada Melody Hits"
    assert data["playlist"]["song_count"] == 0

    with app.app_context():
        assert Playlist.query.filter_by(name="Kannada Melody Hits").count() == 1


def test_create_playlist_validation(client, app):
    """Verify validation on empty, whitespace, and excessively long names."""
    create_and_login_user(client, app)

    # Empty
    r1 = client.post("/playlists/create", json={"name": ""})
    assert r1.status_code == 400
    assert "error" in r1.get_json()

    # Whitespace
    r2 = client.post("/playlists/create", json={"name": "   "})
    assert r2.status_code == 400

    # Over 100 chars
    r3 = client.post("/playlists/create", json={"name": "A" * 105})
    assert r3.status_code == 400


def test_get_playlist_detail_success(client, app):
    """Verify viewing playlist detail returns songs and metadata."""
    create_and_login_user(client, app)
    create_resp = client.post("/playlists/create", json={"name": "Night Vibes"})
    p_id = create_resp.get_json()["playlist"]["id"]

    # Add a song
    client.post(
        f"/playlists/{p_id}/add",
        json={
            "video_id": "vid_abc123",
            "title": "Starry Sky",
            "channel_title": "Ambient Sound",
            "thumbnail": "https://example.com/thumb.jpg",
            "youtube_url": "https://youtube.com/watch?v=vid_abc123"
        }
    )

    response = client.get(f"/playlists/{p_id}")
    assert response.status_code == 200
    assert b"Night Vibes" in response.data

    ajax_resp = client.get(f"/playlists/{p_id}", headers={"X-Requested-With": "XMLHttpRequest"})
    assert ajax_resp.status_code == 200
    data = ajax_resp.get_json()
    assert data["success"] is True
    assert len(data["playlist"]["songs"]) == 1
    assert data["playlist"]["songs"][0]["title"] == "Starry Sky"


def test_playlist_ownership_isolation_returns_404(client, app):
    """Verify User B receives 404 when trying to view User A's playlist."""
    # User A creates playlist
    create_and_login_user(client, app, name="User A", email="usera@example.com")
    create_resp = client.post("/playlists/create", json={"name": "User A Private"})
    playlist_id = create_resp.get_json()["playlist"]["id"]

    # Logout
    client.get("/logout")

    # User B logs in
    create_and_login_user(client, app, name="User B", email="userb@example.com")

    # User B tries to view User A's playlist
    view_resp = client.get(f"/playlists/{playlist_id}")
    assert view_resp.status_code == 404

    # User B tries to add song to User A's playlist
    add_resp = client.post(
        f"/playlists/{playlist_id}/add",
        json={"video_id": "intruder_vid", "title": "Hacked"}
    )
    assert add_resp.status_code == 404

    # User B tries to delete User A's playlist
    del_resp = client.post(f"/playlists/{playlist_id}/delete")
    assert del_resp.status_code == 404


def test_add_song_to_playlist_success(client, app):
    """Verify adding song persists all fields and sets position."""
    create_and_login_user(client, app)
    create_resp = client.post("/playlists/create", json={"name": "Study Mix"})
    p_id = create_resp.get_json()["playlist"]["id"]

    add_resp = client.post(
        f"/playlists/{p_id}/add",
        json={
            "video_id": "vid_lofi_01",
            "title": "Study Beats",
            "channel_title": "Lofi Chill",
            "thumbnail": "https://img.youtube.com/vi/vid_lofi_01/0.jpg",
            "youtube_url": "https://www.youtube.com/watch?v=vid_lofi_01"
        }
    )
    assert add_resp.status_code == 201
    data = add_resp.get_json()
    assert data["success"] is True
    assert data["song"]["position"] == 1
    assert data["song"]["video_id"] == "vid_lofi_01"


def test_add_duplicate_song_returns_409(client, app):
    """Verify duplicate song in same playlist is rejected with 409 and clean error message."""
    create_and_login_user(client, app)
    create_resp = client.post("/playlists/create", json={"name": "No Dups"})
    p_id = create_resp.get_json()["playlist"]["id"]

    song_payload = {
        "video_id": "vid_repeat",
        "title": "Once Only",
        "channel_title": "Artist",
        "youtube_url": "https://youtube.com/watch?v=vid_repeat"
    }

    r1 = client.post(f"/playlists/{p_id}/add", json=song_payload)
    assert r1.status_code == 201

    r2 = client.post(f"/playlists/{p_id}/add", json=song_payload)
    assert r2.status_code == 409
    data = r2.get_json()
    assert "already in this playlist" in data["error"].lower()


def test_remove_song_normalizes_positions(client, app):
    """Verify removing a song re-numbers remaining songs sequentially."""
    create_and_login_user(client, app)
    create_resp = client.post("/playlists/create", json={"name": "Sequence Test"})
    p_id = create_resp.get_json()["playlist"]["id"]

    # Add 3 songs
    for i in (1, 2, 3):
        client.post(
            f"/playlists/{p_id}/add",
            json={"video_id": f"vid_seq_{i}", "title": f"Song {i}"}
        )

    # Get song 2's id
    detail_resp = client.get(f"/playlists/{p_id}", headers={"X-Requested-With": "XMLHttpRequest"})
    songs = detail_resp.get_json()["playlist"]["songs"]
    assert len(songs) == 3
    song_2_id = songs[1]["id"]

    # Remove song 2 via AJAX
    rem_resp = client.post(
        f"/playlists/{p_id}/remove/{song_2_id}",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert rem_resp.status_code == 200

    # Verify positions of remaining songs are 1 and 2
    detail_resp2 = client.get(f"/playlists/{p_id}", headers={"X-Requested-With": "XMLHttpRequest"})
    remaining = detail_resp2.get_json()["playlist"]["songs"]
    assert len(remaining) == 2
    assert remaining[0]["video_id"] == "vid_seq_1"
    assert remaining[0]["position"] == 1
    assert remaining[1]["video_id"] == "vid_seq_3"
    assert remaining[1]["position"] == 2


def test_delete_playlist_success(client, app):
    """Verify deleting a playlist removes it from database."""
    create_and_login_user(client, app)
    create_resp = client.post("/playlists/create", json={"name": "Bye Playlist"})
    p_id = create_resp.get_json()["playlist"]["id"]

    del_resp = client.post(
        f"/playlists/{p_id}/delete",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert del_resp.status_code == 200

    with app.app_context():
        assert db.session.get(Playlist, p_id) is None


# =========================================================================
# 3. Quota Safety: Zero YouTube API Calls Assertion
# =========================================================================

def test_zero_youtube_api_calls_during_playlist_operations(client, app):
    """Verify ZERO YouTube Data API requests are made during all playlist operations."""
    create_and_login_user(client, app)

    with patch("services.youtube_service.search_youtube_query") as mock_search, \
         patch("services.youtube_service.search_music_for_recommendation") as mock_rec:

        # 1. Create playlist
        c_resp = client.post("/playlists/create", json={"name": "Zero Quota Mix"})
        p_id = c_resp.get_json()["playlist"]["id"]

        # 2. Add song
        client.post(
            f"/playlists/{p_id}/add",
            json={
                "video_id": "vid_no_quota",
                "title": "Saved Track",
                "channel_title": "Channel",
                "thumbnail": "https://img.com/thumb.jpg",
                "youtube_url": "https://youtube.com/watch?v=vid_no_quota"
            }
        )

        # 3. View playlist
        client.get(f"/playlists/{p_id}")

        # 4. List playlists
        client.get("/playlists")

        # 5. Remove song
        detail = client.get(f"/playlists/{p_id}", headers={"X-Requested-With": "XMLHttpRequest"})
        song_id = detail.get_json()["playlist"]["songs"][0]["id"]
        client.post(f"/playlists/{p_id}/remove/{song_id}", headers={"X-Requested-With": "XMLHttpRequest"})

        # 6. Delete playlist
        client.post(f"/playlists/{p_id}/delete", headers={"X-Requested-With": "XMLHttpRequest"})

        # Assert YouTube API was NEVER called
        assert mock_search.call_count == 0, "search_youtube_query() should never be called for playlists"
        assert mock_rec.call_count == 0, "search_music_for_recommendation() should never be called for playlists"
