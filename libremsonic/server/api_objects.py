import inspect
from typing import Dict, List, Any


class APIObject:
    @classmethod
    def from_json(cls, data):
        """
        Approach for deserialization here:
        https://stackoverflow.com/a/40639688/2319844
        """
        annotations: Dict[str, Any] = getattr(cls, '__annotations__', {})

        # Handle lists of objects.
        if issubclass(cls, List):
            list_type = cls.__args__[0]
            instance: List[list_type] = list()
            for value in data:
                instance.append(list_type.from_json(value))

        # Handle dictionaries of objects.
        elif issubclass(cls, Dict):
            key_type = cls.__args__[0]
            val_type = cls.__args__[1]
            instance: Dict[key_type, val_type] = dict()
            for key, value in data.items():
                instance.update(key_type.from_json(key),
                                key_type.from_json(value))

        # Handle everything else by first instantiating the class, then adding
        # all of the sub-elements, recursively calling from_json on them.
        else:
            instance: cls = cls()
            for name, value in data.items():
                field_type = annotations.get(name)
                if inspect.isclass(field_type) and isinstance(
                        value, (dict, tuple, list, set, frozenset)):
                    setattr(instance, name, field_type.from_json(value))
                else:
                    setattr(instance, name, value)

        return instance

    def __repr__(self):
        annotations: Dict[str, Any] = self.__annotations__
        typename = type(self).__name__
        fieldstr = ' '.join([
            f'{field}={self.__getattribute__(field)!r}'
            for field in annotations.keys() if hasattr(self, field)
        ])
        return f'<{typename} {fieldstr}>'


class SubsonicError(APIObject):
    code: int
    message: str


class License(APIObject):
    valid: bool
    email: str


class SubsonicResponse(APIObject):
    status: str
    version: str
    license: License
    error: SubsonicError
