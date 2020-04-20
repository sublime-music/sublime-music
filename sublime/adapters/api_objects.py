"""
Defines the objects that are returned by adapter methods.
"""
import abc
from datetime import datetime, timedelta
from typing import Optional, Sequence


class Song(abc.ABC):
    id: str


class Playlist(abc.ABC):
    id: str
    name: str
    song_count: Optional[int]
    duration: Optional[timedelta]
    created: Optional[datetime]
    changed: Optional[datetime]
    comment: Optional[str]
    owner: Optional[str]
    public: Optional[bool]
    cover_art: Optional[str]


class PlaylistDetails(abc.ABC):
    id: str
    name: str
    song_count: int
    duration: timedelta
    songs: Sequence[Song]
    created: Optional[datetime]
    changed: Optional[datetime]
    comment: Optional[str]
    owner: Optional[str]
    public: Optional[bool]
    cover_art: Optional[str]
