from dataclasses import Field, fields
from typing import Any, Dict


class APIObject:
    """Defines the base class for objects coming from the Subsonic API."""
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Any:
        """
        Creates an :class:`APIObject` by taking the ``data`` and passing it to
        the class constructor and then recursively calling ``from_json`` on all
        of the fields. ``data`` just has to be a well-formed :class:`dict`, so
        it can come from the JSON or XML APIs.

        :param data: a Python dictionary representation of the data to
            deserialize
        """
        if data is None:
            return data
        print('=' * 80)
        deserialized = cls.__call__(**data)
        for field in fields(cls):
            print(field)
            value = getattr(deserialized, field.name)
            print('ohea', value)
