"""
These are the API objects that are returned by Subsonic.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

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
    datetime: (lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z") if s else None),
    timedelta: (lambda s: timedelta(seconds=s) if s else None),
}

for type_, translation_function in extra_translation_map.items():
    dataclasses_json.cfg.global_config.decoders[type_] = translation_function
    dataclasses_json.cfg.global_config.decoders[Optional[type_]] = translation_function


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Genre(SublimeAPI.Genre):
    name: str = field(metadata=config(field_name="value"))
    song_count: Optional[int] = None
    album_count: Optional[int] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Album(SublimeAPI.Album):
    id: str
    name: str
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
            if not self.artist_id
            else ArtistAndArtistInfo(self.artist_id, self._artist)
        )
        self.genre = None if not self._genre else Genre(self._genre)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistAndArtistInfo(SublimeAPI.Artist):
    id: str
    name: str
    albums: List[Album] = field(
        default_factory=list, metadata=config(field_name="album")
    )
    album_count: Optional[int] = None
    cover_art: Optional[str] = None
    artist_image_url: Optional[str] = None
    starred: Optional[datetime] = None

    # Artist Info
    similar_artists: List["ArtistAndArtistInfo"] = field(
        default_factory=list, metadata=config(field_name="similar_artist")
    )
    biography: Optional[str] = None
    music_brainz_id: Optional[str] = None
    last_fm_url: Optional[str] = None

    def __post_init__(self):
        self.album_count = self.album_count or len(self.albums)
        if not self.artist_image_url:
            self.artist_image_url = self.cover_art

    def augment_with_artist_info(self, artist_info: Optional["ArtistInfo"]):
        if artist_info:
            for k, v in asdict(artist_info).items():
                if v:
                    setattr(self, k, v)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistInfo:
    similar_artist: List[ArtistAndArtistInfo] = field(default_factory=list)
    biography: Optional[str] = None
    last_fm_url: Optional[str] = None
    artist_image_url: Optional[str] = field(
        default=None, metadata=config(field_name="largeImageUrl")
    )
    music_brainz_id: Optional[str] = None

    def __post_init__(self):
        if self.artist_image_url:
            if self.artist_image_url.endswith("2a96cbd8b46e442fc41c2b86b821562f.png"):
                self.artist_image_url = ""
            elif self.artist_image_url.endswith("-No_image_available.svg.png"):
                self.artist_image_url = ""


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Directory(SublimeAPI.Directory):
    id: str
    title: Optional[str] = None
    parent: Optional["Directory"] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class Song(SublimeAPI.Song):
    id: str
    title: str
    path: str
    parent: Directory = field(init=False)
    _parent: Optional[str] = field(default=None, metadata=config(field_name="parent"))

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

    # TODO deal with these
    track: Optional[int] = None
    year: Optional[int] = None
    cover_art: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    suffix: Optional[str] = None
    transcoded_content_type: Optional[str] = None
    transcoded_suffix: Optional[str] = None
    duration: Optional[timedelta] = None
    bit_rate: Optional[int] = None
    is_video: Optional[bool] = None
    user_rating: Optional[int] = None
    average_rating: Optional[float] = None
    play_count: Optional[int] = None
    disc_number: Optional[int] = None
    created: Optional[datetime] = None
    starred: Optional[datetime] = None
    type: Optional[SublimeAPI.MediaType] = None

    def __post_init__(self):
        # Initialize the cross-references
        self.parent = None if not self._parent else Directory(self._parent)
        self.artist = (
            None
            if not self.artist_id
            else ArtistAndArtistInfo(self.artist_id, self._artist)
        )
        self.album = None if not self.album_id else Album(self.album_id, self._album)
        self.genre = None if not self._genre else Genre(self._genre)


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
    songs: List[Song] = field(default_factory=list, metadata=config(field_name="entry"))
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
            self.current_index = [int(s.id) for s in self.songs].index(cur)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class IndexID3:
    name: str
    artist: List[ArtistAndArtistInfo] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ArtistsID3:
    ignored_articles: str
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
class Playlists:
    playlist: List[Playlist] = field(default_factory=list)


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

    genres: Optional[Genres] = None
    playlist: Optional[PlaylistWithSongs] = None
    playlists: Optional[Playlists] = None
    play_queue: Optional[PlayQueue] = field(
        default=None, metadata=config(field_name="playQueue")
    )
    song: Optional[Song] = None
