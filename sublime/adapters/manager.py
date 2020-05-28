import hashlib
import itertools
import logging
import os
import random
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from time import sleep
from typing import (
    Any,
    Callable,
    cast,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import requests

from .adapter_base import (
    Adapter,
    AlbumSearchQuery,
    CacheMissError,
    CachingAdapter,
    SongCacheStatus,
)
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
from .filesystem import FilesystemAdapter
from .subsonic import SubsonicAdapter

REQUEST_DELAY: Optional[Tuple[float, float]] = None
if delay_str := os.environ.get("REQUEST_DELAY"):
    if "," in delay_str:
        high, low = map(float, delay_str.split(","))
        REQUEST_DELAY = (high, low)
    else:
        REQUEST_DELAY = (float(delay_str), float(delay_str))

NETWORK_ALWAYS_ERROR: bool = False
if always_error := os.environ.get("NETWORK_ALWAYS_ERROR"):
    NETWORK_ALWAYS_ERROR = True

T = TypeVar("T")


class Result(Generic[T]):
    """
    A result from a :class:`AdapterManager` function. This is effectively a wrapper
    around a :class:`concurrent.futures.Future`, but it resolves immediately if the data
    already exists.
    """

    _data: Optional[T] = None
    _future: Optional[Future] = None
    _default_value: Optional[T] = None
    _on_cancel: Optional[Callable[[], None]] = None

    def __init__(
        self,
        data_resolver: Union[T, Callable[[], T]],
        *args,
        is_download: bool = False,
        default_value: T = None,
        on_cancel: Callable[[], None] = None,
    ):
        """
        Creates a :class:`Result` object.

        :param data_resolver: the actual data, or a function that will return the actual
            data. If the latter, the function will be executed by the thread pool.
        :param is_download: whether or not this result requires a file download. If it
            does, then it uses a separate executor.
        """
        if callable(data_resolver):
            if is_download:
                self._future = AdapterManager.download_executor.submit(
                    data_resolver, *args
                )
            else:
                self._future = AdapterManager.executor.submit(data_resolver, *args)
            self._future.add_done_callback(self._on_future_complete)
        else:
            self._data = data_resolver

        self._default_value = default_value
        self._on_cancel = on_cancel

    def _on_future_complete(self, future: Future):
        try:
            self._data = future.result()
        except Exception as e:
            if self._default_value:
                self._data = self._default_value
            else:
                raise e

    def result(self) -> T:
        """
        Retrieve the actual data. If the data exists already, then return it, otherwise,
        blocking-wait on the future's result.
        """
        try:
            if self._data is not None:
                return self._data
            if self._future is not None:
                return self._future.result()

            assert 0, "AdapterManager.Result had neither _data nor _future member!"
        except Exception as e:
            if self._default_value:
                return self._default_value
            else:
                raise e

    def add_done_callback(self, fn: Callable, *args):
        """Attaches the callable ``fn`` to the future."""
        if self._future is not None:
            self._future.add_done_callback(fn, *args)
        else:
            # Run the function immediately if it's not a future.
            fn(self, *args)

    def cancel(self) -> bool:
        """Cancel the future, or do nothing if the data already exists."""
        if self._on_cancel:
            self._on_cancel()
        if self._future is not None:
            return self._future.cancel()
        return True

    @property
    def data_is_available(self) -> bool:
        """
        Whether or not the data is available at the current moment. This can be used to
        determine whether or not the UI needs to put the callback into a
        :class:`GLib.idle_add` call.
        """
        return self._data is not None


class AdapterManager:
    available_adapters: Set[Any] = {FilesystemAdapter, SubsonicAdapter}
    current_download_ids: Set[str] = set()
    download_set_lock = threading.Lock()
    executor: ThreadPoolExecutor = ThreadPoolExecutor()
    download_executor: ThreadPoolExecutor = ThreadPoolExecutor()
    is_shutting_down: bool = False
    offline_mode: bool = False

    @dataclass
    class _AdapterManagerInternal:
        ground_truth_adapter: Adapter
        caching_adapter: Optional[CachingAdapter] = None
        concurrent_download_limit: int = 5

        def __post_init__(self):
            self._download_dir = tempfile.TemporaryDirectory()
            self.download_path = Path(self._download_dir.name)
            self.download_limiter_semaphore = threading.Semaphore(
                self.concurrent_download_limit
            )

        def shutdown(self):
            self.ground_truth_adapter.shutdown()
            if self.caching_adapter:
                self.caching_adapter.shutdown()
            self._download_dir.cleanup()

    _instance: Optional[_AdapterManagerInternal] = None

    @staticmethod
    def register_adapter(adapter_class: Type):
        if not issubclass(adapter_class, Adapter):
            raise TypeError("Attempting to register a class that is not an adapter.")
        AdapterManager.available_adapters.add(adapter_class)

    def __init__(self):
        """
        This should not ever be called. You should only ever use the static methods on
        this class.
        """
        raise Exception(
            "Do not instantiate the AdapterManager. Only use the static methods on the class."  # noqa: 512
        )

    @staticmethod
    def initial_sync() -> Result[None]:
        assert AdapterManager._instance
        return Result(AdapterManager._instance.ground_truth_adapter.initial_sync)

    @staticmethod
    def ground_truth_adapter_is_networked() -> bool:
        assert AdapterManager._instance
        return AdapterManager._instance.ground_truth_adapter.is_networked

    @staticmethod
    def get_ping_status() -> bool:
        assert AdapterManager._instance
        return AdapterManager._instance.ground_truth_adapter.ping_status

    @staticmethod
    def shutdown():
        logging.info("AdapterManager shutdown start")
        AdapterManager.is_shutting_down = True
        AdapterManager.executor.shutdown()
        AdapterManager.download_executor.shutdown()
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        logging.info("AdapterManager shutdown complete")

    @staticmethod
    def reset(config: Any):

        from sublime.config import AppConfiguration

        assert isinstance(config, AppConfiguration)

        # First, shutdown the current one...
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        AdapterManager.offline_mode = config.offline_mode

        # TODO (#197): actually do stuff with the config to determine which adapters to
        # create, etc.
        assert config.server is not None
        source_data_dir = Path(config.cache_location, config.server.strhash())
        source_data_dir.joinpath("g").mkdir(parents=True, exist_ok=True)
        source_data_dir.joinpath("c").mkdir(parents=True, exist_ok=True)

        ground_truth_adapter_type = SubsonicAdapter
        ground_truth_adapter = ground_truth_adapter_type(
            {
                key: getattr(config.server, key)
                for key in ground_truth_adapter_type.get_config_parameters()
            },
            source_data_dir.joinpath("g"),
        )

        caching_adapter_type = FilesystemAdapter
        caching_adapter = None
        if caching_adapter_type and ground_truth_adapter_type.can_be_cached:
            caching_adapter = caching_adapter_type(
                {
                    key: getattr(config.server, key)
                    for key in caching_adapter_type.get_config_parameters()
                },
                source_data_dir.joinpath("c"),
                is_cache=True,
            )

        AdapterManager._instance = AdapterManager._AdapterManagerInternal(
            ground_truth_adapter,
            caching_adapter=caching_adapter,
            concurrent_download_limit=config.concurrent_download_limit,
        )

    # Data Helper Methods
    # ==================================================================================
    TAdapter = TypeVar("TAdapter", bound=Adapter)

    @staticmethod
    def _adapter_can_do(adapter: TAdapter, action_name: str) -> bool:
        return adapter is not None and getattr(adapter, f"can_{action_name}", False)

    @staticmethod
    def _ground_truth_can_do(action_name: str) -> bool:
        if not AdapterManager._instance:
            return False
        ground_truth_adapter = AdapterManager._instance.ground_truth_adapter
        if AdapterManager.offline_mode and ground_truth_adapter.is_networked:
            return False

        return AdapterManager._adapter_can_do(ground_truth_adapter, action_name)

    @staticmethod
    def _can_use_cache(force: bool, action_name: str) -> bool:
        if force:
            return False
        return (
            AdapterManager._instance is not None
            and AdapterManager._instance.caching_adapter is not None
            and AdapterManager._adapter_can_do(
                AdapterManager._instance.caching_adapter, action_name
            )
        )

    @staticmethod
    def _create_ground_truth_result(
        function_name: str,
        *params: Any,
        before_download: Callable[[], None] = None,
        partial_data: Any = None,
        **kwargs,
    ) -> Result:
        """
        Creates a Result using the given ``function_name`` on the ground truth adapter.
        """
        if (
            AdapterManager.offline_mode
            and AdapterManager._instance
            and AdapterManager._instance.ground_truth_adapter.is_networked
        ):
            raise AssertionError(
                "You should never call _create_ground_truth_result in offline mode"
            )

        def future_fn() -> Any:
            assert AdapterManager._instance
            if before_download:
                before_download()
            fn = getattr(AdapterManager._instance.ground_truth_adapter, function_name)
            try:
                return fn(*params, **kwargs)
            except Exception:
                raise CacheMissError(partial_data=partial_data)

        return Result(future_fn)

    @staticmethod
    def _create_download_fn(
        uri: str, id: str, before_download: Callable[[], None] = None,
    ) -> Callable[[], str]:
        """
        Create a function to download the given URI to a temporary file, and return the
        filename. The returned function will spin-loop if the resource is already being
        downloaded to prevent multiple requests for the same download.
        """
        if (
            AdapterManager.offline_mode
            and AdapterManager._instance
            and AdapterManager._instance.ground_truth_adapter.is_networked
        ):
            raise AssertionError(
                "You should never call _create_download_fn in offline mode"
            )

        def download_fn() -> str:
            assert AdapterManager._instance
            download_tmp_filename = AdapterManager._instance.download_path.joinpath(
                hashlib.sha1(bytes(uri, "utf8")).hexdigest()
            )

            resource_downloading = False
            with AdapterManager.download_set_lock:
                if id in AdapterManager.current_download_ids:
                    resource_downloading = True
                AdapterManager.current_download_ids.add(id)

            if before_download:
                before_download()

            # TODO (#122): figure out how to retry if the other request failed.
            if resource_downloading:
                logging.info(f"{uri} already being downloaded.")

                # The resource is already being downloaded. Busy loop until
                # it has completed. Then, just return the path to the
                # resource.
                t = 0.0
                while id in AdapterManager.current_download_ids and t < 20:
                    sleep(0.2)
                    t += 0.2
                    # TODO (#122): handle the timeout
            else:
                logging.info(f"{uri} not found. Downloading...")
                try:
                    if REQUEST_DELAY is not None:
                        delay = random.uniform(*REQUEST_DELAY)
                        logging.info(
                            f"REQUEST_DELAY enabled. Pausing for {delay} seconds"
                        )
                        sleep(delay)

                    if NETWORK_ALWAYS_ERROR:
                        raise Exception("NETWORK_ALWAYS_ERROR enabled")

                    data = requests.get(uri)

                    # TODO (#122): make better
                    if not data:
                        raise Exception("Download failed!")
                    if "json" in data.headers.get("Content-Type", ""):
                        raise Exception("Didn't expect JSON!")

                    with open(download_tmp_filename, "wb+") as f:
                        f.write(data.content)
                finally:
                    # Always release the download set lock, even if there's an error.
                    with AdapterManager.download_set_lock:
                        AdapterManager.current_download_ids.discard(id)

            logging.info(f"{uri} downloaded. Returning.")
            return str(download_tmp_filename)

        return download_fn

    @staticmethod
    def _create_caching_done_callback(
        cache_key: CachingAdapter.CachedDataKey, param: Optional[str]
    ) -> Callable[[Result], None]:
        """
        Create a function to let the caching_adapter ingest new data.

        :param cache_key: the cache key to ingest.
        :param params: the parameters to uniquely identify the cached item.
        """

        def future_finished(f: Result):
            assert AdapterManager._instance
            assert AdapterManager._instance.caching_adapter
            AdapterManager._instance.caching_adapter.ingest_new_data(
                cache_key, param, f.result()
            )

        return future_finished

    @staticmethod
    def _get_scheme() -> str:
        # TODO (#189): eventually this will come from the players
        assert AdapterManager._instance
        scheme_priority = ("https", "http")
        schemes = sorted(
            AdapterManager._instance.ground_truth_adapter.supported_schemes,
            key=scheme_priority.index,
        )
        return list(schemes)[0]

    @staticmethod
    def get_supported_artist_query_types() -> Set[AlbumSearchQuery.Type]:
        assert AdapterManager._instance

        supported_artist_query_types: Set[AlbumSearchQuery.Type] = set()
        supported_artist_query_types.union(
            AdapterManager._instance.ground_truth_adapter.supported_artist_query_types
        )

        if caching_adapter := AdapterManager._instance.caching_adapter:
            supported_artist_query_types.union(
                caching_adapter.supported_artist_query_types
            )

        return supported_artist_query_types

    R = TypeVar("R")

    @staticmethod
    def _get_from_cache_or_ground_truth(
        function_name: str,
        param: Optional[Union[str, AlbumSearchQuery]],
        cache_key: CachingAdapter.CachedDataKey = None,
        before_download: Callable[[], None] = None,
        use_ground_truth_adapter: bool = False,
        allow_download: bool = True,
        on_result_finished: Callable[[Result], None] = None,
        **kwargs: Any,
    ) -> Result[R]:
        """
        Get data from one of the adapters.

        :param function_name: The function to call on the adapter.
        :param param: The parameter to pass to the adapter function (also used for the
            cache parameter to uniquely identify the request).
        :param cache_key: The cache key to use to invalidate caches and ingest caches.
        :param before_download: Function to call before doing a network request.
        :param allow_download: Whether or not to allow a network request to retrieve the
            data.
        :param on_result_finished: A function to run after the result received from the
            ground truth adapter. (Has no effect if the result is from the caching
            adapter.)
        :param kwargs: The keyword arguments to pass to the adapter function.
        """
        assert AdapterManager._instance
        logging.info(f"START: {function_name}")
        partial_data = None
        if AdapterManager._can_use_cache(use_ground_truth_adapter, function_name):
            assert (caching_adapter := AdapterManager._instance.caching_adapter)
            try:
                logging.info(f"END: {function_name}: serving from cache")
                if param is None:
                    return Result(getattr(caching_adapter, function_name)(**kwargs))
                return Result(getattr(caching_adapter, function_name)(param, **kwargs))
            except CacheMissError as e:
                partial_data = e.partial_data
                logging.info(f"Cache Miss on {function_name}.")
            except Exception:
                logging.exception(f"Error on {function_name} retrieving from cache.")

        param_str = param.strhash() if isinstance(param, AlbumSearchQuery) else param
        if (
            cache_key
            and AdapterManager._instance.caching_adapter
            and use_ground_truth_adapter
        ):
            AdapterManager._instance.caching_adapter.invalidate_data(
                cache_key, param_str
            )

        if (
            not allow_download
            and AdapterManager._instance.ground_truth_adapter.is_networked
        ) or not AdapterManager._ground_truth_can_do(function_name):
            logging.info(f"END: NO DOWNLOAD: {function_name}")

            def cache_miss_result():
                raise CacheMissError(partial_data=partial_data)

            return Result(cache_miss_result)

        result: Result[AdapterManager.R] = AdapterManager._create_ground_truth_result(
            function_name,
            *((param,) if param is not None else ()),
            before_download=before_download,
            partial_data=partial_data,
            **kwargs,
        )

        if AdapterManager._instance.caching_adapter:
            if cache_key:
                result.add_done_callback(
                    AdapterManager._create_caching_done_callback(cache_key, param_str)
                )

            if on_result_finished:
                result.add_done_callback(on_result_finished)

        logging.info(f"END: {function_name}")
        logging.debug(result)
        return result

    # Usage and Availability Properties
    # ==================================================================================
    @staticmethod
    def can_get_playlists() -> bool:
        return AdapterManager._ground_truth_can_do("get_playlists")

    @staticmethod
    def can_get_playlist_details() -> bool:
        return AdapterManager._ground_truth_can_do("get_playlist_details")

    @staticmethod
    def can_create_playlist() -> bool:
        return AdapterManager._ground_truth_can_do("create_playlist")

    @staticmethod
    def can_update_playlist() -> bool:
        return AdapterManager._ground_truth_can_do("update_playlist")

    @staticmethod
    def can_delete_playlist() -> bool:
        return AdapterManager._ground_truth_can_do("delete_playlist")

    @staticmethod
    def can_get_song_filename_or_stream() -> bool:
        return AdapterManager._ground_truth_can_do("get_song_uri")

    @staticmethod
    def can_batch_download_songs() -> bool:
        # We can only download from the ground truth adapter.
        return AdapterManager._ground_truth_can_do("get_song_uri")

    @staticmethod
    def can_get_genres() -> bool:
        return AdapterManager._ground_truth_can_do("get_genres")

    @staticmethod
    def can_scrobble_song() -> bool:
        return AdapterManager._ground_truth_can_do("scrobble_song")

    @staticmethod
    def can_get_artists() -> bool:
        return AdapterManager._ground_truth_can_do("get_artists")

    @staticmethod
    def can_get_artist() -> bool:
        return AdapterManager._ground_truth_can_do("get_artist")

    @staticmethod
    def can_get_directory() -> bool:
        return AdapterManager._ground_truth_can_do("get_directory")

    @staticmethod
    def can_get_play_queue() -> bool:
        return AdapterManager._ground_truth_can_do("get_play_queue")

    @staticmethod
    def can_save_play_queue() -> bool:
        return AdapterManager._ground_truth_can_do("save_play_queue")

    @staticmethod
    def can_search() -> bool:
        return AdapterManager._ground_truth_can_do("search")

    # Data Retrieval Methods
    # ==================================================================================
    @staticmethod
    def get_playlists(
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO (#202): rename to use_ground_truth_adapter?
        allow_download: bool = True,
    ) -> Result[Sequence[Playlist]]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_playlists",
            None,
            cache_key=CachingAdapter.CachedDataKey.PLAYLISTS,
            before_download=before_download,
            use_ground_truth_adapter=force,
            allow_download=allow_download,
        )

    @staticmethod
    def get_playlist_details(
        playlist_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO (#202): rename to use_ground_truth_adapter?
        allow_download: bool = True,
    ) -> Result[Playlist]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_playlist_details",
            playlist_id,
            cache_key=CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
            before_download=before_download,
            use_ground_truth_adapter=force,
            allow_download=allow_download,
        )

    @staticmethod
    def create_playlist(
        name: str, songs: Sequence[Song] = None
    ) -> Result[Optional[Playlist]]:
        def on_result_finished(f: Result[Optional[Playlist]]):
            assert AdapterManager._instance
            assert AdapterManager._instance.caching_adapter
            if playlist := f.result():
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
                    playlist.id,
                    playlist,
                )
            else:
                AdapterManager._instance.caching_adapter.invalidate_data(
                    CachingAdapter.CachedDataKey.PLAYLISTS, None
                )

        return AdapterManager._get_from_cache_or_ground_truth(
            "create_playlist",
            name,
            songs=songs,
            on_result_finished=on_result_finished,
            use_ground_truth_adapter=True,
        )

    @staticmethod
    def update_playlist(
        playlist_id: str,
        name: str = None,
        comment: str = None,
        public: bool = False,
        song_ids: Sequence[str] = None,
        append_song_ids: Sequence[str] = None,
        before_download: Callable[[], None] = lambda: None,
    ) -> Result[Playlist]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "update_playlist",
            playlist_id,
            name=name,
            comment=comment,
            public=public,
            song_ids=song_ids,
            append_song_ids=append_song_ids,
            before_download=before_download,
            use_ground_truth_adapter=True,
            cache_key=CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
        )

    @staticmethod
    def delete_playlist(playlist_id: str):
        assert AdapterManager._instance
        ground_truth_adapter = AdapterManager._instance.ground_truth_adapter
        if AdapterManager.offline_mode and ground_truth_adapter.is_networked:
            raise AssertionError(
                "You should never call _create_download_fn in offline mode"
            )

        # TODO (#190): make non-blocking?
        ground_truth_adapter.delete_playlist(playlist_id)

        if AdapterManager._instance.caching_adapter:
            AdapterManager._instance.caching_adapter.delete_data(
                CachingAdapter.CachedDataKey.PLAYLIST_DETAILS, playlist_id
            )

    # TODO (#189): allow this to take a set of schemes and unify with
    # get_cover_art_filename
    @staticmethod
    def get_cover_art_uri(cover_art_id: str = None, size: int = 300) -> str:
        assert AdapterManager._instance
        if (
            not AdapterManager._ground_truth_can_do("get_cover_art_uri")
            or not cover_art_id
        ):
            return ""

        return AdapterManager._instance.ground_truth_adapter.get_cover_art_uri(
            cover_art_id, AdapterManager._get_scheme(), size=size
        )

    @staticmethod
    def get_cover_art_filename(
        cover_art_id: str = None,
        before_download: Callable[[], None] = None,
        force: bool = False,  # TODO (#202): rename to use_ground_truth_adapter?
        allow_download: bool = True,
    ) -> Result[str]:
        existing_cover_art_filename = str(
            Path(__file__).parent.joinpath("images/default-album-art.png")
        )
        if cover_art_id is None:
            return Result(existing_cover_art_filename)

        assert AdapterManager._instance

        # There could be partial data if the cover art exists, but for some reason was
        # marked out-of-date.
        if AdapterManager._can_use_cache(force, "get_cover_art_uri"):
            assert AdapterManager._instance.caching_adapter
            try:
                return Result(
                    AdapterManager._instance.caching_adapter.get_cover_art_uri(
                        cover_art_id, "file", size=300
                    )
                )
            except CacheMissError as e:
                if e.partial_data is not None:
                    existing_cover_art_filename = cast(str, e.partial_data)
                logging.info(f'Cache Miss on {"get_cover_art_uri"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_cover_art_uri"} retrieving from cache.'
                )

        if not allow_download:
            return Result(existing_cover_art_filename)

        if AdapterManager._instance.caching_adapter and force:
            AdapterManager._instance.caching_adapter.invalidate_data(
                CachingAdapter.CachedDataKey.COVER_ART_FILE, cover_art_id
            )

        if not AdapterManager._ground_truth_can_do("get_cover_art_uri"):
            return Result(existing_cover_art_filename)

        future: Result[str] = Result(
            AdapterManager._create_download_fn(
                AdapterManager._instance.ground_truth_adapter.get_cover_art_uri(
                    cover_art_id, AdapterManager._get_scheme(), size=300
                ),
                cover_art_id,
                before_download,
            ),
            is_download=True,
            default_value=existing_cover_art_filename,
        )

        if AdapterManager._instance.caching_adapter:
            future.add_done_callback(
                AdapterManager._create_caching_done_callback(
                    CachingAdapter.CachedDataKey.COVER_ART_FILE, cover_art_id
                )
            )

        return future

    # TODO (#189): allow this to take a set of schemes
    @staticmethod
    def get_song_filename_or_stream(
        song: Song,
        format: str = None,
        force_stream: bool = False,
        allow_song_downloads: bool = True,
    ) -> str:
        assert AdapterManager._instance
        cached_song_filename = None
        if AdapterManager._can_use_cache(force_stream, "get_song_uri"):
            assert AdapterManager._instance.caching_adapter
            try:
                return AdapterManager._instance.caching_adapter.get_song_uri(
                    song.id, "file"
                )
            except CacheMissError as e:
                if e.partial_data is not None:
                    cached_song_filename = cast(str, e.partial_data)
                logging.info(f'Cache Miss on {"get_song_filename_or_stream"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_song_filename_or_stream"} retrieving from cache.'
                )

        if not AdapterManager._ground_truth_can_do("get_song_uri"):
            if not allow_song_downloads or cached_song_filename is None:
                # TODO
                raise Exception("Can't stream the song.")
            return cached_song_filename

        # TODO (subsonic-extensions-api/specification#2) implement subsonic extension to
        # get the hash of the song and compare here. That way of the cache gets blown
        # away, but not the song files, it will not have to re-download.

        if not allow_song_downloads and not AdapterManager._ground_truth_can_do(
            "stream"
        ):
            # TODO
            raise Exception("Can't stream the song.")

        return AdapterManager._instance.ground_truth_adapter.get_song_uri(
            song.id, AdapterManager._get_scheme(), stream=True,
        )

    @staticmethod
    def batch_download_songs(
        song_ids: Sequence[str],
        before_download: Callable[[str], None],
        on_song_download_complete: Callable[[str], None],
        one_at_a_time: bool = False,
        delay: float = 0.0,
    ) -> Result[None]:
        assert AdapterManager._instance
        if (
            AdapterManager.offline_mode
            and AdapterManager._instance.ground_truth_adapter.is_networked
        ):
            raise AssertionError(
                "You should never call batch_download_songs in offline mode"
            )

        # This only really makes sense if we have a caching_adapter.
        if not AdapterManager._instance.caching_adapter:
            return Result(None)

        cancelled = False

        def do_download_song(song_id: str):
            if AdapterManager.is_shutting_down or cancelled:
                return

            assert AdapterManager._instance
            assert AdapterManager._instance.caching_adapter

            logging.info(f"Downloading {song_id}")

            try:
                # Download the actual song file.
                try:
                    # If the song file is already cached, return immediately.
                    AdapterManager._instance.caching_adapter.get_song_uri(
                        song_id, "file"
                    )
                except CacheMissError:
                    # The song is not already cached.
                    if before_download:
                        before_download(song_id)

                    # Download the song.
                    song_tmp_filename = AdapterManager._create_download_fn(
                        AdapterManager._instance.ground_truth_adapter.get_song_uri(
                            song_id, AdapterManager._get_scheme()
                        ),
                        song_id,
                        lambda: before_download(song_id),
                    )()
                    AdapterManager._instance.caching_adapter.ingest_new_data(
                        CachingAdapter.CachedDataKey.SONG_FILE,
                        song_id,
                        (None, song_tmp_filename),
                    )
                    on_song_download_complete(song_id)

                # Download the corresponding cover art.
                song = AdapterManager.get_song_details(song_id).result()
                AdapterManager.get_cover_art_filename(song.cover_art).result()
            finally:
                # Release the semaphore lock. This will allow the next song in the queue
                # to be downloaded. I'm doing this in the finally block so that it
                # always runs, regardless of whether an exception is thrown or the
                # function returns.
                AdapterManager._instance.download_limiter_semaphore.release()

        def do_batch_download_songs():
            sleep(delay)
            for song_id in song_ids:
                if cancelled:
                    return
                # Only allow a certain number of songs to be downloaded
                # simultaneously.
                AdapterManager._instance.download_limiter_semaphore.acquire()

                # Prevents further songs from being downloaded.
                if AdapterManager.is_shutting_down:
                    break

                result = Result(do_download_song, song_id, is_download=True)

                if one_at_a_time:
                    # Wait the file to download.
                    result.result()

        def on_cancel():
            nonlocal cancelled
            cancelled = True

        return Result(do_batch_download_songs, is_download=True, on_cancel=on_cancel)

    @staticmethod
    def batch_permanently_cache_songs(
        song_ids: Sequence[str],
        before_download: Callable[[str], None],
        on_song_download_complete: Callable[[str], None],
    ) -> Result[None]:
        assert AdapterManager._instance
        # This only really makes sense if we have a caching_adapter.
        if not AdapterManager._instance.caching_adapter:
            return Result(None)
        # TODO (#74): actually implement this
        raise NotImplementedError()

    @staticmethod
    def batch_delete_cached_songs(
        song_ids: Sequence[str], on_song_delete: Callable[[str], None]
    ):
        assert AdapterManager._instance

        # This only really makes sense if we have a caching_adapter.
        if not AdapterManager._instance.caching_adapter:
            return

        for song_id in song_ids:
            song = AdapterManager.get_song_details(song_id).result()
            AdapterManager._instance.caching_adapter.delete_data(
                CachingAdapter.CachedDataKey.SONG_FILE, song.id
            )
            on_song_delete(song_id)

    @staticmethod
    def get_song_details(
        song_id: str,
        allow_download: bool = True,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,
    ) -> Result[Song]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_song_details",
            song_id,
            allow_download=allow_download,
            before_download=before_download,
            use_ground_truth_adapter=force,
            cache_key=CachingAdapter.CachedDataKey.SONG,
        )

    @staticmethod
    def get_genres(force: bool = False) -> Result[Sequence[Genre]]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_genres",
            None,
            use_ground_truth_adapter=force,
            cache_key=CachingAdapter.CachedDataKey.GENRES,
        )

    @staticmethod
    def scrobble_song(song: Song):
        assert AdapterManager._instance
        AdapterManager._create_ground_truth_result("scrobble_song", song)

    @staticmethod
    def get_artists(
        force: bool = False, before_download: Callable[[], None] = lambda: None
    ) -> Result[Sequence[Artist]]:
        def do_get_artists() -> Sequence[Artist]:
            return AdapterManager.sort_by_ignored_articles(
                AdapterManager._get_from_cache_or_ground_truth(
                    "get_artists",
                    None,
                    use_ground_truth_adapter=force,
                    before_download=before_download,
                    cache_key=CachingAdapter.CachedDataKey.ARTISTS,
                ).result(),
                key=lambda a: a.name,
                use_ground_truth_adapter=force,
            )

        return Result(do_get_artists)

    @staticmethod
    def _get_ignored_articles(use_ground_truth_adapter: bool) -> Set[str]:
        # TODO (#21) get this at first startup.
        if not AdapterManager._ground_truth_can_do("get_ignored_articles"):
            return set()
        try:
            ignored_articles: Set[str] = AdapterManager._get_from_cache_or_ground_truth(
                "get_ignored_articles",
                None,
                use_ground_truth_adapter=use_ground_truth_adapter,
                cache_key=CachingAdapter.CachedDataKey.IGNORED_ARTICLES,
            ).result()
            return set(map(str.lower, ignored_articles))
        except Exception:
            logging.exception("Failed to retrieve ignored_articles")
            return set()

    @staticmethod
    def _strip_ignored_articles(
        use_ground_truth_adapter: bool, ignored_articles: Set[str], string: str
    ) -> str:
        first_word, *rest = string.split(maxsplit=1)
        if first_word in ignored_articles:
            return rest[0]
        return string

    _S = TypeVar("_S")

    @staticmethod
    def sort_by_ignored_articles(
        it: Iterable[_S],
        key: Callable[[_S], str],
        use_ground_truth_adapter: bool = False,
    ) -> List[_S]:
        ignored_articles = AdapterManager._get_ignored_articles(
            use_ground_truth_adapter
        )
        strip_fn = partial(
            AdapterManager._strip_ignored_articles,
            use_ground_truth_adapter,
            ignored_articles,
        )
        return sorted(it, key=lambda x: strip_fn(key(x).lower()))

    @staticmethod
    def get_artist(
        artist_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,
    ) -> Result[Artist]:
        def on_result_finished(f: Result[Artist]):
            if not force:
                return

            assert AdapterManager._instance
            assert AdapterManager._instance.caching_adapter
            if artist := f.result():
                for album in artist.albums or []:
                    AdapterManager._instance.caching_adapter.invalidate_data(
                        CachingAdapter.CachedDataKey.ALBUM, album.id
                    )

        return AdapterManager._get_from_cache_or_ground_truth(
            "get_artist",
            artist_id,
            before_download=before_download,
            use_ground_truth_adapter=force,
            cache_key=CachingAdapter.CachedDataKey.ARTIST,
            on_result_finished=on_result_finished,
        )

    # Albums
    @staticmethod
    def get_albums(
        query: AlbumSearchQuery,
        sort_direction: str = "ascending",
        before_download: Callable[[], None] = lambda: None,
        use_ground_truth_adapter: bool = False,
    ) -> Result[Sequence[Album]]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_albums",
            query,
            sort_direction=sort_direction,
            cache_key=CachingAdapter.CachedDataKey.ALBUMS,
            before_download=before_download,
            use_ground_truth_adapter=use_ground_truth_adapter,
        )

    @staticmethod
    def get_album(
        album_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,
    ) -> Result[Album]:
        return AdapterManager._get_from_cache_or_ground_truth(
            "get_album",
            album_id,
            before_download=before_download,
            use_ground_truth_adapter=force,
            cache_key=CachingAdapter.CachedDataKey.ALBUM,
        )

    # Browse
    @staticmethod
    def get_directory(
        directory_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,
    ) -> Result[Directory]:
        def do_get_directory() -> Directory:
            directory: Directory = AdapterManager._get_from_cache_or_ground_truth(
                "get_directory",
                directory_id,
                before_download=before_download,
                use_ground_truth_adapter=force,
                cache_key=CachingAdapter.CachedDataKey.DIRECTORY,
            ).result()
            directory.children = AdapterManager.sort_by_ignored_articles(
                directory.children,
                key=lambda c: cast(Directory, c).name or ""
                if hasattr(c, "name")
                else cast(Song, c).title,
                use_ground_truth_adapter=force,
            )
            return directory

        return Result(do_get_directory)

    # Play Queue
    @staticmethod
    def get_play_queue() -> Result[Optional[PlayQueue]]:
        assert AdapterManager._instance
        return AdapterManager._create_ground_truth_result("get_play_queue")

    @staticmethod
    def save_play_queue(
        song_ids: Sequence[int],
        current_song_index: int = None,
        position: timedelta = None,
    ):
        assert AdapterManager._instance
        AdapterManager._create_ground_truth_result(
            "save_play_queue",
            song_ids,
            current_song_index=current_song_index,
            position=position,
        )

    @staticmethod
    def search(
        query: str,
        search_callback: Callable[[SearchResult], None],
        before_download: Callable[[], None] = lambda: None,
    ) -> Result[bool]:
        if query == "":
            search_callback(SearchResult(""))
            return Result(True)

        before_download()

        # Keep track of if the result is cancelled and if it is, then don't do anything
        # with any results.
        cancelled = False

        # This function actually does the search and calls the search_callback when each
        # of the futures completes. Returns whether or not it was cancelled.
        def do_search() -> bool:
            # Sleep for a little while before returning the local results. They are less
            # expensive to retrieve (but they still incur some overhead due to the GTK
            # UI main loop queue).
            sleep(0.3)
            if cancelled:
                logging.info(f"Cancelled query {query} before caching adapter")
                return True

            assert AdapterManager._instance

            # Caching Adapter Results
            search_result = SearchResult(query)
            if AdapterManager._can_use_cache(False, "search"):
                assert AdapterManager._instance.caching_adapter
                try:
                    logging.info(
                        f"Returning caching adapter search results for '{query}'."
                    )
                    search_result.update(
                        AdapterManager._instance.caching_adapter.search(query)
                    )
                    search_callback(search_result)
                except Exception:
                    logging.exception("Error on caching adapter search")

            if not AdapterManager._ground_truth_can_do("search"):
                return False

            # Wait longer to see if the user types anything else so we don't peg the
            # server with tons of requests.
            sleep(
                1 if AdapterManager._instance.ground_truth_adapter.is_networked else 0.3
            )
            if cancelled:
                logging.info(f"Cancelled query {query} before server results")
                return True

            try:
                ground_truth_search_results = AdapterManager._instance.ground_truth_adapter.search(  # noqa: E501
                    query
                )
                search_result.update(ground_truth_search_results)
                search_callback(search_result)
            except Exception:
                logging.exception(
                    "Failed getting search results from server for query '{query}'"
                )

            if AdapterManager._instance.caching_adapter:
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.SEARCH_RESULTS,
                    None,
                    ground_truth_search_results,
                )

            return False

        # When the future is cancelled (this will happen if a new search is created),
        # set cancelled to True so that the search function can abort.
        def on_cancel():
            nonlocal cancelled
            cancelled = True

        return Result(do_search, on_cancel=on_cancel)

    # Cache Status Methods
    # ==================================================================================
    @staticmethod
    def get_cached_statuses(song_ids: Sequence[str]) -> Sequence[SongCacheStatus]:
        assert AdapterManager._instance
        if not AdapterManager._instance.caching_adapter:
            return list(itertools.repeat(SongCacheStatus.NOT_CACHED, len(song_ids)))

        cached_statuses = AdapterManager._instance.caching_adapter.get_cached_statuses(
            song_ids
        )
        return [
            SongCacheStatus.DOWNLOADING
            if song_id in AdapterManager.current_download_ids
            else cached_statuses[song_id]
            for song_id in song_ids
        ]

    @staticmethod
    def clear_song_cache():
        assert AdapterManager._instance
        if not AdapterManager._instance.caching_adapter:
            return
        AdapterManager._instance.caching_adapter.delete_data(
            CachingAdapter.CachedDataKey.ALL_SONGS, None
        )

    @staticmethod
    def clear_entire_cache():
        assert AdapterManager._instance
        if not AdapterManager._instance.caching_adapter:
            return
        AdapterManager._instance.caching_adapter.delete_data(
            CachingAdapter.CachedDataKey.EVERYTHING, None
        )
