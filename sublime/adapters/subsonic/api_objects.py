"""
These are the API objects that are returned by Subsonic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import operator
from functools import reduce

import dataclasses_json
from dataclasses_json import (
    config,
    dataclass_json,
    DataClassJsonMixin,
    LetterCase,
)

from .. import api_objects as SublimeAPI

# Translation map
extra_translation_map = {
    datetime:
    (lambda s: datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f%z') if s else None),
    timedelta: (lambda s: timedelta(seconds=s) if s else None),
}

for type_, translation_function in extra_translation_map.items():
    dataclasses_json.cfg.global_config.decoders[type_] = translation_function
    dataclasses_json.cfg.global_config.decoders[
        Optional[type_]] = translation_function


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Child(SublimeAPI.Song):
    id: str
    title: str
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
    duration: Optional[timedelta] = None
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
    songs: List[Child] = field(
        default_factory=list, metadata=config(field_name='entry'))
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
            seconds=sum(s.duration.total_seconds() if s.duration else 0 for s in self.songs))


@dataclass
class Playlists(DataClassJsonMixin):
    playlist: List[Playlist] = field(default_factory=list)


@dataclass
class Response(DataClassJsonMixin):
    """
    The base Subsonic response object.
    """
    song: Optional[Child] = None
    playlists: Optional[Playlists] = None
    playlist: Optional[PlaylistWithSongs] = None
