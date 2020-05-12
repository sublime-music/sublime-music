"""
Defines the objects that are returned by adapter methods.
"""
import abc
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Sequence


class MediaType(Enum):
    MUSIC = "music"
    PODCAST = "podcast"
    AUDIOBOOK = "audiobook"
    VIDEO = "video"


class Genre(abc.ABC):
    name: str
    song_count: Optional[int]
    album_count: Optional[int]


class Album(abc.ABC):
    id: str
    name: str
    artist: Optional["Artist"]
    cover_art: Optional[str]
    created: Optional[datetime]
    duration: Optional[timedelta]
    genre: Optional[Genre]
    play_count: Optional[int]
    song_count: Optional[int]
    songs: Optional[Sequence["Song"]]
    starred: Optional[datetime]
    year: Optional[int]


class Artist(abc.ABC):
    id: str
    name: str
    album_count: Optional[int]
    artist_image_url: Optional[str]
    starred: Optional[datetime]
    albums: Optional[Sequence[Album]]

    similar_artists: Optional[Sequence["Artist"]] = None
    biography: Optional[str] = None
    music_brainz_id: Optional[str] = None
    last_fm_url: Optional[str] = None


class Directory(abc.ABC):
    id: str
    title: Optional[str]
    parent: Optional["Directory"]


class Song(abc.ABC):
    # TODO make these cross-reference the corresponding Album / Artist / Directory
    id: str
    title: str
    parent: Directory
    album: Optional[Album]
    artist: Optional[Artist]
    genre: Optional[Genre]

    track: Optional[int]
    year: Optional[int]
    cover_art: Optional[str]
    size: Optional[int]
    content_type: Optional[str]
    suffix: Optional[str]
    transcoded_content_type: Optional[str]
    transcoded_suffix: Optional[str]
    duration: Optional[timedelta]
    bit_rate: Optional[int]
    path: str
    is_video: Optional[bool]
    user_rating: Optional[int]
    average_rating: Optional[float]
    play_count: Optional[int]
    disc_number: Optional[int]
    created: Optional[datetime]
    starred: Optional[datetime]
    type: Optional[MediaType]
    # TODO trim down, make another data structure for directory?


# TODO remove distinction between Playlist and PlaylistDetails
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


class PlayQueue(abc.ABC):
    songs: Sequence[Song]
    position: timedelta
    username: Optional[str]
    changed: Optional[datetime]
    changed_by: Optional[str]
    value: Optional[str]
    current_index: Optional[int]
