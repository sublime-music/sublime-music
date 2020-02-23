from enum import Enum
from typing import Any, Dict

from sublime.from_json import from_json as _from_json


class APIObject:
    """
    Defines the base class for objects coming from the Subsonic API. For now,
    this only supports JSON.
    """
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Any:
        """
        Creates an :class:`APIObject` by deserializing JSON data into a Python
        object.  This calls the :class:`sublime.from_json.from_json` function
        to do the deserializing.

        :param data: a Python dictionary representation of the data to
            deserialize
        """
        return _from_json(cls, data)

    def get(self, field: str, default: Any = None) -> Any:
        """
        Get the value of ``field`` or ``default``.

        :param field: name of the field to retrieve
        :param default: the default value to return if ``field`` is falsy.
        """
        return getattr(self, field, default)

    def __repr__(self) -> str:
        if isinstance(self, Enum):
            return super().__repr__()
        if isinstance(self, str):
            return self

        annotations: Dict[str, Any] = self.get('__annotations__', {})
        typename = type(self).__name__
        fieldstr = ' '.join(
            [
                f'{field}={getattr(self, field)!r}'
                for field in annotations.keys()
                if hasattr(self, field) and getattr(self, field) is not None
            ])
        return f'<{typename} {fieldstr}>'
