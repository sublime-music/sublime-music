import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
)

from sublime.config import AppConfiguration

from .adapter_base import Adapter, CacheMissError, CachingAdapter
from .api_objects import Playlist, PlaylistDetails
from .filesystem import FilesystemAdapter
from .subsonic import SubsonicAdapter

T = TypeVar('T')


class Result(Generic[T]):
    """
    A result from a :class:`AdapterManager` function. This is effectively a
    wrapper around a :class:`concurrent.futures.Future`, but it can also
    resolve immediately if the data already exists.
    """
    _data: Optional[T] = None
    _future: Optional[Future] = None
    on_cancel: Optional[Callable[[], None]] = None

    def __init__(self, data_resolver: Union[T, Callable[[], T]]):
        if callable(data_resolver):

            def future_complete(f: Future):
                self._data = f.result()

            self._future = AdapterManager.executor.submit(data_resolver)
            self._future.add_done_callback(future_complete)
        else:
            self._data = data_resolver

    def result(self) -> T:
        if self._data is not None:
            return self._data
        if self._future is not None:
            return self._future.result()

        raise Exception(
            'AdapterManager.Result had neither _data nor _future member!')

    def add_done_callback(self, fn: Callable, *args):
        if self._future is not None:
            self._future.add_done_callback(fn, *args)
        else:
            # Run the function immediately if it's not a future.
            fn(self, *args)

    def cancel(self) -> bool:
        if self._future is not None:
            return self._future.cancel()
        return True

    @property
    def data_is_available(self) -> bool:
        return self._data is not None


class AdapterManager:
    available_adapters: Set[Any] = {FilesystemAdapter, SubsonicAdapter}
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)
    is_shutting_down: bool = False

    @dataclass
    class _AdapterManagerInternal:
        ground_truth_adapter: Adapter
        caching_adapter: Optional[CachingAdapter] = None

        def shutdown(self):
            self.ground_truth_adapter.shutdown()
            if self.caching_adapter:
                self.caching_adapter.shutdown()

    _instance: Optional[_AdapterManagerInternal] = None

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
    def shutdown():
        logging.info('AdapterManager shutdown start')
        AdapterManager.is_shutting_down = True
        AdapterManager.executor.shutdown()
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        logging.info('CacheManager shutdown complete')

    @staticmethod
    def reset(config: AppConfiguration):
        # First, shutdown the current one...
        if AdapterManager._instance:
            AdapterManager._instance.shutdown()

        # TODO: actually do stuff with the config to determine which adapters
        # to create, etc.
        assert config.server is not None
        source_data_dir = Path(config.cache_location, config.server.strhash())
        source_data_dir.joinpath('g').mkdir(parents=True, exist_ok=True)
        source_data_dir.joinpath('c').mkdir(parents=True, exist_ok=True)

        ground_truth_adapter_type = SubsonicAdapter
        ground_truth_adapter = ground_truth_adapter_type(
            {
                key: getattr(config.server, key)
                for key in ground_truth_adapter_type.get_config_parameters()
            },
            source_data_dir.joinpath('g'),
        )

        caching_adapter_type = FilesystemAdapter
        caching_adapter = None
        if caching_adapter_type and ground_truth_adapter_type.can_be_cached:
            caching_adapter = caching_adapter_type(
                {
                    key: getattr(config.server, key)
                    for key in caching_adapter_type.get_config_parameters()
                },
                source_data_dir.joinpath('c'),
                is_cache=True,
            )

        AdapterManager._instance = AdapterManager._AdapterManagerInternal(
            ground_truth_adapter,
            caching_adapter=caching_adapter,
        )

    @staticmethod
    def can_get_playlists() -> bool:
        # It only matters that the ground truth one can service the request.
        return (
            AdapterManager._instance is not None and
            AdapterManager._instance.ground_truth_adapter.can_service_requests
            and
            AdapterManager._instance.ground_truth_adapter.can_get_playlists)

    @staticmethod
    def get_playlists(
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[Sequence[Playlist]]:
        assert AdapterManager._instance
        if (not force and AdapterManager._instance.caching_adapter and
                AdapterManager._instance.caching_adapter.can_service_requests
                and
                AdapterManager._instance.caching_adapter.can_get_playlists):
            try:
                return Result(
                    AdapterManager._instance.caching_adapter.get_playlists())
            except CacheMissError:
                logging.debug(f'Cache Miss on {"get_playlists"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_playlists"} retrieving from cache.')

        if (AdapterManager._instance.ground_truth_adapter
                and not AdapterManager._instance.ground_truth_adapter
                .can_service_requests and not AdapterManager._instance
                .ground_truth_adapter.can_get_playlists):
            raise Exception(
                f'No adapters can service {"get_playlists"} at the moment.')

        def future_fn() -> Sequence[Playlist]:
            assert AdapterManager._instance
            if before_download:
                before_download()
            return (
                AdapterManager._instance.ground_truth_adapter.get_playlists())

        future: Result[Sequence[Playlist]] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.FunctionNames.GET_PLAYLISTS,
                    (),
                    f.result(),
                )

            future.add_done_callback(future_finished)

        return future

    @staticmethod
    def can_get_playlist_details() -> bool:
        # It only matters that the ground truth one can service the request.
        return (
            AdapterManager._instance.ground_truth_adapter.can_service_requests
            and AdapterManager._instance.ground_truth_adapter
            .can_get_playlist_details)

    @staticmethod
    def get_playlist_details(
        playlist_id: str,
        before_download: Callable[[], None] = lambda: None,
        force: bool = False,  # TODO: rename to use_ground_truth_adapter?
    ) -> Result[PlaylistDetails]:
        assert AdapterManager._instance
        partial_playlist_data = None
        if (not force and AdapterManager._instance.caching_adapter and
                AdapterManager._instance.caching_adapter.can_service_requests
                and AdapterManager._instance.caching_adapter
                .can_get_playlist_details):
            try:
                return Result(
                    AdapterManager._instance.caching_adapter
                    .get_playlist_details(playlist_id))
            except CacheMissError as e:
                partial_playlist_data = e.partial_data
                logging.debug(f'Cache Miss on {"get_playlist_details"}.')
            except Exception:
                logging.exception(
                    f'Error on {"get_playlist_details"} retrieving from cache.'
                )

        if (AdapterManager._instance.ground_truth_adapter
                and not AdapterManager._instance.ground_truth_adapter
                .can_service_requests and not AdapterManager._instance
                .ground_truth_adapter.can_get_playlist_details):
            if partial_playlist_data:
                # TODO do something here
                pass
            raise Exception(
                f'No adapters can service {"get_playlist_details"} at the moment.'
            )

        def future_fn() -> PlaylistDetails:
            assert AdapterManager._instance
            if before_download:
                before_download()
            return (
                AdapterManager._instance.ground_truth_adapter
                .get_playlist_details(playlist_id))

        future: Result[PlaylistDetails] = Result(future_fn)

        if AdapterManager._instance.caching_adapter:

            def future_finished(f: Future):
                assert AdapterManager._instance
                assert AdapterManager._instance.caching_adapter
                AdapterManager._instance.caching_adapter.ingest_new_data(
                    CachingAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
                    (playlist_id, ),
                    f.result(),
                )

            future.add_done_callback(future_finished)

        return future
