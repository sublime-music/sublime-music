import inspect
from typing import Dict, List, Any
from datetime import datetime
from dateutil import parser


def _from_json(cls, data):
    """
    Approach for deserialization here:
    https://stackoverflow.com/a/40639688/2319844
    """
    print(cls, data)
    annotations: Dict[str, Any] = getattr(cls, '__annotations__', {})

    # Handle lists of objects.
    if cls == str:
        return data
    if issubclass(cls, List):
        list_type = cls.__args__[0]
        instance: List[list_type] = list()
        for value in data:
            instance.append(_from_json(list_type, value))

    # Handle dictionaries of objects.
    elif issubclass(cls, Dict):
        key_type, val_type = cls.__args__
        instance: Dict[key_type, val_type] = dict()
        for key, value in data.items():
            instance.update(_from_json(key_type, key),
                            _from_json(val_type, value))

    # Handle everything else by first instantiating the class, then adding
    # all of the sub-elements, recursively calling from_json on them.
    else:
        instance: cls = cls()
        for name, value in data.items():
            field_type = annotations.get(name)
            print('ohea', field_type, value)
            if inspect.isclass(field_type):
                setattr(instance, name, _from_json(field_type, value))
            else:
                setattr(instance, name, value)

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


class MusicFolder(APIObject):
    id: int
    name: str


class SubsonicResponse(APIObject):
    status: str
    version: str
    license: License
    error: SubsonicError
    musicFolders: List[MusicFolder]
