"""Models package for MoodTune."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user_model import User
from .playlist_model import Playlist, PlaylistSong

__all__ = ["db", "User", "Playlist", "PlaylistSong"]
