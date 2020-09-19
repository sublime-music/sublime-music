from typing import List, Optional, Union

from peewee import (
    AutoField,
    BooleanField,
    ForeignKeyField,
    IntegerField,
    Model,
    prefetch,
    Query,
    SqliteDatabase,
    TextField,
)

from .sqlite_extensions import (
    CacheConstantsField,
    DurationField,
    SortedManyToManyField,
    TzDateTimeField,
)

database = SqliteDatabase(None)


# Models
# =============================================================================
class BaseModel(Model):
    class Meta:
        database = database


class CacheInfo(BaseModel):
    id = AutoField()
    valid = BooleanField(default=False)
    cache_key = CacheConstantsField()
    parameter = TextField(null=True, default="")
    # TODO (#2) actually use this for cache expiry.
    last_ingestion_time = TzDateTimeField(null=False)

    class Meta:
        indexes = ((("cache_key", "parameter"), True),)

    # Used for cached files.
    file_id = TextField(null=True)
    file_hash = TextField(null=True)
    size = IntegerField(null=True)
    path = TextField(null=True)
    cache_permanently = BooleanField(null=True)


class Genre(BaseModel):
    name = TextField(unique=True, primary_key=True)
    song_count = IntegerField(null=True)
    album_count = IntegerField(null=True)


class Artist(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)
    album_count = IntegerField(null=True)
    starred = TzDateTimeField(null=True)
    biography = TextField(null=True)
    music_brainz_id = TextField(null=True)
    last_fm_url = TextField(null=True)

    _artist_image_url = ForeignKeyField(CacheInfo, null=True)

    @property
    def artist_image_url(self) -> Optional[str]:
        try:
            return self._artist_image_url.file_id
        except Exception:
            return None

    @property
    def similar_artists(self) -> Query:
        return (
            Artist.select()
            .join(SimilarArtist, on=(SimilarArtist.similar_artist == Artist.id))
            .where(SimilarArtist.artist == self.id)
            .order_by(SimilarArtist.order)
        )


class SimilarArtist(BaseModel):
    artist = ForeignKeyField(Artist)
    similar_artist = ForeignKeyField(Artist)
    order = IntegerField()

    class Meta:
        # The whole thing is unique.
        indexes = ((("artist", "similar_artist", "order"), True),)


class Album(BaseModel):
    id = TextField(unique=True, primary_key=True)
    created = TzDateTimeField(null=True)
    duration = DurationField(null=True)
    name = TextField(null=True)
    play_count = IntegerField(null=True)
    song_count = IntegerField(null=True)
    starred = TzDateTimeField(null=True)
    year = IntegerField(null=True)

    artist = ForeignKeyField(Artist, null=True, backref="albums")
    genre = ForeignKeyField(Genre, null=True, backref="albums")

    _cover_art = ForeignKeyField(CacheInfo, null=True)

    @property
    def cover_art(self) -> Optional[str]:
        try:
            return self._cover_art.file_id
        except Exception:
            return None

    @property
    def songs(self) -> List["Song"]:
        albums = Album.select()
        artists = Album.select()
        return sorted(
            prefetch(self._songs, albums, artists),
            key=lambda s: (s.disc_number or 1, s.track),
        )


class AlbumQueryResult(BaseModel):
    query_hash = TextField(primary_key=True)
    albums = SortedManyToManyField(Album)


class IgnoredArticle(BaseModel):
    name = TextField(unique=True, primary_key=True)


class Directory(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)
    parent_id = TextField(null=True)

    _children: Optional[List[Union["Directory", "Song"]]] = None

    @property
    def children(self) -> List[Union["Directory", "Song"]]:
        if not self._children:
            self._children = list(
                Directory.select().where(Directory.parent_id == self.id)
            ) + list(Song.select().where(Song.parent_id == self.id))
        return self._children

    @children.setter
    def children(self, value: List[Union["Directory", "Song"]]):
        self._children = value


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)
    title = TextField()
    duration = DurationField(null=True)

    parent_id = TextField(null=True)
    album = ForeignKeyField(Album, null=True, backref="_songs")
    artist = ForeignKeyField(Artist, null=True)
    genre = ForeignKeyField(Genre, null=True, backref="songs")

    # figure out how to deal with different transcodings, etc.
    file = ForeignKeyField(CacheInfo, null=True)

    @property
    def size(self) -> Optional[int]:
        try:
            return self.file.size
        except Exception:
            return None

    @property
    def path(self) -> Optional[str]:
        try:
            return self.file.path
        except Exception:
            return None

    _cover_art = ForeignKeyField(CacheInfo, null=True)

    @property
    def cover_art(self) -> Optional[str]:
        try:
            return self._cover_art.file_id
        except Exception:
            return None

    track = IntegerField(null=True)
    disc_number = IntegerField(null=True)
    year = IntegerField(null=True)
    user_rating = IntegerField(null=True)
    starred = TzDateTimeField(null=True)


class Playlist(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField()
    comment = TextField(null=True)
    owner = TextField(null=True)
    song_count = IntegerField(null=True)
    duration = DurationField(null=True)
    created = TzDateTimeField(null=True)
    changed = TzDateTimeField(null=True)
    public = BooleanField(null=True)

    _songs = SortedManyToManyField(Song, backref="playlists")

    @property
    def songs(self) -> List[Song]:
        albums = Album.select()
        artists = Album.select()
        return prefetch(self._songs, albums, artists)

    _cover_art = ForeignKeyField(CacheInfo, null=True)

    @property
    def cover_art(self) -> Optional[str]:
        try:
            return self._cover_art.file_id
        except Exception:
            return None


class Version(BaseModel):
    id = IntegerField(unique=True, primary_key=True)
    major = IntegerField()
    minor = IntegerField()
    patch = IntegerField()

    @staticmethod
    def is_less_than(semver: str) -> bool:
        major, minor, patch = map(int, semver.split("."))
        version, created = Version.get_or_create(
            id=0, defaults={"major": major, "minor": minor, "patch": patch}
        )
        if created:
            # There was no version before, definitely out-of-date
            return True

        return version.major < major or version.minor < minor or version.patch < patch

    @staticmethod
    def update_version(semver: str):
        major, minor, patch = map(int, semver.split("."))
        Version.update(major=major, minor=minor, patch=patch)


ALL_TABLES = (
    Album,
    AlbumQueryResult,
    AlbumQueryResult.albums.get_through_model(),
    Artist,
    CacheInfo,
    Directory,
    Genre,
    IgnoredArticle,
    Playlist,
    Playlist._songs.get_through_model(),
    SimilarArtist,
    Song,
    Version,
)
