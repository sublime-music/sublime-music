from datetime import timedelta
from typing import Any, Optional

from peewee import (
    BooleanField,
    DateTimeField,
    DatabaseProxy,
    Field,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

database = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = database


class DurationField(IntegerField):
    def db_value(self, value: timedelta) -> Optional[int]:
        return value.microseconds if value else None

    def python_value(self, value: Optional[int]) -> Optional[timedelta]:
        return timedelta(microseconds=value) if value else None


class CoverArt(BaseModel):
    id = TextField(unique=True, primary_key=True)
    url = TextField()
    filename = TextField(null=True)


class Playlist(BaseModel):
    id = TextField(unique=True, primary_key=True)
    name = TextField()
    song_count = IntegerField()
    duration = DurationField()
    created = DateTimeField()
    changed = DateTimeField()
    public = BooleanField()
    cover_art = TextField()


ALL_TABLES = (
    CoverArt,
    Playlist,
)
