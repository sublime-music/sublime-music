from datetime import timedelta
from enum import Enum
from typing import Any, Optional

from peewee import (
    BooleanField,
    ManyToManyField,
    DateTimeField,
    Field,
    SqliteDatabase,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)
from playhouse.sqliteq import SqliteQueueDatabase

from sublime.adapters.adapter_base import CachingAdapter

database = SqliteDatabase(None)


# Custom Fields
# =============================================================================
class DurationField(IntegerField):
    def db_value(self, value: timedelta) -> Optional[int]:
        return value.microseconds if value else None

    def python_value(self, value: Optional[int]) -> Optional[timedelta]:
        return timedelta(microseconds=value) if value else None


class CacheConstantsField(TextField):
    def db_value(self, value: CachingAdapter.FunctionNames) -> str:
        return value.value

    def python_value(self, value: str) -> CachingAdapter.FunctionNames:
        return CachingAdapter.FunctionNames(value)


# Models
# =============================================================================
class BaseModel(Model):
    class Meta:
        database = database


class CoverArt(BaseModel):
    id = TextField(unique=True, primary_key=True)
    url = TextField()
    filename = TextField(null=True)


class Song(BaseModel):
    id = TextField(unique=True, primary_key=True)


class CacheInfo(BaseModel):
    query_name = CacheConstantsField(unique=True, primary_key=True)
    last_ingestion_time = DateTimeField(null=False)


class Playlist(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField()
    comment = TextField(null=True)
    owner = TextField(null=True)
    song_count = IntegerField(null=True)
    duration = DurationField(null=True)
    created = DateTimeField(null=True)
    changed = DateTimeField(null=True)
    public = BooleanField(null=True)
    cover_art = TextField(null=True)

    songs = ManyToManyField(Song, backref='playlists')


ALL_TABLES = (
    CacheInfo,
    CoverArt,
    Playlist,
    Playlist.songs.get_through_model(),
    Song,
)
