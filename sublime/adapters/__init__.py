from typing import Any, List, Set, Optional, Type

from .adapter_base import Adapter, CachingAdapter
from .api_objects import Playlist, PlaylistDetails
from .filesystem import FilesystemAdapter
from .subsonic import SubsonicAdapter


class AdapterManager():
    class _AdapterManagerInternal:
        pass

    _instance: Optional[_AdapterManagerInternal] = None

    available_adapters: Set[Any] = {FilesystemAdapter, SubsonicAdapter}

    @staticmethod
    def register_adapter(adapter_class: Type):
        if not issubclass(adapter_class, Adapter):
            raise TypeError(
                'Attempting to register a class that is not an adapter.')
        AdapterManager.available_adapters.add(adapter_class)

    def __init__(self):
        """
        This should not ever be called. You should only ever use the static
        methods on this class.
        """
        raise Exception(
            "Cannot instantiate AdapterManager. Only use the static methods "
            "on the class.")

    @staticmethod
    def reset():
        AdapterManager._instance = AdapterManager._AdapterManagerInternal()

    @staticmethod
    def get_playlists() -> List[Playlist]:
        return []

    @staticmethod
    def get_playlist_details(playlist_id: str) -> PlaylistDetails:
        raise NotImplementedError()


__all__ = ('Adapter', 'AdapterManager', 'CachingAdapter')
