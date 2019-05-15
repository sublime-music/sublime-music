import inspect
import typing
from typing import Dict, List, Any, Type
from datetime import datetime
from dateutil import parser


def _from_json(cls, data):
    """
    Approach for deserialization here:
    https://stackoverflow.com/a/40639688/2319844
    """
    annotations: Dict[str, Type] = getattr(cls, '__annotations__', {})

    # Handle lists of objects.
    if cls == str:
        instance = data
    elif cls == int:
        instance = int(data)
    elif cls == bool:
        instance = bool(data)
    elif cls == datetime:
        instance = parser.parse(data)
    elif type(cls) == typing._GenericAlias:
        # Having to use this because things changed in Python 3.7.

        # No idea what the heck this is, but let's go with it.
        if cls._name == 'List':
            list_type = cls.__args__[0]
            instance: List[list_type] = list()
            for value in data:
                instance.append(_from_json(list_type, value))

        elif cls._name == 'Dict':
            key_type, val_type = cls.__args__
            instance: Dict[key_type, val_type] = dict()
            for key, value in data.items():
                key = _from_json(key_type, key)
                value = _from_json(val_type, value)
                instance[key] = value
        else:
            raise Exception(
                'Trying to deserialize an unsupported type: {cls._name}')

    # Handle everything else by first instantiating the class, then adding
    # all of the sub-elements, recursively calling from_json on them.
    else:
        instance: cls = cls()
        for name, value in data.items():
            field_type = annotations.get(name)

            # Sometimes there are extraneous values, ignore them.
            if field_type:
                setattr(instance, name, _from_json(field_type, value))

    return instance


class APIObject:
    @classmethod
    def from_json(cls, data):
        return _from_json(cls, data)

    def get(self, field, default=None):
        return getattr(self, field, default)

    def __repr__(self):
        annotations: Dict[str, Any] = self.__annotations__
        typename = type(self).__name__
        fieldstr = ' '.join([
            f'{field}={getattr(self, field)!r}'
            for field in annotations.keys() if hasattr(self, field)
        ])
        return f'<{typename} {fieldstr}>'


class SubsonicError(APIObject):
    code: int
    message: str

    def as_exception(self):
        return Exception(f'{self.code}: {self.message}')


class License(APIObject):
    valid: bool
    email: str
    licenseExpires: datetime
    trialExpires: datetime


class MusicFolder(APIObject):
    id: int
    name: str


class SubsonicResponse(APIObject):
    status: str
    version: str
    license: License
    error: SubsonicError
    musicFolders: Dict[str, List[MusicFolder]]
