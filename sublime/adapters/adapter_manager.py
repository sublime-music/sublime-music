import logging
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
)

import requests

from sublime.config import AppConfiguration

from .adapter_base import Adapter, CacheMissError, CachingAdapter, SongCacheStatus
from .api_objects import Playlist, PlaylistDetails, Song
from .filesystem import FilesystemAdapter
from .subsonic import SubsonicAdapter

T = TypeVar("T")


class Result(Generic[T]):
    """
    A result from a :class:`AdapterManager` function. This is effectively a wrapper
    around a :class:`concurrent.futures.Future`, but it resolves immediately if the data
    already exists.
    """

    _data: Optional[T] = None
    _future: Optional[Future] = None
    on_cancel: Optional[Callable[[], None]] = None

    def __init__(self, data_resolver: Union[T, Callable[[], T]]):
        # TODO take in the partial_data in this constructor so that it can be used if
        # getting the result fails.
        """
        Creates a :class:`Result` object.

        :param data_resolver: the actual data, or a function that will return the actual
            data. If the latter, the function will be executed by the thread pool.
        """
        if callable(data_resolver):
            self._future = AdapterManager.executor.submit(data_resolver)
            self._future.add_done_callback(self._on_future_complete)
        else:
            self._data = data_resolver

    def _on_future_complete(self, future: Future):
        self._data = future.result()

    def result(self) -> T:
        """
        Retrieve the actual data. If the data exists already, then return it, otherwise,
        blocking-wait on the future's result.
        """
        if self._data is not None:
            return self._data
        if self._future is not None:
            return self._future.result()

        raise Exception("AdapterManager.Result had neither _data nor _future member!")

    def add_done_callback(self, fn: Callable, *args):
        """Attaches the callable ``fn`` to the future."""
        if self._future is not None:
            self._future.add_done_callback(fn, *args)
        else:
            # Run the function immediately if it's not a future.
            fn(self, *args)

    def cancel(self) -> bool:
        """Cancel the future, or do nothing if the data already exists."""
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
    executor: ThreadPoolExecutor = ThreadPoolExecutor()
    is_shutting_down: bool = False

    @dataclass
    class _AdapterManagerInternal:
        ground_truth_adapter: Adapter
        caching_adapter: Optional[CachingAdapter] = None

        def __post_init__(self):
            self._download_dir = tempfile.TemporaryDirectory()
            self.download_path = Path(self._download_dir.name)

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
            "Do not instantiate the AdapterManager. "
            "Only use the static methods on the class."
        )

    @staticmethod
    def shutdown():
        logging.info("AdapterManager shutdown start")
        AdapterManager.is_shutting_down = True
        AdapterManager.executor.shutdown()
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        logging.info("AdapterManager shutdown complete")

    @staticmethod
    def reset(config: AppConfiguration):
        # First, shutdown the current one...
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        # TODO: actually do stuff with the config to determine which adapters
        # to create, etc.
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
            ground_truth_adapter, caching_adapter=caching_adapter,
        )

    # Data Helper Methods
    # ==================================================================================
    TAdapter = TypeVar("TAdapter", bound=Adapter)

    @staticmethod
    def _adapter_can_do(adapter: Optional[TAdapter], action_name: str):
        return (
            adapter is not None
            and adapter.can_service_requests
            and getattr(adapter, f"can_{action_name}", False)
        )

    @staticmethod
    def _cache_can_do(action_name: str):
        return AdapterManager._instance is not None and AdapterManager._adapter_can_do(
            AdapterManager._instance.caching_adapter, action_name
        )

    @staticmethod
    def _ground_truth_can_do(action_name: str):
        return AdapterManager._instance is not None and AdapterManager._adapter_can_do(
            AdapterManager._instance.ground_truth_adapter, action_name
        )

    @staticmethod
    def _can_use_cache(force: bool, action_name: str) -> bool:
        if force:
            return False
        return AdapterManager._cache_can_do(action_name)

    @staticmethod
    def _any_adapter_can_do(action_name: str):
        if AdapterManager._instance is None:
            return False

        return AdapterManager._ground_truth_can_do(
            action_name
        ) or AdapterManager._cache_can_do(action_name)

    # TODO abstract more stuff

    # Usage and Availability Properties
    # ==================================================================================
    @staticmethod
    def can_get_playlists() -> bool:
        return AdapterManager._any_adapter_can_do("get_playlists")

    @staticmethod
    def can_get_playlist_details() -> bool:
        return AdapterManager._any_adapter_can_do("get_playlist_details")

    @staticmethod
    def can_create_playlist() -> bool:
        return AdapterManager._any_adapter_can_do("create_playlist")

    @staticmethod
    def can_update_playlist() -> bool:
        return AdapterManager._any_adapter_can_do("update_playlist")

    @staticmethod
    def can_delete_playlist() -> bool:
        return AdapterManager._any_adapter_can_do("delete_playlist")

    @staticmethod
    def can_get_cover_art_uri() -> bool:
        return AdapterManager._any_adapter_can_do("get_cover_art_uri")

    @staticmethod
    def can_get_song_uri() -> bool:
        return AdapterManager._any_adapter_can_do("get_song_uri")

    # Data Retrieval Methods
    # ==================================================================================
    @staticmethod
    def get_playlists(
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[Sequence[Playlist]]:
        assert AdapterManager._instance
        partial_playlists_data = None
        if AdapterManager._can_use_cache(force, "get_playlists"):
            assert AdapterManager._instance.caching_adapter
            try:
                return Result(AdapterManager._instance.caching_adapter.get_playlists())
            except CacheMissError as e:
                partial_playlists_data = e.partial_data
                logging.debug(f'Cache Miss on {"get_playlists"}.')
            except Exception:
                logging.exception(f'Error on {"get_playlists"} retrieving from cache.')

        if AdapterManager._instance.caching_adapter and force:
            AdapterManager._instance.caching_adapter.invalidate_data(
                CachingAdapter.CachedDataKey.PLAYLISTS, ()
            )

        if not AdapterManager._ground_truth_can_do("get_playlists"):
            if partial_playlists_data:
                return partial_playlists_data
            raise Exception(f'No adapters can service {"get_playlists"} at the moment.')

        def future_fn() -> Sequence[Playlist]:
            assert AdapterManager._instance
            if before_download:
                before_download()
            return AdapterManager._instance.ground_truth_adapter.get_playlists()

        future: Result[Sequence[Playlist]] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.PLAYLISTS, (), f.result(),
                )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def get_playlist_details(
        playlist_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[PlaylistDetails]:
        assert AdapterManager._instance
        partial_playlist_data = None
        if AdapterManager._can_use_cache(force, "get_playlist_details"):
            assert AdapterManager._instance.caching_adapter
            try:
                return Result(
                    AdapterManager._instance.caching_adapter.get_playlist_details(
                        playlist_id
                    )
                )
            except CacheMissError as e:
                partial_playlist_data = e.partial_data
                logging.debug(f'Cache Miss on {"get_playlist_details"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_playlist_details"} retrieving from cache.'
                )

        if AdapterManager._instance.caching_adapter and force:
            AdapterManager._instance.caching_adapter.invalidate_data(
                CachingAdapter.CachedDataKey.PLAYLIST_DETAILS, (playlist_id,)
            )

        if not AdapterManager._ground_truth_can_do("get_playlist_details"):
            if partial_playlist_data:
                return partial_playlist_data
            raise Exception(
                f'No adapters can service {"get_playlist_details"} at the moment.'
            )

        def future_fn() -> PlaylistDetails:
            assert AdapterManager._instance
            if before_download:
                before_download()
            return AdapterManager._instance.ground_truth_adapter.get_playlist_details(
                playlist_id
            )

        future: Result[PlaylistDetails] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
                    (playlist_id,),
                    f.result(),
                )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def create_playlist(
        name: str,
        songs: List[Song] = None,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[None]:
        assert AdapterManager._instance

        def future_fn():
            assert AdapterManager._instance
            if before_download:
                before_download()
            AdapterManager._instance.ground_truth_adapter.create_playlist(
                name, songs=songs
            )

        future: Result[None] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                playlist: Optional[PlaylistDetails] = f.result()
                if playlist:
                    AdapterManager._instance.caching_adapter.ingest_new_data(
                        CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
                        (playlist.id,),
                        playlist,
                    )
                else:
                    AdapterManager._instance.caching_adapter.invalidate_data(
                        CachingAdapter.CachedDataKey.PLAYLISTS, ()
                    )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def update_playlist(
        playlist_id: str,
        name: str = None,
        comment: str = None,
        public: bool = False,
        song_ids: List[str] = None,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[PlaylistDetails]:
        assert AdapterManager._instance

        def future_fn() -> PlaylistDetails:
            assert AdapterManager._instance
            if before_download:
                before_download()
            return AdapterManager._instance.ground_truth_adapter.update_playlist(
                playlist_id,
                name=name,
                comment=comment,
                public=public,
                song_ids=song_ids,
            )

        future: Result[PlaylistDetails] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                playlist: PlaylistDetails = f.result()
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.PLAYLIST_DETAILS,
                    (playlist.id,),
                    playlist,
                )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def delete_playlist(playlist_id: str):
        # TODO: make non-blocking?
        assert AdapterManager._instance
        AdapterManager._instance.ground_truth_adapter.delete_playlist(playlist_id)

        if AdapterManager._instance.caching_adapter:
            AdapterManager._instance.caching_adapter.delete_data(
                CachingAdapter.CachedDataKey.PLAYLIST_DETAILS, (playlist_id,)
            )

    @staticmethod
    def get_cover_art_filename(
        cover_art_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[str]:  # TODO: convert to return bytes?
        assert AdapterManager._instance

        # There could be partial data if the cover art exists, but for some reason was
        # marked out-of-date.
        existing_cover_art_filename = None
        if AdapterManager._can_use_cache(force, "get_cover_art_uri"):
            assert AdapterManager._instance.caching_adapter
            try:
                return Result(
                    AdapterManager._instance.caching_adapter.get_cover_art_uri(
                        cover_art_id, "file"
                    )
                )
            except CacheMissError as e:
                existing_cover_art_filename = e.partial_data
                logging.debug(f'Cache Miss on {"get_cover_art_uri"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_cover_art_uri"} retrieving from cache.'
                )

        if AdapterManager._instance.caching_adapter and force:
            AdapterManager._instance.caching_adapter.invalidate_data(
                CachingAdapter.CachedDataKey.COVER_ART_FILE, (cover_art_id,)
            )

        if not AdapterManager._ground_truth_can_do("get_cover_art_uri"):
            if existing_cover_art_filename:
                return existing_cover_art_filename
            raise Exception(
                f'No adapters can service {"get_cover_art_uri"} at the moment.'
            )

        def future_fn() -> str:
            assert AdapterManager._instance
            if before_download:
                before_download()

            scheme_priority = ("https", "http")
            schemes = sorted(
                AdapterManager._instance.ground_truth_adapter.supported_schemes,
                key=scheme_priority.index,
            )

            # TODO guard for already being downloaded
            data = requests.get(
                AdapterManager._instance.ground_truth_adapter.get_cover_art_uri(
                    cover_art_id, list(schemes)[0]
                )
            )

            # TODO (#122): make better
            if "json" in data.headers.get("Content-Type", ""):
                raise Exception("Didn't expect JSON.")

            download_dir = AdapterManager._instance.download_path.joinpath("cover_art")
            download_dir.mkdir(parents=True, exist_ok=True)
            cover_art_filename = download_dir.joinpath(cover_art_id)
            with open(cover_art_filename, "wb+") as f:
                f.write(data.content)

            return str(cover_art_filename)

        future: Result[str] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.CachedDataKey.COVER_ART_FILE,
                    (cover_art_id,),
                    f.result(),
                )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def get_song_uri(
        song_id: str,
        scheme: str,
        stream=False,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[str]:
        raise NotImplementedError()

    # Cache Status Methods
    # ==================================================================================
    @staticmethod
    def get_cached_status(song: Song) -> SongCacheStatus:
        assert AdapterManager._instance
        if not AdapterManager._instance.caching_adapter:
            return SongCacheStatus.NOT_CACHED

        return AdapterManager._instance.caching_adapter.get_cached_status(song)
