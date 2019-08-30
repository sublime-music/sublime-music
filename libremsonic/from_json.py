from datetime import datetime
from enum import EnumMeta
import typing
from typing import Dict, List, Type

from dateutil import parser


def from_json(cls, data):
    """
    Converts data from a JSON parse into Python data structures.

    Arguments:

    cls: the template class to deserialize into
    data: the data to deserialize to the class
    """
    # Approach for deserialization here:
    # https://stackoverflow.com/a/40639688/2319844

    # If it's a forward reference, evaluate it to figure out the actual
    # type. This allows for types that have to be put into a string.
    if isinstance(cls, typing.ForwardRef):
        cls = cls._evaluate(globals(), locals())

    annotations: Dict[str, Type] = getattr(cls, '__annotations__', {})

    # Handle primitive of objects
    if data is None:
        instance = None
    # Handle generics. List[*], Dict[*, *] in particular.
    elif type(cls) == typing._GenericAlias:
        # Having to use this because things changed in Python 3.7.
        class_name = cls._name

        # This is not very elegant since it doesn't allow things which sublass
        # from List or Dict. For my purposes, this doesn't matter.
        if class_name == 'List':
            list_type = cls.__args__[0]
            instance: List[list_type] = list()
            for value in data:
                instance.append(from_json(list_type, value))

        elif class_name == 'Dict':
            key_type, val_type = cls.__args__
            instance: Dict[key_type, val_type] = dict()
            for key, value in data.items():
                key = from_json(key_type, key)
                value = from_json(val_type, value)
                instance[key] = value
        else:
            raise Exception(
                f'Trying to deserialize an unsupported type: {cls._name}')

    elif cls == str or issubclass(cls, str):
        instance = data
    elif cls == int or issubclass(cls, int):
        instance = int(data)
    elif cls == bool or issubclass(cls, bool):
        instance = bool(data)
    elif type(cls) == EnumMeta:
        if type(data) == dict:
            instance = cls(data.get('_value_'))
        else:
            instance = cls(data)
    elif cls == datetime:
        if type(data) == int:
            instance = datetime.fromtimestamp(data / 1000)
        else:
            instance = parser.parse(data)

    # Handle everything else by first instantiating the class, then adding
    # all of the sub-elements, recursively calling from_json on them.
    else:
        instance: cls = cls()
        for field, field_type in annotations.items():
            value = data.get(field)
            setattr(instance, field, from_json(field_type, value))

    return instance
