import abc
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Sequence,
    Optional,
    Tuple,
    Type,
    Union,
)

from .api_objects import (
    Playlist,
    PlaylistDetails,
)


class CacheMissError(Exception):
    """
    This exception should be thrown by caching adapters when the request
    data is not available or is invalid.
    """
    pass


@dataclass
class ConfigParamDescriptor:
    """
    Describes a parameter that can be used to configure an adapter. The
    :class:`description`, :class:`required` and :class:`default:` should be
    self-evident as to what they do.

    The :class:`type` must be one of the following:

    * The literal type ``str``: corresponds to a freeform text entry field in
      the UI.
    * The literal type ``bool``: corresponds to a checkbox in the UI.
    * The literal type ``int``: corresponds to a numeric input in the UI.
    * The literal string ``"password"``: corresponds to a password entry field
      in the UI.
    * The literal string ``"option"``: corresponds to dropdown in the UI.

    The :class:`numeric_bounds` parameter only has an effect if the
    :class:`type` is `int`. It specifies the min and max values that the UI
    control can have.

    The :class:`numeric_step` parameter only has an effect if the :class:`type`
    is `int`. It specifies the step that will be taken using the "+" and "-"
    buttons on the UI control (if supported).

    The :class:`options` parameter only has an effect if the :class:`type` is
    ``"option"``. It specifies the list of options that will be available in
    the dropdown in the UI.
    """
    type: Union[Type, str]
    description: str
    required: bool = True
    default: Any = None
    numeric_bounds: Optional[Tuple[int, int]] = None
    numeric_step: Optional[int] = None
    options: Optional[Iterable[str]] = None


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
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        """
        Specifies the settings which can be configured for the adapter.

        :returns: An dictionary where the keys are the name of the
            configuration paramter and the values are the
            :class:`ConfigParamDescriptor` object corresponding to that
            configuration parameter. The order of the keys in the dictionary
            correspond to the order that the configuration parameters will be
            shown in the UI.
        """

    @staticmethod
    @abc.abstractmethod
    def verify_configuration(
            config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Specifies a function for verifying whether or not the config is valid.

        :param config: The adapter configuration. The keys of are the
            configuration parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual
            value of the configuration parameter. It is guaranteed that all
            configuration parameters that are marked as required will have a
            value in ``config``.

        :returns: A dictionary containing varification errors. The keys of the
            returned dictionary should be the same as the passed in via the
            ``config`` parameter. The values should be strings describing why
            the corresponding value in the ``config`` dictionary is invalid.

            Not all keys need be returned (for example, if there's no error for
            a given configuration parameter), and returning `None` indicates no
            error.
        """

    @abc.abstractmethod
    def __init__(self, config: dict, data_directory: Path):
        """
        This function should be overridden by inheritors of
        :class:`Adapter` and should be used to do whatever setup is
        required for the adapter.

        :param config: The adapter configuration. The keys of are the
            configuration parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual
            value of the configuration parameter.
        :param data_directory: the directory where the adapter can store data.
            This directory is guaranteed to exist.
        """

    def shutdown(self):
        """
        This function is called when the app is being closed or the server is
        changing. This should be used to clean up anything that is necessary
        such as writing a cache to disk, disconnecting from a server, etc.
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
        this is ``False``, none of the other data retrieval functions are
        expected to work.

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
    def get_playlists(self) -> Sequence[Playlist]:
        """
        Gets a list of all of the :class:`sublime.adapter.api_objects.Playlist`
        objects known to the adapter.
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

        :param config: The adapter configuration. The keys of are the
            configuration parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual
            value of the configuration parameter.
        :param data_directory: the directory where the adapter can store data.
            This directory is guaranteed to exist.
        :param is_cache: whether or not the adapter is being used as a cache.
        """

    # Data Ingestion Methods
    # =========================================================================
    @abc.abstractmethod
    def ingest_new_data(
        self,
        function_name: str,
        params: Tuple[Any, ...],
        data: Any,
    ):
        """
        This function will be called after the fallback, ground-truth adapter
        returns new data. This normally will happen if this adapter has a cache
        miss or if the UI forces retrieval from the ground-truth adapter.

        :param function_name: the name of the function that was called on the
            ground truth adapter.
        :param params: the parameters that were passed to the function on the
            ground truth adapter.
        :param data: the data that was returned by the ground truth adapter.
        """
