from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

from peewee import (
    DoubleField,
    ensure_tuple,
    ForeignKeyField,
    IntegerField,
    ManyToManyField,
    ManyToManyFieldAccessor,
    ManyToManyQuery,
    Model,
    SelectQuery,
    TextField,
)

from sublime_music.adapters.adapter_base import CachingAdapter


# Custom Fields
# =============================================================================
class CacheConstantsField(TextField):
    def db_value(self, value: CachingAdapter.CachedDataKey) -> str:
        return value.value

    def python_value(self, value: str) -> CachingAdapter.CachedDataKey:
        return CachingAdapter.CachedDataKey(value)


class DurationField(DoubleField):
    def db_value(self, value: timedelta) -> Optional[float]:
        return value.total_seconds() if value else None

    def python_value(self, value: Optional[float]) -> Optional[timedelta]:
        return timedelta(seconds=value) if value else None


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
        assert not isinstance(value, SelectQuery)
        value = ensure_tuple(value)
        if not value:
            return

        inserts = [
            {
                accessor.src_fk.name: src_id,
                accessor.dest_fk.name: rel_id,
                "position": i,
            }
            for i, rel_id in enumerate(self._id_list(value))
        ]
        accessor.through_model.insert_many(inserts).execute()


class SortedManyToManyFieldAccessor(ManyToManyFieldAccessor):
    def __get__(
        self,
        instance: Model,
        instance_type: Any = None,
        force_query: bool = False,
    ):
        if instance is not None:
            if not force_query and self.src_fk.backref != "+":
                backref = getattr(instance, self.src_fk.backref)
                assert not isinstance(backref, list)
                # if isinstance(backref, list):
                #     return [getattr(obj, self.dest_fk.name) for obj in backref]

            src_id = getattr(instance, self.src_fk.rel_field.name)
            return (
                SortedManyToManyQuery(instance, self, self.rel_model)
                .join(self.through_model)
                .join(self.model)
                .where(self.src_fk == src_id)
                .order_by(self.through_model.position)
            )

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
            table_name = "{}_{}_through".format(*tables)
            indexes = (((lhs._meta.name, rhs._meta.name, "position"), True),)

        params = {"on_delete": self._on_delete, "on_update": self._on_update}
        attrs = {
            lhs._meta.name: ForeignKeyField(lhs, **params),
            rhs._meta.name: ForeignKeyField(rhs, **params),
            "position": IntegerField(),
            "Meta": Meta,
        }

        klass_name = "{}{}Through".format(lhs.__name__, rhs.__name__)
        return type(klass_name, (Model,), attrs)
