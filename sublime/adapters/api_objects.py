"""
Defines the objects that are returned by adapter methods.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass(frozen=True)
class Song:
    id: str


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    song_count: Optional[int] = None
    duration: Optional[timedelta] = None
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    cover_art: Optional[str] = None


@dataclass(frozen=True)
class PlaylistDetails:
    id: str
    name: str
    song_count: int
    duration: timedelta
    songs: List[Song]
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    cover_art: Optional[str] = None
