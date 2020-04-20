"""
These are the API objects that are returned by Subsonic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Sequence

from dataclasses_json import config, dataclass_json, DataClassJsonMixin, LetterCase
from dateutil import parser
from marshmallow import fields

from .. import api_objects as SublimeAPI

datetime_metadata = config(
    encoder=datetime.isoformat,
    decoder=lambda d: parser.parse(d) if d else None,
    mm_field=fields.DateTime(format='iso'),
)

timedelta_metadata = config(
    encoder=datetime.isoformat,
    decoder=lambda s: timedelta(seconds=s) if s else None,
    mm_field=fields.TimeDelta(),
)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(frozen=True)
class Child(SublimeAPI.Song, DataClassJsonMixin):
    title: str
    value: Optional[str] = None
    parent: Optional[str] = None
    album: Optional[str] = None
    artist: Optional[str] = None
    track: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    coverArt: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    suffix: Optional[str] = None
    transcoded_content_type: Optional[str] = None
    transcoded_suffix: Optional[str] = None
    duration: Optional[int] = None
    bit_rate: Optional[int] = None
    path: Optional[str] = None
    isVideo: Optional[bool] = None
    # userRating: Optional[UserRating] = None
    # averageRating: Optional[AverageRating] = None
    play_count: Optional[int] = None
    disc_number: Optional[int] = None
    created: Optional[datetime] = None
    starred: Optional[datetime] = None
    albumId: Optional[str] = None
    artistId: Optional[str] = None
    # type_: Optional[MediaType] = None
    bookmark_position: Optional[int] = None
    original_width: Optional[int] = None
    original_height: Optional[int] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Playlist(SublimeAPI.Playlist):
    id: str
    name: str
    song_count: Optional[int] = None
    duration: Optional[timedelta] = field(
        default=None, metadata=timedelta_metadata)
    created: Optional[datetime] = field(
        default=None, metadata=datetime_metadata)
    changed: Optional[datetime] = field(
        default=None, metadata=datetime_metadata)
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    cover_art: Optional[str] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PlaylistWithSongs(SublimeAPI.PlaylistDetails):
    duration: timedelta = field(
        default_factory=timedelta, metadata=timedelta_metadata)
    songs: List[SublimeAPI.Song] = field(
        default_factory=list,
        metadata=config(field_name='entry'),
    )
    created: Optional[datetime] = field(
        default=None, metadata=datetime_metadata)
    changed: Optional[datetime] = field(
        default=None, metadata=datetime_metadata)


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
    value: Optional[str] = None
