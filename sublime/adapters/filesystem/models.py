from peewee import (
    BooleanField,
    CompositeKey,
    # ForeignKeyField,
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


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)
    title = TextField()
    duration = DurationField()
    parent = TextField()  # TODO: fk
    album = TextField()  # TODO: fk
    artist = TextField()  # TODO: fk
    track = IntegerField(null=True)
    year = IntegerField(null=True)
    genre = TextField(null=True)  # TODO: fk
    cover_art = TextField(null=True)  # TODO: fk
    # size: Optional[int] = None
    # content_type: Optional[str] = None
    # suffix: Optional[str] = None
    # transcoded_content_type: Optional[str] = None
    # transcoded_suffix: Optional[str] = None
    # duration= DurationField ()
    # bit_rate: Optional[int] = None
    path = TextField()
    # is_video: Optional[bool] = None
    # user_rating: Optional[int] = None
    # average_rating: Optional[float] = None
    # play_count: Optional[int] = None
    # disc_number: Optional[int] = None
    # created: Optional[datetime] = None
    # starred: Optional[datetime] = None
    # album_id: Optional[str] = None
    # artist_id: Optional[str] = None
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


ALL_TABLES = (
    CacheInfo,
    # CachedFile,
    Playlist,
    Playlist.songs.get_through_model(),
    Song,
)
