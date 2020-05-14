import json
import logging
import os
import re
import shutil
import threading
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from enum import EnumMeta
from pathlib import Path
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

try:
    import gi

    gi.require_version("NM", "1.0")
    from gi.repository import NM

    networkmanager_imported = True
except Exception:
    # I really don't care what kind of exception it is, all that matters is the
    # import failed for some reason.
    logging.warning(
        "Unable to import NM from GLib. Detection of SSID will be disabled."
    )
    networkmanager_imported = False

from .config import AppConfiguration
from .server import Server
from .server.api_object import APIObject
from .server.api_objects import (
    AlbumWithSongsID3,
    Artist,
    ArtistID3,
    ArtistInfo2,
    ArtistWithAlbumsID3,
    Child,
    Directory,
)


class Singleton(type):
    """
    Metaclass for :class:`CacheManager` so that it can be used like a
    singleton.
    """

    def __getattr__(cls, name: str) -> Any:
        if not CacheManager._instance:
            return None
        # If the cache has a function to do the thing we want, use it. If
        # not, then go directly to the server (this is useful for things
        # that just send data  to the server.)
        if hasattr(CacheManager._instance, name):
            return getattr(CacheManager._instance, name)
        else:
            return getattr(CacheManager._instance.server, name)

        return None


T = TypeVar("T")


class CacheManager(metaclass=Singleton):
    """
    Handles everything related to caching metadata and song files.
    """

    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)
    should_exit: bool = False

    class Result(Generic[T]):
        # This needs to accept some way of:
        # 1. getting data from the server to fulfill the request
        # 2. coercing the data to the schema of the cachedb
        # 3. queries for retriving the data from the cachedb
        # All results should be retrieved using select statements from the DB
        """
        A result from a CacheManager function. This is effectively a wrapper
        around a Future, but it can also resolve immediately if the data
        already exists.
        """
        data: Optional[T] = None
        future: Optional[Future] = None
        on_cancel: Optional[Callable[[], None]] = None

        @staticmethod
        def from_data(data: T) -> "CacheManager.Result[T]":
            result: "CacheManager.Result[T]" = CacheManager.Result()
            result.data = data
            return result

        @staticmethod
        def from_server(
            download_fn: Callable[[], T],
            before_download: Callable[[], Any] = None,
            after_download: Callable[[T], Any] = None,
            on_cancel: Callable[[], Any] = None,
        ) -> "CacheManager.Result[T]":
            result: "CacheManager.Result[T]" = CacheManager.Result()

            def future_fn() -> T:
                if before_download:
                    before_download()
                return download_fn()

            result.future = CacheManager.executor.submit(future_fn)
            result.on_cancel = on_cancel

            if after_download is not None:
                result.future.add_done_callback(
                    lambda f: after_download and after_download(f.result())
                )

            return result

        def result(self) -> T:
            if self.data is not None:
                return self.data
            if self.future is not None:
                return self.future.result()

            raise Exception(
                "CacheManager.Result did not have either a data or future " "member."
            )

        def add_done_callback(self, fn: Callable, *args):
            if self.future is not None:
                self.future.add_done_callback(fn, *args)
            else:
                # Run the function immediately if it's not a future.
                fn(self, *args)

        def cancel(self) -> bool:
            if self.on_cancel is not None:
                self.on_cancel()

            if self.future is not None:
                return self.future.cancel()
            return True

        @property
        def is_future(self) -> bool:
            return self.future is not None

    @staticmethod
    def ready() -> bool:
        return CacheManager._instance is not None

    @staticmethod
    def shutdown():
        logging.info("CacheManager shutdown start")
        CacheManager.should_exit = True
        CacheManager.executor.shutdown()
        CacheManager._instance.save_cache_info()
        logging.info("CacheManager shutdown complete")

    class CacheEncoder(json.JSONEncoder):
        def default(self, obj: Any) -> Optional[Union[int, List, Dict]]:
            """
            Encodes Python objects to JSON.

            - ``datetime`` objects are converted to UNIX timestamps (``int``)
            - ``set`` objects are converted to ``list`` objects
            - ``APIObject`` objects are recursively encoded
            - ``EnumMeta`` objects are ignored
            - everything else is encoded using the default encoder
            """
            if type(obj) == datetime:
                return int(obj.timestamp() * 1000)
            elif type(obj) == set:
                return list(obj)
            elif isinstance(obj, APIObject):
                return {k: v for k, v in obj.__dict__.items() if v is not None}
            elif isinstance(obj, EnumMeta):
                return None

            return json.JSONEncoder.default(self, obj)

    class __CacheManagerInternal:
        # Thread lock for preventing threads from overriding the state while
        # it's being saved.
        cache_lock = threading.Lock()

        cache: DefaultDict[str, Any] = defaultdict(dict)
        permanently_cached_paths: Set[str] = set()

        # The server instance.
        server: Server

        # TODO (#56): need to split out the song downloads and make them higher
        # priority I think. Maybe even need to just make this a priority queue.
        download_set_lock = threading.Lock()
        current_downloads: Set[str] = set()

        def __init__(self, app_config: AppConfiguration):
            self.app_config = app_config
            assert self.app_config.server is not None
            self.app_config.server

            # If connected to the "Local Network SSID", use the "Local Network
            # Address" instead of the "Server Address".
            hostname = self.app_config.server.server_address
            if self.app_config.server.local_network_ssid in self.current_ssids:
                hostname = self.app_config.server.local_network_address

            self.server = Server(
                name=self.app_config.server.name,
                hostname=hostname,
                username=self.app_config.server.username,
                password=self.app_config.server.password,
                disable_cert_verify=self.app_config.server.disable_cert_verify,
            )
            self.download_limiter_semaphore = threading.Semaphore(
                self.app_config.concurrent_download_limit
            )

            self.load_cache_info()

        @property
        def current_ssids(self) -> Set[str]:
            if not networkmanager_imported:
                return set()

            self.networkmanager_client = NM.Client.new()
            self.nmclient_initialized = False
            self._current_ssids: Set[str] = set()
            if not self.nmclient_initialized:
                # Only look at the active WiFi connections.
                for ac in self.networkmanager_client.get_active_connections():
                    if ac.get_connection_type() != "802-11-wireless":
                        continue
                    devs = ac.get_devices()
                    if len(devs) != 1:
                        continue
                    if devs[0].get_device_type() != NM.DeviceType.WIFI:
                        continue

                    self._current_ssids.add(ac.get_id())

            return self._current_ssids

        def load_cache_info(self):
            cache_meta_file = self.calculate_abs_path(".cache_meta")

            meta_json = {}
            if cache_meta_file.exists():
                with open(cache_meta_file, "r") as f:
                    try:
                        meta_json = json.load(f)
                    except json.decoder.JSONDecodeError:
                        # Just continue with the default meta_json.
                        logging.warning("Unable to load cache", stack_info=True)

            cache_version = meta_json.get("version", 0)

            if cache_version < 1:
                logging.info("Migrating cache to version 1.")
                cover_art_re = re.compile(r"(\d+)_(\d+)")
                abs_path = self.calculate_abs_path("cover_art/")
                abs_path.mkdir(parents=True, exist_ok=True)
                for cover_art_file in abs_path.iterdir():
                    match = cover_art_re.match(cover_art_file.name)
                    if match:
                        art_id, dimensions = map(int, match.groups())
                        if dimensions == 1000:
                            no_dimens = cover_art_file.parent.joinpath("{art_id}")
                            logging.info(f"Moving {cover_art_file} to {no_dimens}")
                            shutil.move(cover_art_file, no_dimens)
                        else:
                            logging.info(f"Deleting {cover_art_file}")
                            cover_art_file.unlink()

            self.cache["version"] = 1

            cache_configs = [
                ("song_details", Child, dict),
                # Non-ID3 caches
                ("music_directories", Directory, dict),
                ("indexes", Artist, list),
                # ID3 caches
                ("albums", AlbumWithSongsID3, "dict-list"),
                ("album_details", AlbumWithSongsID3, dict),
                ("artists", ArtistID3, list),
                ("artist_details", ArtistWithAlbumsID3, dict),
                ("artist_infos", ArtistInfo2, dict),
            ]
            for name, type_name, default in cache_configs:
                if default == list:
                    self.cache[name] = [
                        type_name.from_json(x) for x in meta_json.get(name) or []
                    ]
                elif default == dict:
                    self.cache[name] = {
                        id: type_name.from_json(x)
                        for id, x in (meta_json.get(name) or {}).items()
                    }
                elif default == "dict-list":
                    self.cache[name] = {
                        n: [type_name.from_json(x) for x in xs]
                        for n, xs in (meta_json.get(name) or {}).items()
                    }

        def save_cache_info(self):
            os.makedirs(self.app_config.cache_location, exist_ok=True)

            cache_meta_file = self.calculate_abs_path(".cache_meta")
            os.makedirs(os.path.dirname(cache_meta_file), exist_ok=True)
            with open(cache_meta_file, "w+") as f, self.cache_lock:
                f.write(json.dumps(self.cache, indent=2, cls=CacheManager.CacheEncoder))

        def save_file(self, absolute_path: Path, data: bytes):
            # Make the necessary directories and write to file.
            os.makedirs(absolute_path.parent, exist_ok=True)
            with open(absolute_path, "wb+") as f:
                f.write(data)

        def calculate_abs_path(self, *relative_paths) -> Path:
            assert self.app_config.server is not None
            return Path(self.app_config.cache_location).joinpath(
                self.app_config.server.strhash(), *relative_paths
            )

        @staticmethod
        def create_future(fn: Callable, *args) -> Future:
            """Creates a future on the CacheManager's executor."""
            return CacheManager.executor.submit(fn, *args)

        def get_indexes(
            self,
            before_download: Callable[[], None] = lambda: None,
            force: bool = False,
        ) -> "CacheManager.Result[List[Artist]]":
            cache_name = "indexes"

            if self.cache.get(cache_name) and not force:
                return CacheManager.Result.from_data(self.cache[cache_name])

            def download_fn() -> List[Artist]:
                artists: List[Artist] = []
                for index in self.server.get_indexes().index:
                    artists.extend(index.artist)
                return artists

            def after_download(artists: List[Artist]):
                with self.cache_lock:
                    self.cache[cache_name] = artists
                self.save_cache_info()

            return CacheManager.Result.from_server(
                download_fn,
                before_download=before_download,
                after_download=after_download,
            )

        def get_music_directory(
            self,
            id: int,
            before_download: Callable[[], None] = lambda: None,
            force: bool = False,
        ) -> "CacheManager.Result[Directory]":
            cache_name = "music_directories"

            if id in self.cache.get(cache_name, {}) and not force:
                return CacheManager.Result.from_data(self.cache[cache_name][id])

            def after_download(directory: Directory):
                with self.cache_lock:
                    self.cache[cache_name][id] = directory
                self.save_cache_info()

            return CacheManager.Result.from_server(
                lambda: self.server.get_music_directory(id),
                before_download=before_download,
                after_download=after_download,
            )

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self):
        raise Exception("Do not instantiate the CacheManager.")

    @staticmethod
    def reset(app_config: AppConfiguration):
        CacheManager._instance = CacheManager.__CacheManagerInternal(app_config)
