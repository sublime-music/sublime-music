from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Sequence, List

from peewee import (
    ensure_tuple,
    SelectQuery,
    FieldAccessor,
    Value,
    ManyToManyFieldAccessor,
    BooleanField,
    DoubleField,
    Field,
    ForeignKeyField,
    IntegerField,
    ManyToManyField,
    ManyToManyQuery,
    Model,
    SqliteDatabase,
    TextField,
)

from sublime.adapters.adapter_base import CachingAdapter

database = SqliteDatabase(None)


# Custom Fields
# =============================================================================
class DurationField(DoubleField):
    def db_value(self, value: timedelta) -> Optional[float]:
        return value.total_seconds() if value else None

    def python_value(self, value: Optional[float]) -> Optional[timedelta]:
        return timedelta(seconds=value) if value else None


class CacheConstantsField(TextField):
    def db_value(self, value: CachingAdapter.FunctionNames) -> str:
        return value.value

    def python_value(self, value: str) -> CachingAdapter.FunctionNames:
        return CachingAdapter.FunctionNames(value)


class TzDateTimeField(TextField):
    def db_value(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    def python_value(self, value: Optional[str]) -> Optional[datetime]:
        return datetime.fromisoformat(value) if value else None


# Sorted M-N Association Field
# =============================================================================
class SortedManyToManyQuery(ManyToManyQuery):
    def add(self, value: Sequence[Any], clear_existing: bool = False):
        if clear_existing:
            self.clear()

        accessor = self._accessor
        src_id = getattr(self._instance, self._src_attr)
        if isinstance(value, SelectQuery):
            print('TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT')
            raise NotImplementedError()
            # query = value.columns(Value(src_id), accessor.dest_fk.rel_field)
            # accessor.through_model.insert_from(
            #     fields=[accessor.src_fk, accessor.dest_fk],
            #     query=query).execute()
        else:
            value = ensure_tuple(value)
            if not value:
                return

            inserts = [
                {
                    accessor.src_fk.name: src_id,
                    accessor.dest_fk.name: rel_id,
                    'position': i,
                } for i, rel_id in enumerate(self._id_list(value))
            ]
            accessor.through_model.insert_many(inserts).execute()

    def remove(self, value: Any) -> Any:
        print('RRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR')
        raise NotImplementedError()
        # src_id = getattr(self._instance, self._src_attr)
        # if isinstance(value, SelectQuery):
        #     column = getattr(value.model, self._dest_attr)
        #     subquery = value.columns(column)
        #     return (
        #         self._accessor.through_model.delete().where(
        #             (self._accessor.dest_fk << subquery)
        #             & (self._accessor.src_fk == src_id)).execute())
        # else:
        #     value = ensure_tuple(value)
        #     if not value:
        #         return
        #     return (
        #         self._accessor.through_model.delete().where(
        #             (self._accessor.dest_fk << self._id_list(value))
        #             & (self._accessor.src_fk == src_id)).execute())

    # def clear(self) -> Any:
    #     src_id = getattr(self._instance, self._src_attr)
    #     return (
    #         self._accessor.through_model.delete().where(
    #             self._accessor.src_fk == src_id).execute())


class SortedManyToManyFieldAccessor(ManyToManyFieldAccessor):
    def __get__(
        self,
        instance: Model,
        instance_type: Any = None,
        force_query: bool = False,
    ):
        if instance is not None:
            if not force_query and self.src_fk.backref != '+':
                backref = getattr(instance, self.src_fk.backref)
                if isinstance(backref, list):
                    return [getattr(obj, self.dest_fk.name) for obj in backref]

            src_id = getattr(instance, self.src_fk.rel_field.name)
            return SortedManyToManyQuery(instance, self, self.rel_model) \
                .join(self.through_model) \
                .join(self.model) \
                .where(self.src_fk == src_id) \
                .order_by(self.through_model.position)

        return self.field

    def __set__(self, instance: Model, value: Sequence[Any]):
        query = self.__get__(instance, force_query=True)
        query.add(value, clear_existing=True)


class SortedManyToManyField(ManyToManyField):
    accessor_class = SortedManyToManyFieldAccessor

    def _create_through_model(self) -> type:
        lhs, rhs = self.get_models()
        tables = [model._meta.table_name for model in (lhs, rhs)]

        class Meta:
            database = self.model._meta.database
            schema = self.model._meta.schema
            table_name = '{}_{}_through'.format(*tables)
            indexes = (((lhs._meta.name, rhs._meta.name), True), )

        params = {'on_delete': self._on_delete, 'on_update': self._on_update}
        attrs = {
            lhs._meta.name: ForeignKeyField(lhs, **params),
            rhs._meta.name: ForeignKeyField(rhs, **params),
            'position': IntegerField(),
            'Meta': Meta
        }

        klass_name = '{}{}Through'.format(lhs.__name__, rhs.__name__)
        return type(klass_name, (Model, ), attrs)


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
    title = TextField()
    duration = DurationField()
    parent = TextField()
    album = TextField()
    artist = TextField()
    track = IntegerField(null=True)
    year = IntegerField(null=True)
    genre = TextField(null=True)
    cover_art = TextField(null=True)
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
    query_name = CacheConstantsField(unique=True, primary_key=True)
    last_ingestion_time = TzDateTimeField(null=False)


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
    cover_art = TextField(null=True)

    songs = SortedManyToManyField(Song, backref='playlists')


ALL_TABLES = (
    CacheInfo,
    CoverArt,
    Playlist,
    Playlist.songs.get_through_model(),
    Song,
)
