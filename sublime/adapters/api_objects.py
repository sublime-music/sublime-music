"""
Defines the objects that are returned by adapter methods.
"""
import abc
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Sequence


class MediaType(Enum):
    MUSIC = 'music'
    PODCAST = 'podcast'
    AUDIOBOOK = 'audiobook'
    VIDEO = 'video'


class Song(abc.ABC):
    id: str
    title: str
    parent: str
    album: str
    artist: str
    track: Optional[int]
    year: Optional[int]
    genre: Optional[str]
    cover_art: Optional[str]
    size: Optional[int]
    content_type: Optional[str]
    suffix: Optional[str]
    transcoded_content_type: Optional[str]
    transcoded_suffix: Optional[str]
    duration: Optional[timedelta]
    bit_rate: Optional[int]
    path: Optional[str]
    is_video: Optional[bool]
    user_rating: Optional[int]
    average_rating: Optional[float]
    play_count: Optional[int]
    disc_number: Optional[int]
    created: Optional[datetime]
    starred: Optional[datetime]
    album_id: Optional[str]
    artist_id: Optional[str]
    type: Optional[MediaType]
    # TODO trim down, make another data structure for directory?


class Playlist(abc.ABC):
    # TODO trim down
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
    # TODO trim down
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
