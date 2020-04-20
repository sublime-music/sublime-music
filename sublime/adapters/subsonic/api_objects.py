"""
These are the API objects that are returned by Subsonic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

import dataclasses_json
from dataclasses_json import (
    config,
    dataclass_json,
    DataClassJsonMixin,
    LetterCase,
)
from dateutil import parser

from .. import api_objects as SublimeAPI

dataclasses_json.cfg.global_config.encoders[datetime] = datetime.isoformat
dataclasses_json.cfg.global_config.decoders[datetime] = parser.parse
dataclasses_json.cfg.global_config.encoders[timedelta] = (
    timedelta.total_seconds)
dataclasses_json.cfg.global_config.decoders[timedelta] = lambda s: timedelta(
    seconds=s)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(frozen=True)
class Child(SublimeAPI.Song):
    id: str
    title: str
    value: Optional[str] = None
    parent: Optional[str] = None
    album: Optional[str] = None
    artist: Optional[str] = None
    track: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    cover_art: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    suffix: Optional[str] = None
    transcoded_content_type: Optional[str] = None
    transcoded_suffix: Optional[str] = None
    duration: Optional[int] = None
    bit_rate: Optional[int] = None
    path: Optional[str] = None
    is_video: Optional[bool] = None
    user_rating: Optional[int] = None
    average_rating: Optional[float] = None
    play_count: Optional[int] = None
    disc_number: Optional[int] = None
    created: Optional[datetime] = None
    starred: Optional[datetime] = None
    album_id: Optional[str] = None
    artist_id: Optional[str] = None
    type: Optional[SublimeAPI.MediaType] = None
    bookmark_position: Optional[int] = None
    original_width: Optional[int] = None
    original_height: Optional[int] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Playlist(SublimeAPI.Playlist):
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


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PlaylistWithSongs(SublimeAPI.PlaylistDetails):
    id: str
    name: str
    songs: List[Child] = field(metadata=config(field_name='entry'))
    song_count: int = field(default=0)
    duration: timedelta = field(default=timedelta())
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    cover_art: Optional[str] = None

    def __post_init__(self):
        self.song_count = self.song_count or len(self.songs)
        self.duration = self.duration or timedelta(
            seconds=sum(s.duration for s in self.songs))


@dataclass(frozen=True)
class Playlists(DataClassJsonMixin):
    playlist: List[Playlist] = field(default_factory=list)


@dataclass(frozen=True)
class Response(DataClassJsonMixin):
    """
    The base Subsonic response object.
    """
    song: Optional[Child] = None
    playlists: Optional[Playlists] = None
    playlist: Optional[PlaylistWithSongs] = None
