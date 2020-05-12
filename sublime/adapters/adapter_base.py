import abc
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

from .api_objects import (
    Album,
    Artist,
    Genre,
    Playlist,
    PlaylistDetails,
    PlayQueue,
    SearchResult,
    Song,
)


class SongCacheStatus(Enum):
    """
    Represents the cache state of a given song.

    * :class:`SongCacheStatus.NOT_CACHED` -- indicates
    * :class:`SongCacheStatus.CACHED` -- indicates
    * :class:`SongCacheStatus.PERMANENTLY_CACHED` -- indicates
    * :class:`SongCacheStatus.DOWNLOADING` -- indicates
    """

    NOT_CACHED = 0
    CACHED = 1
    PERMANENTLY_CACHED = 2
    DOWNLOADING = 3


@dataclass(frozen=True)
class AlbumSearchQuery:
    """
    Represents a query for getting albums from an adapter. The UI will request the
    albums in pages.

    **Fields:**

    * :class:`AlbumSearchQuery.type` -- the query :class:`AlbumSearchQuery.Type`
    * :class:`AlbumSearchQuery.year_range` -- (guaranteed to only exist if ``type`` is
      :class:`AlbumSearchQuery.Type.YEAR_RANGE`) a tuple with the lower and upper bound
      (inclusive) of the album years to return
    * :class:`AlbumSearchQuery.genre` -- (guaranteed to only exist if the ``type`` is
      :class:`AlbumSearchQuery.Type.GENRE`) return albums of the given genre
    """

    class _Genre(Genre):
        def __init__(self, name: str):
            self.name = name

    class Type(Enum):
        """
        Represents a type of query. Use :class:`Adapter.supported_artist_query_types` to
        specify what search types your adapter supports.

        * :class:`AlbumSearchQuery.Type.RANDOM` -- return a random set of albums
        * :class:`AlbumSearchQuery.Type.NEWEST` -- return the most recently added albums
        * :class:`AlbumSearchQuery.Type.RECENT` -- return the most recently played
          albums
        * :class:`AlbumSearchQuery.Type.STARRED` -- return only starred albums
        * :class:`AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME` -- return the albums
          sorted alphabetically by album name
        * :class:`AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST` -- return the albums
          sorted alphabetically by artist name
        * :class:`AlbumSearchQuery.Type.YEAR_RANGE` -- return albums in the given year
          range
        * :class:`AlbumSearchQuery.Type.GENRE` -- return songs of the given genre
        """

        RANDOM = 0
        NEWEST = 1
        FREQUENT = 2
        RECENT = 3
        STARRED = 4
        ALPHABETICAL_BY_NAME = 5
        ALPHABETICAL_BY_ARTIST = 6
        YEAR_RANGE = 7
        GENRE = 8

    type: Type
    year_range: Tuple[int, int] = (2010, 2020)
    genre: Genre = _Genre("Rock")


class CacheMissError(Exception):
    """
    This exception should be thrown by caching adapters when the request data is not
    available or is invalid. If some of the data is available, but not all of it, the
    ``partial_data`` parameter should be set with the partial data. If the ground truth
    adapter can't service the request, or errors for some reason, the UI will try to
    populate itself with the partial data returned in this exception (with the necessary
    error text to inform the user that retrieval from the ground truth adapter failed).
    """

    def __init__(self, *args, partial_data: Any = None):
        """
        Create a :class:`CacheMissError` exception.

        :param args: arguments to pass to the :class:`BaseException` base class.
        :param partial_data: the actual partial data for the UI to use in case of ground
            truth adapter failure.
        """
        self.partial_data = partial_data
        super().__init__(*args)


@dataclass
class ConfigParamDescriptor:
    """
    Describes a parameter that can be used to configure an adapter. The
    :class:`description`, :class:`required` and :class:`default:` should be self-evident
    as to what they do.

    The :class:`type` must be one of the following:

    * The literal type ``str``: corresponds to a freeform text entry field in the UI.
    * The literal type ``bool``: corresponds to a checkbox in the UI.
    * The literal type ``int``: corresponds to a numeric input in the UI.
    * The literal string ``"password"``: corresponds to a password entry field in the
      UI.
    * The literal string ``"option"``: corresponds to dropdown in the UI.

    The :class:`numeric_bounds` parameter only has an effect if the :class:`type` is
    `int`. It specifies the min and max values that the UI control can have.

    The :class:`numeric_step` parameter only has an effect if the :class:`type` is
    `int`. It specifies the step that will be taken using the "+" and "-" buttons on the
    UI control (if supported).

    The :class:`options` parameter only has an effect if the :class:`type` is
    ``"option"``. It specifies the list of options that will be available in the
    dropdown in the UI.
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

    All functions that actually retrieve data have a corresponding: ``can_``-prefixed
    property (which can be dynamic) which specifies whether or not the adapter supports
    that operation at the moment.
    """

    # Configuration and Initialization Properties
    # These properties determine how the adapter can be configured and how to
    # initialize the adapter given those configuration values.
    # ==================================================================================
    @staticmethod
    @abc.abstractmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        """
        Specifies the settings which can be configured for the adapter.

        :returns: An dictionary where the keys are the name of the configuration
            paramter and the values are the :class:`ConfigParamDescriptor` object
            corresponding to that configuration parameter. The order of the keys in the
            dictionary correspond to the order that the configuration parameters will be
            shown in the UI.
        """

    @staticmethod
    @abc.abstractmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Specifies a function for verifying whether or not the config is valid.

        :param config: The adapter configuration. The keys of are the configuration
            parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual value of
            the configuration parameter. It is guaranteed that all configuration
            parameters that are marked as required will have a value in ``config``.

        :returns: A dictionary containing varification errors. The keys of the returned
            dictionary should be the same as the passed in via the ``config`` parameter.
            The values should be strings describing why the corresponding value in the
            ``config`` dictionary is invalid.

            Not all keys need be returned (for example, if there's no error for a given
            configuration parameter), and returning `None` indicates no error.
        """

    @abc.abstractmethod
    def __init__(self, config: dict, data_directory: Path):
        """
        This function should be overridden by inheritors of :class:`Adapter` and should
        be used to do whatever setup is required for the adapter.

        :param config: The adapter configuration. The keys of are the configuration
            parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual value of
            the configuration parameter.
        :param data_directory: the directory where the adapter can store data.  This
            directory is guaranteed to exist.
        """

    def shutdown(self):
        """
        This function is called when the app is being closed or the server is changing.
        This should be used to clean up anything that is necessary such as writing a
        cache to disk, disconnecting from a server, etc.
        """

    # Usage Properties
    # These properties determine how the adapter can be used and how quickly
    # data can be expected from this adapter.
    # ==================================================================================
    @property
    def can_be_cached(self) -> bool:
        """
        Whether or not this adapter can be used as the ground-truth adapter behind a
        caching adapter.

        The default is ``True``, since most adapters will want to take advantage of the
        built-in filesystem cache.
        """
        return True

    @property
    def is_networked(self) -> bool:
        """
        Whether or not this adapter operates over the network. This will be used to
        determine whether or not some of the offline/online management features should
        be enabled.
        """
        return True

    # Availability Properties
    # These properties determine if what things the adapter can be used to do
    # at the current moment.
    # ==================================================================================
    @property
    @abc.abstractmethod
    def can_service_requests(self) -> bool:
        """
        Specifies whether or not the adapter can currently service requests. If this is
        ``False``, none of the other data retrieval functions are expected to work.

        This property must be server *instantly*. This function is called *very* often,
        and even a few milliseconds delay stacks up quickly and can block the UI thread.

        For example, if your adapter requires access to an external service, on option
        is to ping the server every few seconds and cache the result of the ping and use
        that as the return value of this function.
        """

    # Playlists
    @property
    def can_get_playlists(self) -> bool:
        """
        Whether :class:`get_playlist` can be called on the adapter right now.
        """
        return False

    @property
    def can_get_playlist_details(self) -> bool:
        """
        Whether :class:`get_playlist_details` can be called on the adapter right now.
        """
        return False

    @property
    def can_create_playlist(self) -> bool:
        """
        Whether :class:`create_playlist` can be called on the adapter right now.
        """
        return False

    @property
    def can_update_playlist(self) -> bool:
        """
        Whether :class:`update_playlist` can be called on the adapter right now.
        """
        return False

    @property
    def can_delete_playlist(self) -> bool:
        """
        Whether :class:`delete_playlist` can be called on the adapter right now.
        """
        return False

    # Downloading/streaming cover art and songs
    @property
    def supported_schemes(self) -> Iterable[str]:
        """
        Specifies a collection of scheme names that can be provided by the adapter for a
        given resource (song or cover art) right now.

        Examples of values that could be provided include ``http``, ``https``, ``file``,
        or ``ftp``.
        """
        # TODO actually use this
        return ()

    @property
    def can_get_cover_art_uri(self) -> bool:
        """
        Whether :class:`get_cover_art_uri` can be called on the adapter right now.
        """

    @property
    def can_stream(self) -> bool:
        """
        Whether or not the adapter can provide a stream URI right now.
        """
        return False

    @property
    def can_get_song_uri(self) -> bool:
        """
        Whether :class:`get_song_uri` can be called on the adapter right now.
        """
        return False

    # Songs
    @property
    def can_get_song_details(self) -> bool:
        """
        Whether :class:`get_song_details` can be called on the adapter right now.
        """
        return False

    @property
    def can_scrobble_song(self) -> bool:
        """
        Whether :class:`scrobble_song` can be called on the adapter right now.
        """
        return False

    # Artists
    @property
    def supported_artist_query_types(self) -> Set[AlbumSearchQuery.Type]:
        """
        A set of the query types that this adapter can service.

        :returns: A set of :class:`AlbumSearchQuery.Type` objects.
        """
        # TODO: use this
        return set()

    @property
    def can_get_artists(self) -> bool:
        """
        Whether :class:`get_aritsts` can be called on the adapter right now.
        """
        return False

    @property
    def can_get_artist(self) -> bool:
        """
        Whether :class:`get_aritst` can be called on the adapter right now.
        """
        return False

    @property
    def can_get_ignored_articles(self) -> bool:
        """
        Whether :class:`get_ignored_articles` can be called on the adapter right now.
        """
        return False

    # Albums
    @property
    def can_get_albums(self) -> bool:
        """
        Whether :class:`get_albums` can be called on the adapter right now.
        """
        return False

    @property
    def can_get_album(self) -> bool:
        """
        Whether :class:`get_album` can be called on the adapter right now.
        """
        return False

    # Misc
    @property
    def can_get_genres(self) -> bool:
        """
        Whether :class:`get_genres` can be called on the adapter right now.
        """
        return False

    # Play Queue
    @property
    def can_get_play_queue(self) -> bool:
        """
        Whether :class:`get_play_queue` can be called on the adapter right now.
        """
        return False

    @property
    def can_save_play_queue(self) -> bool:
        """
        Whether :class:`save_play_queue` can be called on the adapter right now.
        """
        return False

    # Search
    @property
    def can_search(self) -> bool:
        """
        Whether :class:`search` can be called on the adapter right now.
        """
        return False

    # Data Retrieval Methods
    # These properties determine if what things the adapter can be used to do
    # at the current moment.
    # ==================================================================================
    def get_playlists(self) -> Sequence[Playlist]:
        """
        Get a list of all of the playlists known by the adapter.

        :returns: A list of all of the :class:`sublime.adapter.api_objects.Playlist`
            objects known to the adapter.
        """
        raise self._check_can_error("get_playlists")

    def get_playlist_details(self, playlist_id: str,) -> PlaylistDetails:
        """
        Get the details for the given ``playlist_id``. If the playlist_id does not
        exist, then this function should throw an exception.

        :param playlist_id: The ID of the playlist to retrieve.
        :returns: A :class:`sublime.adapter.api_objects.PlaylistDetails` object for the
            given playlist.
        """
        raise self._check_can_error("get_playlist_details")

    def create_playlist(
        self, name: str, songs: Sequence[Song] = None,
    ) -> Optional[PlaylistDetails]:  # TODO make not optional?
        """
        Creates a playlist of the given name with the given songs.

        :param name: The human-readable name of the playlist.
        :param songs: A list of songs that should be included in the playlist.
        :returns: A :class:`sublime.adapter.api_objects.PlaylistDetails` object for the
            created playlist. If getting this information will incurr network overhead,
            then just return ``None``.
        """
        raise self._check_can_error("create_playlist")

    def update_playlist(
        self,
        playlist_id: str,
        name: str = None,
        comment: str = None,
        public: bool = None,
        song_ids: Sequence[str] = None,
    ) -> PlaylistDetails:
        """
        Updates a given playlist. If a parameter is ``None``, then it will be ignored
        and no updates will occur to that field.

        :param playlist_id: The human-readable name of the playlist.
        :param name: The human-readable name of the playlist.
        :param comment: The playlist comment.
        :param public: This is very dependent on the adapter, but if the adapter has a
            shared/public vs. not shared/private playlists concept, setting this to
            ``True`` will make the playlist shared/public.
        :param song_ids: A list of song IDs that should be included in the playlist.
        :returns: A :class:`sublime.adapter.api_objects.PlaylistDetails` object for the
            updated playlist.
        """
        raise self._check_can_error("update_playlist")

    def delete_playlist(self, playlist_id: str):
        """
        Deletes the given playlist.

        :param playlist_id: The human-readable name of the playlist.
        """
        raise self._check_can_error("delete_playlist")

    def get_cover_art_uri(self, cover_art_id: str, scheme: str) -> str:
        """
        Get a URI for a given ``cover_art_id``.

        :param cover_art_id: The song, album, or artist ID.
        :param scheme: The URI scheme that should be returned. It is guaranteed that
            ``scheme`` will be one of the schemes returned by
            :class:`supported_schemes`.
        :returns: The URI as a string.
        """
        raise self._check_can_error("get_cover_art_uri")

    def get_song_uri(self, song_id: str, scheme: str, stream: bool = False) -> str:
        """
        Get a URI for a given song.

        :param song_id: The ID of the song to get a URI for.
        :param scheme: The URI scheme that should be returned. It is guaranteed that
            ``scheme`` will be one of the schemes returned by
            :class:`supported_schemes`.
        :param stream: Whether or not the URI returned should be a stream URI. This will
            only be ``True`` if :class:`supports_streaming` returns ``True``. TODO fix
        :returns: The URI for the given song.
        """
        raise self._check_can_error("get_song_uri")

    def get_song_details(self, song_id: str) -> Song:
        """
        Get the details for a given song ID.

        :param song_id: The ID of the song to get the details for.
        :returns: The :class:`sublime.adapters.api_objects.Song`.
        """
        raise self._check_can_error("get_song_details")

    def scrobble_song(self, song: Song):
        """
        Scrobble the given song.

        :params song: The :class:`sublime.adapters.api_objects.Song` to scrobble.
        """
        raise self._check_can_error("scrobble_song")

    def get_artists(self) -> Sequence[Artist]:
        """
        Get a list of all of the artists known to the adapter.

        :returns: A list of all of the :class:`sublime.adapter.api_objects.Artist`
            objects known to the adapter.
        """
        raise self._check_can_error("get_artists")

    def get_artist(self, artist_id: str) -> Artist:
        """
        Get the details for the given artist ID.

        :param artist_id: The ID of the artist to get the details for.
        :returns: The :classs`sublime.adapters.api_objects.Artist`
        """
        raise self._check_can_error("get_artist")

    def get_ignored_articles(self) -> Set[str]:
        """
        Get the list of articles to ignore when sorting artists by name.

        :returns: A set of articles (i.e. The, A, El, La, Los) to ignore when sorting
            artists.
        """
        raise self._check_can_error("get_ignored_articles")

    def get_albums(
        self, query: AlbumSearchQuery, limit: int, offset: int
    ) -> Sequence[Album]:
        """
        Get a list of all of the albums known to the adapter for the given query.

        :param query: An :class:`AlbumSearchQuery` object representing the types of
            albums to return.
        :param limit: The maximum number of albums to return.
        :param offset: The index at whith to start returning albums (for paging).
        :returns: A list of all of the :class:`sublime.adapter.api_objects.Album`
            objects known to the adapter.
        """
        raise self._check_can_error("get_albums")

    def get_album(self, album_id: str) -> Album:
        """
        Get the details for the given album ID.

        :param album_id: The ID of the album to get the details for.
        :returns: The :classs`sublime.adapters.api_objects.Album`
        """
        raise self._check_can_error("get_album")

    def get_genres(self) -> Sequence[Genre]:
        """
        Get a list of the genres known to the adapter.

        :returns: A list of all of the :classs`sublime.adapter.api_objects.Genre`
            objects known to the adapter.
        """
        raise self._check_can_error("get_genres")

    def get_play_queue(self) -> Optional[PlayQueue]:
        """
        Returns the state of the play queue for this user. This could be used to restore
        the play queue from the cloud.

        :returns: The cloud-saved play queue as a
            :class:`sublime.adapter.api_objects.PlayQueue` object.
        """
        raise self._check_can_error("get_play_queue")

    def save_play_queue(
        self,
        song_ids: Sequence[int],
        current_song_index: int = None,
        position: timedelta = None,
    ):
        """
        Save the current play queue to the cloud.

        :param song_ids: A list of the song IDs in the queue.
        :param current_song_index: The index of the song that is currently being played.
        :param position: The current position in the song.
        """
        raise self._check_can_error("can_save_play_queue")

    def search(self, query: str) -> SearchResult:
        """
        Return search results fro the given query.

        :param query: The query string.
        :returns: A :class:`sublime.adapters.api_objects.SearchResult` object
            representing the results of the search.
        """
        raise self._check_can_error("can_save_play_queue")

    @staticmethod
    def _check_can_error(method_name: str) -> NotImplementedError:
        return NotImplementedError(
            f"Adapter.{method_name} called. "
            "Did you forget to check that can_{method_name} is True?"
        )


class CachingAdapter(Adapter):
    """
    Defines an adapter that can be used as a cache for another adapter.

    A caching adapter sits "in front" of a non-caching adapter and the UI will attempt
    to retrieve the data from the caching adapter before retrieving it from the
    non-caching adapter. (The exception is when the UI requests that the data come
    directly from the ground truth adapter, in which case the cache will be bypassed.)

    Caching adapters *must* be able to service requests instantly, or nearly instantly
    (in most cases, this means that the data must come directly from the local
    filesystem).
    """

    @abc.abstractmethod
    def __init__(self, config: dict, data_directory: Path, is_cache: bool = False):
        """
        This function should be overridden by inheritors of :class:`CachingAdapter` and
        should be used to do whatever setup is required for the adapter.

        :param config: The adapter configuration. The keys of are the configuration
            parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual value of
            the configuration parameter.
        :param data_directory: the directory where the adapter can store data.  This
            directory is guaranteed to exist.
        :param is_cache: whether or not the adapter is being used as a cache.
        """

    # Data Ingestion Methods
    # ==================================================================================
    class CachedDataKey(Enum):
        ALBUM = "album"
        ALBUMS = "albums"
        ARTIST = "artist"
        ARTISTS = "artists"
        COVER_ART_FILE = "cover_art_file"
        GENRES = "genres"
        IGNORED_ARTICLES = "ignored_articles"
        PLAYLIST_DETAILS = "get_playlist_details"
        PLAYLISTS = "get_playlists"
        SEARCH_RESULTS = "search_results"
        SONG_DETAILS = "song_details"
        SONG_FILE = "song_file"
        SONG_FILE_PERMANENT = "song_file_permanent"

    @abc.abstractmethod
    def ingest_new_data(
        self, data_key: CachedDataKey, params: Tuple[Any, ...], data: Any
    ):
        """
        This function will be called after the fallback, ground-truth adapter returns
        new data. This normally will happen if this adapter has a cache miss or if the
        UI forces retrieval from the ground-truth adapter.

        :param data_key: the type of data to be ingested.
        :param params: the parameters that uniquely identify the data to be ingested.
            For example, with playlist details, this will be a tuple containing a single
            element: the playlist ID. If that playlist ID is requested again, the
            adapter should service that request, but it should not service a request for
            a different playlist ID.
        :param data: the data that was returned by the ground truth adapter.
        """

    @abc.abstractmethod
    def invalidate_data(self, data_key: CachedDataKey, params: Tuple[Any, ...]):
        """
        This function will be called if the adapter should invalidate some of its data.
        This should not destroy the invalidated data. If invalid data is requested, a
        ``CacheMissError`` should be thrown, but the old data should be included in the
        ``partial_data`` field of the error.

        :param data_key: the type of data to be invalidated.
        :param params: the parameters that uniquely identify the data to be invalidated.
            For example, with playlist details, this will be a tuple containing a single
            element: the playlist ID.
        """

    @abc.abstractmethod
    def delete_data(self, data_key: CachedDataKey, params: Tuple[Any, ...]):
        """
        This function will be called if the adapter should delete some of its data.
        This should destroy the data. If the deleted data is requested, a
        ``CacheMissError`` should be thrown with no data in the ``partial_data`` field.

        :param data_key: the type of data to be deleted.
        :param params: the parameters that uniquely identify the data to be invalidated.
            For example, with playlist details, this will be a tuple containing a single
            element: the playlist ID.
        """

    # Cache-Specific Methods
    # ==================================================================================
    @abc.abstractmethod
    def get_cached_status(self, song: Song) -> SongCacheStatus:
        """
        Returns the cache status of a given song. See the :class:`SongCacheStatus`
        documentation for more details about what each status means.

        :params song: The song to get the cache status for.
        :returns: The :class:`SongCacheStatus` for the song.
        """
