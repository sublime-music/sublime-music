from peewee import (
    BooleanField,
    CompositeKey,
    ForeignKeyField,
    IntegerField,
    Model,
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


# class CachedFile(BaseModel):
#     id = TextField(unique=True, primary_key=True)
#     filename = TextField(null=True)


class Genre(BaseModel):
    name = TextField(unique=True, primary_key=True)
    song_count = IntegerField(null=True)
    album_count = IntegerField(null=True)


class Album(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)


class Artist(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)


class Directory(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField(null=True)
    parent = ForeignKeyField("self", null=True, backref="children")


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)
    title = TextField()
    duration = DurationField()
    album = ForeignKeyField(Album, null=True)
    artist = ForeignKeyField(Artist, null=True)
    parent = ForeignKeyField(Directory, null=True)
    genre = ForeignKeyField(Genre, null=True)

    track = IntegerField(null=True)
    year = IntegerField(null=True)
    cover_art = TextField(null=True)  # TODO: fk?
    path = TextField()
    play_count = TextField(null=True)
    created = TzDateTimeField(null=True)
    starred = TzDateTimeField(null=True)

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


class CacheInfo(BaseModel):
    cache_key = CacheConstantsField()
    params_hash = TextField()
    last_ingestion_time = TzDateTimeField(null=False)

    # TODO some sort of expiry?

    class Meta:
        primary_key = CompositeKey("cache_key", "params_hash")


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
    cover_art = TextField(null=True)  # TODO: fk

    # cover_art_file = ForeignKeyField(CachedFile, null=True)

    songs = SortedManyToManyField(Song, backref="playlists")


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
    Genre,
    Playlist,
    Playlist.songs.get_through_model(),
    Song,
    Version,
)
