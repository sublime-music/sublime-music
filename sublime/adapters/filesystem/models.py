from typing import Optional

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


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)
    title = TextField()
    duration = DurationField()
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

    # TODO make these fks
    album = TextField(null=True)
    album_id = TextField(null=True)
    artist = TextField(null=True)
    artist_id = TextField(null=True)

    parent = TextField(null=True)

    _genre = ForeignKeyField(Genre, null=True)

    @property
    def genre(self) -> Optional[str]:
        return self._genre.name if self._genre else None

    @genre.setter
    def genre(self, genre_name: str):
        if not genre_name:
            return
        genre, genre_created = Genre.get_or_create(
            name=genre_name, defaults={"name": genre_name},
        )
        self._genre = genre
        self.save()


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
    Album,
    CacheInfo,
    # CachedFile,
    Genre,
    Playlist,
    Playlist.songs.get_through_model(),
    Song,
)
