import abc
import copy
import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    cast,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

try:
    import keyring

    keyring_imported = True
except Exception:
    keyring_imported = False

from .api_objects import (
    Album,
    Artist,
    Directory,
    Genre,
    Playlist,
    PlayQueue,
    SearchResult,
    Song,
)
from ..util import this_decade


class SongCacheStatus(Enum):
    """
    Represents the cache state of a given song.

    * :class:`SongCacheStatus.NOT_CACHED` -- indicates that the song is not cached on
      disk.
    * :class:`SongCacheStatus.CACHED` -- indicates that the song is cached on disk.
    * :class:`SongCacheStatus.PERMANENTLY_CACHED` -- indicates that the song is cached
      on disk and will not be deleted when the cache gets too big.
    * :class:`SongCacheStatus.DOWNLOADING` -- indicates that the song is being
      downloaded.
    * :class:`SongCacheStatus.CACHED_STALE` -- indicates that the song is cached on
      disk, but has been invalidated.
    """

    NOT_CACHED = 0
    CACHED = 1
    PERMANENTLY_CACHED = 2
    DOWNLOADING = 3
    CACHED_STALE = 4


@dataclass
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
    year_range: Tuple[int, int] = this_decade()
    genre: Genre = _Genre("Rock")

    _strhash: Optional[str] = None

    def strhash(self) -> str:
        """
        Returns a deterministic hash of the query as a string.

        >>> AlbumSearchQuery(
        ...     AlbumSearchQuery.Type.YEAR_RANGE, year_range=(2018, 2019)
        ... ).strhash()
        '275c58cac77c5ea9ccd34ab870f59627ab98e73c'
        >>> AlbumSearchQuery(
        ...     AlbumSearchQuery.Type.YEAR_RANGE, year_range=(2018, 2020)
        ... ).strhash()
        'e5dc424e8fc3b7d9ff7878b38cbf2c9fbdc19ec2'
        >>> AlbumSearchQuery(AlbumSearchQuery.Type.STARRED).strhash()
        '861b6ff011c97d53945ca89576463d0aeb78e3d2'
        """
        if not self._strhash:
            hash_tuple: Tuple[Any, ...] = (self.type.value,)
            if self.type == AlbumSearchQuery.Type.YEAR_RANGE:
                hash_tuple += (self.year_range,)
            elif self.type == AlbumSearchQuery.Type.GENRE:
                hash_tuple += (self.genre.name,)
            self._strhash = hashlib.sha1(bytes(str(hash_tuple), "utf8")).hexdigest()
        return self._strhash


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


KEYRING_APP_NAME = "app.sublimemusic.SublimeMusic"


class ConfigurationStore(dict):
    """
    This defines an abstract store for all configuration parameters for a given Adapter.
    """

    MOCK = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._changed_secrets_store = {}

    def __repr__(self) -> str:
        values = ", ".join(f"{k}={v!r}" for k, v in sorted(self.items()))
        return f"ConfigurationStore({values})"

    def clone(self) -> "ConfigurationStore":
        configuration_store = ConfigurationStore(**copy.deepcopy(self))
        configuration_store._changed_secrets_store = copy.deepcopy(
            self._changed_secrets_store
        )
        return configuration_store

    def persist_secrets(self):
        if not keyring_imported or ConfigurationStore.MOCK:
            return

        for key, secret in self._changed_secrets_store.items():
            try:
                password_id = None
                if password_type_and_id := self.get(key):
                    if cast(List[str], password_type_and_id)[0] == "keyring":
                        password_id = password_type_and_id[1]

                if password_id is None:
                    password_id = str(uuid.uuid4())

                keyring.set_password(KEYRING_APP_NAME, password_id, secret)
                self[key] = ["keyring", password_id]
            except Exception:
                return

    def get_secret(self, key: str) -> Optional[str]:
        """
        Get the secret value in the store with the given key. This will retrieve the
        secret from whatever is configured as the underlying secret storage mechanism so
        you don't have to deal with secret storage yourself.
        """
        if secret := self._changed_secrets_store.get(key):
            return secret

        value = self.get(key)
        if not isinstance(value, list) or len(value) != 2:
            return None

        storage_type, storage_key = value
        return {
            "keyring": lambda: keyring.get_password(KEYRING_APP_NAME, storage_key),
            "plaintext": lambda: storage_key,
        }[storage_type]()

    def set_secret(self, key: str, value: str = None):
        """
        Set the secret value of the given key in the store. This should be used for
        things such as passwords or API tokens. When :class:`persist_secrets` is called,
        the secrets will be stored in whatever is configured as the underlying secret
        storage mechanism so you don't have to deal with secret storage yourself.
        """
        self._changed_secrets_store[key] = value
        self[key] = ["plaintext", value]


@dataclass
class UIInfo:
    name: str
    description: str
    icon_basename: str
    icon_dir: Optional[Path] = None

    def icon_name(self) -> str:
        return f"{self.icon_basename}-symbolic"

    def status_icon_name(self, status: str) -> str:
        return f"{self.icon_basename}-{status.lower()}-symbolic"


class Adapter(abc.ABC):
    """
    Defines the interface for a Sublime Music Adapter.

    All functions that actually retrieve data have a corresponding: ``can_``-prefixed
    property (which can be dynamic) which specifies whether or not the adapter supports
    that operation at the moment.
    """

    # Configuration and Initialization Properties
    # These functions determine how the adapter can be configured and how to
    # initialize the adapter given those configuration values.
    # ==================================================================================
    @staticmethod
    @abc.abstractmethod
    def get_ui_info() -> UIInfo:
        """
        :returns: A :class:`UIInfo` object.
        """

    @staticmethod
    @abc.abstractmethod
    def get_configuration_form(config_store: ConfigurationStore) -> Gtk.Box:
        """
        This function should return a :class:`Gtk.Box` that gets any inputs required
        from the user and uses the given ``config_store`` to store the configuration
        values.

        The ``Gtk.Box`` must expose a signal with the name ``"config-valid-changed"``
        which returns a single boolean value indicating whether or not the configuration
        is valid.

        If you don't want to implement all of the GTK logic yourself, and just want a
        simple form, then you can use the :class:`ConfigureServerForm` class to generate
        a form in a declarative manner.
        """

    @staticmethod
    @abc.abstractmethod
    def migrate_configuration(config_store: ConfigurationStore):
        """
        This function allows the adapter to migrate its configuration.
        """

    @abc.abstractmethod
    def __init__(self, config_store: ConfigurationStore, data_directory: Path):
        """
        This function should be overridden by inheritors of :class:`Adapter` and should
        be used to do whatever setup is required for the adapter.

        This should do the bare minimum to get things set up, since this blocks the main
        UI loop. If you need to do longer initialization, use the :class:`initial_sync`
        function.

        :param config: The adapter configuration. The keys of are the configuration
            parameter names as defined by the return value of the
            :class:`get_config_parameters` function. The values are the actual value of
            the configuration parameter.
        :param data_directory: the directory where the adapter can store data.  This
            directory is guaranteed to exist.
        """

    @abc.abstractmethod
    def initial_sync(self):
        """
        Perform any operations that are required to get the adapter functioning
        properly. For example, this function can be used to wait for an initial ping to
        come back from the server.
        """

    @abc.abstractmethod
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
    @staticmethod
    def can_be_ground_truth() -> bool:
        """
        Whether or not this adapter can be used as a ground truth adapter.
        """
        return True

    # Network Properties
    # These properties determine whether or not the adapter requires connection over a
    # network and whether the underlying server can be pinged.
    # ==================================================================================
    @property
    def is_networked(self) -> bool:
        """
        Whether or not this adapter operates over the network. This will be used to
        determine whether or not some of the offline/online management features should
        be enabled.
        """
        return True

    def on_offline_mode_change(self, offline_mode: bool):
        """
        This function should be used to handle any operations that need to be performed
        when Sublime Music goes from online to offline mode or vice versa.
        """

    @property
    @abc.abstractmethod
    def ping_status(self) -> bool:
        """
        If the adapter :class:`is_networked`, then this function should return whether
        or not the server can be pinged. This function must provide an answer
        *instantly* (it can't actually ping the server). This function is called *very*
        often, and even a few milliseconds delay stacks up quickly and can block the UI
        thread.

        One option is to ping the server every few seconds and cache the result of the
        ping and use that as the result of this function.
        """

    # Availability Properties
    # These properties determine if what things the adapter can be used to do. These
    # properties can be dynamic based on things such as underlying API version, or other
    # factors like that. However, these properties should not be dependent on the
    # connection state. After the initial sync, these properties are expected to be
    # constant.
    # ==================================================================================
    # Playlists
    @property
    def can_get_playlists(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_playlist`.
        """
        return False

    @property
    def can_get_playlist_details(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_playlist_details`.
        """
        return False

    @property
    def can_create_playlist(self) -> bool:
        """
        Whether or not the adapter supports :class:`create_playlist`.
        """
        return False

    @property
    def can_update_playlist(self) -> bool:
        """
        Whether or not the adapter supports :class:`update_playlist`.
        """
        return False

    @property
    def can_delete_playlist(self) -> bool:
        """
        Whether or not the adapter supports :class:`delete_playlist`.
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
        return ()

    @property
    def can_get_cover_art_uri(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_cover_art_uri`.
        """
        return False

    @property
    def can_get_song_file_uri(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_song_file_uri`.
        """
        return False

    @property
    def can_get_song_stream_uri(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_song_stream_uri`.
        """
        return False

    # Songs
    @property
    def can_get_song_details(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_song_details`.
        """
        return False

    @property
    def can_scrobble_song(self) -> bool:
        """
        Whether or not the adapter supports :class:`scrobble_song`.
        """
        return False

    # Artists
    @property
    def supported_artist_query_types(self) -> Set[AlbumSearchQuery.Type]:
        """
        A set of the query types that this adapter can service.

        :returns: A set of :class:`AlbumSearchQuery.Type` objects.
        """
        return set()

    @property
    def can_get_artists(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_aritsts`.
        """
        return False

    @property
    def can_get_artist(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_aritst`.
        """
        return False

    @property
    def can_get_ignored_articles(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_ignored_articles`.
        """
        return False

    # Albums
    @property
    def can_get_albums(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_albums`.
        """
        return False

    @property
    def can_get_album(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_album`.
        """
        return False

    # Browse directories
    @property
    def can_get_directory(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_directory`.
        """
        return False

    # Genres
    @property
    def can_get_genres(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_genres`.
        """
        return False

    # Play Queue
    @property
    def can_get_play_queue(self) -> bool:
        """
        Whether or not the adapter supports :class:`get_play_queue`.
        """
        return False

    @property
    def can_save_play_queue(self) -> bool:
        """
        Whether or not the adapter supports :class:`save_play_queue`.
        """
        return False

    # Search
    @property
    def can_search(self) -> bool:
        """
        Whether or not the adapter supports :class:`search`.
        """
        return False

    # Data Retrieval Methods
    # These properties determine if what things the adapter can be used to do
    # at the current moment.
    # ==================================================================================
    def get_playlists(self) -> Sequence[Playlist]:
        """
        Get a list of all of the playlists known by the adapter.

        :returns: A list of all of the
            :class:`sublime_music.adapter.api_objects.Playlist` objects known to the
            adapter.
        """
        raise self._check_can_error("get_playlists")

    def get_playlist_details(self, playlist_id: str) -> Playlist:
        """
        Get the details for the given ``playlist_id``. If the playlist_id does not
        exist, then this function should throw an exception.

        :param playlist_id: The ID of the playlist to retrieve.
        :returns: A :class:`sublime_music.adapter.api_objects.Play` object for the given
            playlist.
        """
        raise self._check_can_error("get_playlist_details")

    def create_playlist(
        self, name: str, songs: Sequence[Song] = None
    ) -> Optional[Playlist]:
        """
        Creates a playlist of the given name with the given songs.

        :param name: The human-readable name of the playlist.
        :param songs: A list of songs that should be included in the playlist.
        :returns: A :class:`sublime_music.adapter.api_objects.Playlist` object for the
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
    ) -> Playlist:
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
        :returns: A :class:`sublime_music.adapter.api_objects.Playlist` object for the
            updated playlist.
        """
        raise self._check_can_error("update_playlist")

    def delete_playlist(self, playlist_id: str):
        """
        Deletes the given playlist.

        :param playlist_id: The human-readable name of the playlist.
        """
        raise self._check_can_error("delete_playlist")

    def get_cover_art_uri(self, cover_art_id: str, scheme: str, size: int) -> str:
        """
        Get a URI for a given ``cover_art_id``.

        :param cover_art_id: The song, album, or artist ID.
        :param scheme: The URI scheme that should be returned. It is guaranteed that
            ``scheme`` will be one of the schemes returned by
            :class:`supported_schemes`.
        :param size: The size of image to return. Denotes the max width or max height
            (whichever is larger).
        :returns: The URI as a string.
        """
        raise self._check_can_error("get_cover_art_uri")

    def get_song_file_uri(self, song_id: str, schemes: Iterable[str]) -> str:
        """
        Get a URI for a given song. This URI must give the full file.

        :param song_id: The ID of the song to get a URI for.
        :param schemes: A set of URI schemes that can be returned. It is guaranteed that
            all of the items in ``schemes`` will be one of the schemes returned by
            :class:`supported_schemes`.
        :returns: The URI for the given song.
        """
        raise self._check_can_error("get_song_file_uri")

    def get_song_stream_uri(self, song_id: str) -> str:
        """
        Get a URI for streaming the given song.

        :param song_id: The ID of the song to get the stream URI for.
        :returns: the stream URI for the given song.
        """
        raise self._check_can_error("get_song_stream_uri")

    def get_song_details(self, song_id: str) -> Song:
        """
        Get the details for a given song ID.

        :param song_id: The ID of the song to get the details for.
        :returns: The :class:`sublime_music.adapters.api_objects.Song`.
        """
        raise self._check_can_error("get_song_details")

    def scrobble_song(self, song: Song):
        """
        Scrobble the given song.

        :params song: The :class:`sublime_music.adapters.api_objects.Song` to scrobble.
        """
        raise self._check_can_error("scrobble_song")

    def get_artists(self) -> Sequence[Artist]:
        """
        Get a list of all of the artists known to the adapter.

        :returns: A list of all of the :class:`sublime_music.adapter.api_objects.Artist`
            objects known to the adapter.
        """
        raise self._check_can_error("get_artists")

    def get_artist(self, artist_id: str) -> Artist:
        """
        Get the details for the given artist ID.

        :param artist_id: The ID of the artist to get the details for.
        :returns: The :classs`sublime_music.adapters.api_objects.Artist`
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
        self, query: AlbumSearchQuery, sort_direction: str = "ascending"
    ) -> Sequence[Album]:
        """
        Get a list of all of the albums known to the adapter for the given query.

        .. note::

           This request is not paged. You should do any page management to get all of
           the albums matching the query internally.

        :param query: An :class:`AlbumSearchQuery` object representing the types of
            albums to return.
        :returns: A list of all of the :class:`sublime_music.adapter.api_objects.Album`
            objects known to the adapter that match the query.
        """
        raise self._check_can_error("get_albums")

    def get_album(self, album_id: str) -> Album:
        """
        Get the details for the given album ID.

        :param album_id: The ID of the album to get the details for.
        :returns: The :classs`sublime_music.adapters.api_objects.Album`
        """
        raise self._check_can_error("get_album")

    def get_directory(self, directory_id: str) -> Directory:
        """
        Return a Directory object representing the song files and directories in the
        given directory. This may not make sense for your adapter (for example, if
        there's no actual underlying filesystem). In that case, make sure to set
        :class:`can_get_directory` to ``False``.

        :param directory_id: The directory to retrieve. If the special value ``"root"``
            is given, the adapter should list all of the directories at the root of the
            filesystem tree.
        :returns: A list of the :class:`sublime_music.adapter.api_objects.Directory` and
            :class:`sublime_music.adapter.api_objects.Song` objects in the given
            directory.
        """
        raise self._check_can_error("get_directory")

    def get_genres(self) -> Sequence[Genre]:
        """
        Get a list of the genres known to the adapter.

        :returns: A list of all of the :classs`sublime_music.adapter.api_objects.Genre`
            objects known to the adapter.
        """
        raise self._check_can_error("get_genres")

    def get_play_queue(self) -> Optional[PlayQueue]:
        """
        Returns the state of the play queue for this user. This could be used to restore
        the play queue from the cloud.

        :returns: The cloud-saved play queue as a
            :class:`sublime_music.adapter.api_objects.PlayQueue` object.
        """
        raise self._check_can_error("get_play_queue")

    def save_play_queue(
        self,
        song_ids: Sequence[str],
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
        :returns: A :class:`sublime_music.adapters.api_objects.SearchResult` object
            representing the results of the search.
        """
        raise self._check_can_error("search")

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

    ping_status = True

    # Data Ingestion Methods
    # ==================================================================================
    class CachedDataKey(Enum):
        ALBUM = "album"
        ALBUMS = "albums"
        ARTIST = "artist"
        ARTISTS = "artists"
        COVER_ART_FILE = "cover_art_file"
        DIRECTORY = "directory"
        GENRE = "genre"
        GENRES = "genres"
        IGNORED_ARTICLES = "ignored_articles"
        PLAYLIST_DETAILS = "get_playlist_details"
        PLAYLISTS = "get_playlists"
        SEARCH_RESULTS = "search_results"
        SONG = "song"
        SONG_FILE = "song_file"
        SONG_FILE_PERMANENT = "song_file_permanent"

        # These are only for clearing the cache, and will only do deletion
        ALL_SONGS = "all_songs"
        EVERYTHING = "everything"

    @abc.abstractmethod
    def ingest_new_data(self, data_key: CachedDataKey, param: Optional[str], data: Any):
        """
        This function will be called after the fallback, ground-truth adapter returns
        new data. This normally will happen if this adapter has a cache miss or if the
        UI forces retrieval from the ground-truth adapter.

        :param data_key: the type of data to be ingested.
        :param param: a string that uniquely identify the data to be ingested. For
            example, with playlist details, this will be the playlist ID. If that
            playlist ID is requested again, the adapter should service that request, but
            it should not service a request for a different playlist ID.

            For the playlist list, this will be none since there are no parameters to
            that request.
        :param data: the data that was returned by the ground truth adapter.
        """

    @abc.abstractmethod
    def invalidate_data(self, data_key: CachedDataKey, param: Optional[str]):
        """
        This function will be called if the adapter should invalidate some of its data.
        This should not destroy the invalidated data. If invalid data is requested, a
        ``CacheMissError`` should be thrown, but the old data should be included in the
        ``partial_data`` field of the error.

        :param data_key: the type of data to be invalidated.
        :param params: the parameters that uniquely identify the data to be invalidated.
            For example, with playlist details, this will be the playlist ID.

            For the playlist list, this will be none since there are no parameters to
            that request.
        """

    @abc.abstractmethod
    def delete_data(self, data_key: CachedDataKey, param: Optional[str]):
        """
        This function will be called if the adapter should delete some of its data.
        This should destroy the data. If the deleted data is requested, a
        ``CacheMissError`` should be thrown with no data in the ``partial_data`` field.

        :param data_key: the type of data to be deleted.
        :param params: the parameters that uniquely identify the data to be invalidated.
            For example, with playlist details, this will be the playlist ID.

            For the playlist list, this will be none since there are no parameters to
            that request.
        """

    # Cache-Specific Methods
    # ==================================================================================
    @abc.abstractmethod
    def get_cached_statuses(
        self, song_ids: Sequence[str]
    ) -> Dict[str, SongCacheStatus]:
        """
        Returns the cache statuses for the given list of songs. See the
        :class:`SongCacheStatus` documentation for more details about what each status
        means.

        :params songs: The songs to get the cache status for.
        :returns: A dictionary of song ID to :class:`SongCacheStatus` objects for each
            of the songs.
        """
