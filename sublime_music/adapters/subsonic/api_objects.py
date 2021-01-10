"""
These are the API objects that are returned by Subsonic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import dataclasses_json
from dataclasses_json import (
    config,
    dataclass_json,
    DataClassJsonMixin,
    LetterCase,
)
from dateutil import parser

from .. import api_objects as SublimeAPI

# Translation map for encoding/decoding API results. For instance some servers
# may return a string where an integer is required.
decoder_functions = {
    datetime: (lambda s: parser.parse(s) if s else None),
    timedelta: (lambda s: timedelta(seconds=float(s)) if s else None),
    int: (lambda s: int(s) if s else None),
}
encoder_functions = {
    datetime: (lambda d: datetime.strftime(d, "%Y-%m-%dT%H:%M:%S.%f%z") if d else None),
    timedelta: (lambda t: t.total_seconds() if t else None),
}

for type_, translation_function in decoder_functions.items():
    dataclasses_json.cfg.global_config.decoders[type_] = translation_function
    dataclasses_json.cfg.global_config.decoders[
        Optional[type_]  # type: ignore
    ] = translation_function

for type_, translation_function in encoder_functions.items():
    dataclasses_json.cfg.global_config.encoders[type_] = translation_function
    dataclasses_json.cfg.global_config.encoders[
        Optional[type_]  # type: ignore
    ] = translation_function


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Genre(SublimeAPI.Genre):
    name: str = field(metadata=config(field_name="value"))
    song_count: Optional[int] = None
    album_count: Optional[int] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Album(SublimeAPI.Album):
    name: str
    id: Optional[str]
    cover_art: Optional[str] = None
    song_count: Optional[int] = None
    year: Optional[int] = None
    duration: Optional[timedelta] = None
    created: Optional[datetime] = None
    songs: List["Song"] = field(
        default_factory=list, metadata=config(field_name="song")
    )
    play_count: Optional[int] = None
    starred: Optional[datetime] = None

    # Artist
    artist: Optional["ArtistAndArtistInfo"] = field(init=False)
    _artist: Optional[str] = field(default=None, metadata=config(field_name="artist"))
    artist_id: Optional[str] = None

    # Genre
    genre: Optional[Genre] = field(init=False)
    _genre: Optional[str] = field(default=None, metadata=config(field_name="genre"))

    def __post_init__(self):
        # Initialize the cross-references
        self.artist = (
            None
            if not self.artist_id and not self._artist
            else ArtistAndArtistInfo(id=self.artist_id, name=self._artist)
        )
        self.genre = None if not self._genre else Genre(self._genre)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistAndArtistInfo(SublimeAPI.Artist):
    name: str
    id: Optional[str]
    albums: List[Album] = field(
        default_factory=list, metadata=config(field_name="album")
    )
    album_count: Optional[int] = None
    cover_art: Optional[str] = None
    artist_image_url: Optional[str] = None
    starred: Optional[datetime] = None

    # Artist Info
    similar_artists: List["ArtistAndArtistInfo"] = field(default_factory=list)
    biography: Optional[str] = None
    music_brainz_id: Optional[str] = None
    last_fm_url: Optional[str] = None

    def __post_init__(self):
        if not self.album_count and len(self.albums) > 0:
            self.album_count = len(self.albums)
        if not self.artist_image_url:
            self.artist_image_url = self.cover_art

    def augment_with_artist_info(self, artist_info: Optional["ArtistInfo"]):
        if artist_info:
            self.similar_artists = artist_info.similar_artists
            self.biography = artist_info.biography
            self.last_fm_url = artist_info.last_fm_url
            self.artist_image_url = (
                artist_info.artist_image_url or self.artist_image_url
            )
            self.music_brainz_id = artist_info.music_brainz_id


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistInfo:
    similar_artists: List[ArtistAndArtistInfo] = field(
        default_factory=list, metadata=config(field_name="similarArtist")
    )
    biography: Optional[str] = None
    last_fm_url: Optional[str] = None
    artist_image_url: Optional[str] = field(
        default=None, metadata=config(field_name="largeImageUrl")
    )
    music_brainz_id: Optional[str] = None

    def __post_init__(self):
        if self.artist_image_url:
            placeholder_image_names = (
                "2a96cbd8b46e442fc41c2b86b821562f.png",
                "-No_image_available.svg.png",
            )
            for n in placeholder_image_names:
                if self.artist_image_url.endswith(n):
                    self.artist_image_url = ""
                    return


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Directory(SublimeAPI.Directory):
    id: str
    name: Optional[str] = None
    title: Optional[str] = None
    parent_id: Optional[str] = field(default=None, metadata=config(field_name="parent"))

    children: List[Union["Directory", "Song"]] = field(init=False)
    _children: List[Dict[str, Any]] = field(
        default_factory=list, metadata=config(field_name="child")
    )

    def __post_init__(self):
        if not isinstance(self.id, str):
            self.id = str(self.id)
        self.parent_id = (self.parent_id or "root") if self.id != "root" else None

        self.name = self.name or self.title
        self.children = [
            Directory.from_dict(c) if c.get("isDir") else Song.from_dict(c)
            for c in self._children
        ]


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Song(SublimeAPI.Song, DataClassJsonMixin):
    id: str
    title: str = field(metadata=config(field_name="name"))
    path: Optional[str] = None
    parent_id: Optional[str] = field(default=None, metadata=config(field_name="parent"))
    duration: Optional[timedelta] = None

    # Artist
    artist: Optional[ArtistAndArtistInfo] = field(init=False)
    _artist: Optional[str] = field(default=None, metadata=config(field_name="artist"))
    artist_id: Optional[str] = None

    # Album
    album: Optional[Album] = field(init=False)
    _album: Optional[str] = field(default=None, metadata=config(field_name="album"))
    album_id: Optional[str] = None

    # Genre
    genre: Optional[Genre] = field(init=False)
    _genre: Optional[str] = field(default=None, metadata=config(field_name="genre"))

    track: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[int] = None
    size: Optional[int] = None
    cover_art: Optional[str] = None
    user_rating: Optional[int] = None
    starred: Optional[datetime] = None

    def __post_init__(self):
        if not isinstance(self.id, str):
            self.id = str(self.id)
        self.parent_id = (self.parent_id or "root") if self.id != "root" else None
        self.artist = (
            None
            if not self._artist
            else ArtistAndArtistInfo(id=self.artist_id, name=self._artist)
        )
        self.album = (
            None if not self._album else Album(id=self.album_id, name=self._album)
        )
        self.genre = None if not self._genre else Genre(self._genre)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Playlist(SublimeAPI.Playlist):
    id: str
    name: str
    songs: List[Song] = field(default_factory=list, metadata=config(field_name="entry"))
    song_count: Optional[int] = field(default=None)
    duration: Optional[timedelta] = field(default=None)
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    cover_art: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.id, str):
            self.id = str(self.id)
        if self.songs is None:
            return
        if self.song_count is None:
            self.song_count = len(self.songs)

        if self.duration is None:
            self.duration = timedelta(
                seconds=sum(
                    s.duration.total_seconds() if s.duration else 0 for s in self.songs
                )
            )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PlayQueue(SublimeAPI.PlayQueue):
    songs: List[Song] = field(default_factory=list, metadata=config(field_name="entry"))
    position: timedelta = timedelta(0)
    username: Optional[str] = None
    changed: Optional[datetime] = None
    changed_by: Optional[str] = None
    value: Optional[str] = None
    current: Optional[str] = None
    current_index: Optional[int] = None

    def __post_init__(self):
        if pos := self.position:
            # The position for this endpoint is in milliseconds instead of seconds
            # because the Subsonic API is sometime stupid.
            self.position = pos / 1000
        if cur := self.current:
            self.current_index = [s.id for s in self.songs].index(str(cur))


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Index:
    name: str
    artist: List[Dict[str, Any]] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class IndexID3:
    name: str
    artist: List[ArtistAndArtistInfo] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistsID3:
    ignored_articles: Optional[str] = None
    index: List[IndexID3] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class AlbumList2:
    album: List[Album] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Genres:
    genre: List[Genre] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Indexes:
    ignored_articles: Optional[str] = None
    index: List[Index] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Playlists:
    playlist: List[Playlist] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class SearchResult3:
    artist: List[ArtistAndArtistInfo] = field(default_factory=list)
    album: List[Album] = field(default_factory=list)
    song: List[Song] = field(default_factory=list)


@dataclass
class Response(DataClassJsonMixin):
    """The base Subsonic response object."""

    artists: Optional[ArtistsID3] = None
    artist: Optional[ArtistAndArtistInfo] = None
    artist_info: Optional[ArtistInfo] = field(
        default=None, metadata=config(field_name="artistInfo2")
    )

    albums: Optional[AlbumList2] = field(
        default=None, metadata=config(field_name="albumList2")
    )
    album: Optional[Album] = None

    directory: Optional[Directory] = None

    genres: Optional[Genres] = None

    indexes: Optional[Indexes] = None

    playlist: Optional[Playlist] = None
    playlists: Optional[Playlists] = None

    play_queue: Optional[PlayQueue] = field(
        default=None, metadata=config(field_name="playQueue")
    )

    song: Optional[Song] = None

    search_result: Optional[SearchResult3] = field(
        default=None, metadata=config(field_name="searchResult3")
    )
