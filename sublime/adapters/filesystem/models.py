from typing import Optional

from peewee import (
    AutoField,
    BooleanField,
    ForeignKeyField,
    IntegerField,
    Model,
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
    valid = BooleanField(default=True)
    cache_key = CacheConstantsField()
    params_hash = TextField()
    last_ingestion_time = TzDateTimeField(null=False)
    file_id = TextField(null=True)
    file_hash = TextField(null=True)

    # TODO some sort of expiry?

    class Meta:
        indexes = ((("cache_key", "params_hash"), True),)


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
        return SimilarArtist.select().where(SimilarArtist.artist == self.id)


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


class IgnoredArticle(BaseModel):
    name = TextField(unique=True, primary_key=True)


class Directory(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)
    parent = ForeignKeyField("self", null=True, backref="children")


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)
    title = TextField()
    duration = DurationField()
    path = TextField()

    album = ForeignKeyField(Album, null=True, backref="songs")
    artist = ForeignKeyField(Artist, null=True, backref="songs")
    parent = ForeignKeyField(Directory, null=True, backref="songs")
    genre = ForeignKeyField(Genre, null=True, backref="songs")

    # figure out how to deal with different transcodings, etc.
    file = ForeignKeyField(CacheInfo, null=True)

    _cover_art = ForeignKeyField(CacheInfo, null=True)

    @property
    def cover_art(self) -> Optional[str]:
        try:
            return self._cover_art.file_id
        except Exception:
            return None

    track = IntegerField(null=True)
    year = IntegerField(null=True)
    play_count = TextField(null=True)
    created = TzDateTimeField(null=True)
    starred = TzDateTimeField(null=True)

    # TODO do I need any of these?
    # size: Optional[int] = None
    # content_type: Optional[str] = None
    # suffix: Optional[str] = None
    # transcoded_content_type: Optional[str] = None
    # transcoded_suffix: Optional[str] = None
    # bit_rate: Optional[int] = None
    # is_video: Optional[bool] = None
    # user_rating: Optional[int] = None
    # average_rating: Optional[float] = None
    # disc_number: Optional[int] = None
    # - type_: Optional[SublimeAPI.MediaType] = None
    # bookmark_position: Optional[int] = None
    # original_width: Optional[int] = None
    # original_height: Optional[int] = None


class DirectoryXChildren(BaseModel):
    directory_id = TextField()
    order = IntegerField()


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

    songs = SortedManyToManyField(Song, backref="playlists")

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
    Artist,
    CacheInfo,
    Directory,
    DirectoryXChildren,
    Genre,
    IgnoredArticle,
    Playlist,
    Playlist.songs.get_through_model(),
    SimilarArtist,
    Song,
    Version,
)
