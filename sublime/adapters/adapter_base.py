import abc
from typing import Any, Dict, List, Tuple
from pathlib import Path

from .api_objects import (Playlist, PlaylistDetails)


class AdapterCacheMiss(Exception):
    """
    This exception should be thrown by caching adapters when the request
    data is not available or is invalid.
    """
    pass


class Adapter(abc.ABC):
    """
    Defines the interface for a Sublime Music Adapter.

    All functions that actually retrieve data have a corresponding:
    ``can_``-prefixed property (which can be dynamic) which specifies whether
    or not the adapter supports that operation at the moment.
    """
    # Configuration and Initialization Properties
    # These properties determine how the adapter can be configured and how to
    # initialize the adapter given those configuration values.
    # =========================================================================
    @staticmethod
    @abc.abstractmethod
    def get_config_parameters() -> List[Tuple[str, str]]:  # TODO fix
        """
        Specifies the settings which can be configured for the adapter.

        Tuples of (config_key, parameter_config)
        The config_key gets used in the config dict in __init__

        TODO
        """

    @staticmethod
    @abc.abstractmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, str]:
        """
        Specifies a function for verifying whether or not a config is valid.

        Return a dict of field: ('verification error' OR None)

        TODO
        """

    @abc.abstractmethod
    def __init__(self, config: dict, data_directory: Path):
        """
        This function should be overridden by inheritors of
        :class:`Adapter` and should be used to do whatever setup is
        required for the adapter.

        :param config: TODO
        :param data_directory: the directory where the adapter can store data
        """

    # Usage Properties
    # These properties determine how the adapter can be used and how quickly
    # data can be expected from this adapter.
    # =========================================================================
    @property
    def can_be_cached(self) -> bool:
        """
        Specifies whether or not this adapter can be used as the ground-truth
        adapter behind a caching adapter.

        The default is ``True``, since most adapters will want to take
        advantage of the built-in filesystem cache.
        """
        return True

    # Availability Properties
    # These properties determine if what things the adapter can be used to do
    # at the current moment.
    # =========================================================================
    @property
    @abc.abstractmethod
    def can_service_requests(self) -> bool:
        """
        Specifies whether or not the adapter can currently service requests. If
        this is ``False``, none of the other functions are expected to work.

        For example, if your adapter requires access to an external service,
        use this function to determine if it is currently possible to connect
        to that external service.
        """

    @property
    def can_get_playlists(self) -> bool:
        """
        Whether :class:`get_playlist` can be called on the adapter right now.
        """
        return False

    @property
    def can_get_playlist_details(self) -> bool:
        """
        Whether :class:`get_playlist_details` can be called on the adapter
        right now.
        """
        return False

    # Data Retrieval Methods
    # These properties determine if what things the adapter can be used to do
    # at the current moment.
    # =========================================================================
    def get_playlists(self) -> List[Playlist]:
        """
        Gets a list of all of the :class:`Playlist` objects known to the
        adapter.
        """
        raise self._check_can_error('get_playlists')

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        """
        Gets the details about the given ``playlist_id``. If the playlist_id
        does not exist, then this function should throw an exception.

        :param playlist_id: The ID of the playlist to retrieve.
        """
        raise self._check_can_error('get_playlist_details')

    @staticmethod
    def _check_can_error(method_name: str) -> NotImplementedError:
        return NotImplementedError(
            f'Adapter.{method_name} called. '
            'Did you forget to check that can_{method_name} is True?')


class CachingAdapter(Adapter):
    """
    Defines an adapter that can be used as a cache for another adapter.

    A caching adapter sits "in front" of a non-caching adapter and the UI
    will attempt to retrieve the data from the caching adapter before
    retrieving it from the non-caching adapter. (The exception is when the
    UI requests that the data come directly from the ground truth adapter,
    in which case the cache will be bypassed.)

    Caching adapters *must* be able to service requests instantly, or
    nearly instantly (in most cases, this meanst the data must come
    directly from the local filesystem).
    """
    @abc.abstractmethod
    def __init__(
        self,
        config: dict,
        data_directory: Path,
        is_cache: bool = False,
    ):
        """
        This function should be overridden by inheritors of
        :class:`CachingAdapter` and should be used to do whatever setup is
        required for the adapter.

        :param config: TODO
        :param data_directory: the directory where the adapter can store data
        :param is_cache: whether or not the adapter is being used as a cache
        """

    # Data Ingestion Methods
    # =========================================================================
    @abc.abstractmethod
    def ingest_new_data(self):  # TODO: actually ingest data
        """
        This function will be called after the fallback, ground-truth adapter
        returns new data. This normally will happen if this adapter has a cache
        miss or if the UI forces retrieval from the ground-truth adapter.
        """
