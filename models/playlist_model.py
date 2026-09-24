"""Playlist and PlaylistSong models for MoodTune (Module 08)."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from . import db


class Playlist(db.Model):
    """User-created playlist database model."""

    __tablename__ = "playlists"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to ordered PlaylistSongs
    songs = db.relationship(
        "PlaylistSong",
        backref="playlist",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="PlaylistSong.position"
    )

    @property
    def song_count(self) -> int:
        """Return the number of songs in this playlist."""
        return len(self.songs)

    def to_dict(self) -> Dict[str, Any]:
        """Compact dictionary representation of the playlist."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "song_count": self.song_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "songs": [song.to_dict() for song in self.songs]
        }

    def __repr__(self) -> str:
        return f"<Playlist {self.id}: {self.name!r} (user_id={self.user_id})>"


class PlaylistSong(db.Model):
    """Individual song saved inside a user playlist."""

    __tablename__ = "playlist_songs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    playlist_id = db.Column(
        db.Integer,
        db.ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    video_id = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    channel_title = db.Column(db.String(255), nullable=True, default="")
    thumbnail = db.Column(db.String(512), nullable=True, default="")
    youtube_url = db.Column(db.String(512), nullable=True, default="")
    position = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Unique constraint: Prevent duplicate video_id within the SAME playlist
    __table_args__ = (
        db.UniqueConstraint("playlist_id", "video_id", name="uq_playlist_video"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return song format strictly compatible with Module 07 player queue."""
        return {
            "id": self.id,
            "playlist_id": self.playlist_id,
            "video_id": self.video_id,
            "title": self.title,
            "channel_title": self.channel_title or "YouTube",
            "thumbnail": self.thumbnail or f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg",
            "youtube_url": self.youtube_url or f"https://www.youtube.com/watch?v={self.video_id}",
            "position": self.position,
            "added_at": self.added_at.isoformat() if self.added_at else None
        }

    def __repr__(self) -> str:
        return f"<PlaylistSong {self.id}: {self.title!r} (video_id={self.video_id}) in Playlist {self.playlist_id}>"
