import typing
from datetime import datetime
from enum import EnumMeta
from typing import Any, Dict, Type

from dateutil import parser


def from_json(template_type: Any, data: Any) -> Any:
    """
    Converts data from a JSON parse into an instantiation of the Python object
    specified by template_type.

    Arguments:

    template_type: the template type to deserialize into
    data: the data to deserialize to the class
    """
    # Approach for deserialization here:
    # https://stackoverflow.com/a/40639688/2319844

    # If it's a forward reference, evaluate it to figure out the actual
    # type. This allows for types that have to be put into a string.
    if isinstance(template_type, typing.ForwardRef):  # type: ignore
        template_type = template_type._evaluate(globals(), locals())

    annotations: Dict[str,
                      Type] = getattr(template_type, '__annotations__', {})

    # Handle primitive of objects
    instance: Any = None
    if data is None:
        instance = None
    # Handle generics. List[*], Dict[*, *] in particular.
    elif type(template_type) == typing._GenericAlias:  # type: ignore
        # Having to use this because things changed in Python 3.7.
        class_name = template_type._name

        # This is not very elegant since it doesn't allow things which sublass
        # from List or Dict. For my purposes, this doesn't matter.
        if class_name == 'List':
            inner_type = template_type.__args__[0]
            instance = [from_json(inner_type, value) for value in data]

        elif class_name == 'Dict':
            key_type, val_type = template_type.__args__
            instance = {
                from_json(key_type, key): from_json(val_type, value)
                for key, value in data.items()
            }
        else:
            raise Exception(
                'Trying to deserialize an unsupported type: {}'.format(
                    template_type._name))
    elif template_type == str or issubclass(template_type, str):
        instance = data
    elif template_type == int or issubclass(template_type, int):
        instance = int(data)
    elif template_type == bool or issubclass(template_type, bool):
        instance = bool(data)
    elif type(template_type) == EnumMeta:
        if type(data) == dict:
            instance = template_type(data.get('_value_'))
        else:
            instance = template_type(data)
    elif template_type == datetime:
        if type(data) == int:
            instance = datetime.fromtimestamp(data / 1000)
        else:
            instance = parser.parse(data)

    # Handle everything else by first instantiating the class, then adding
    # all of the sub-elements, recursively calling from_json on them.
    else:
        instance = template_type()
        for field, field_type in annotations.items():
            value = data.get(field)
            setattr(instance, field, from_json(field_type, value))

    return instance
