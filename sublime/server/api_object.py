"""
Defines the base class for API objects.
"""

from enum import Enum
from typing import Any, Dict

from sublime.from_json import from_json as _from_json


class APIObject:
    @classmethod
    def from_json(cls, data):
        return _from_json(cls, data)

    def get(self, field, default=None):
        return getattr(self, field, default)

    def __repr__(self):
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
