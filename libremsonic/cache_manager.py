import os
import json

from enum import EnumMeta, Enum
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Union, Callable, Set

from libremsonic.config import AppConfiguration, ServerConfiguration
from libremsonic.server import Server
from libremsonic.server.api_object import APIObject
from libremsonic.server.api_objects import Playlist, PlaylistWithSongs, Child


class Singleton(type):
    def __getattr__(cls, name):
        if not CacheManager._instance:
            CacheManager.reset(None, None)
        # If the cache has a function to do the thing we want, use it. If
        # not, then go directly to the server (this is useful for things
        # that just send data  to the server.)
        if hasattr(CacheManager._instance, name):
            return getattr(CacheManager._instance, name)
        else:
            return getattr(CacheManager._instance.server, name)

        return None


class SongCacheStatus(Enum):
    NOT_CACHED = 0
    CACHED = 1
    PERMANENTLY_CACHED = 2
    DOWNLOADING = 3


class CacheManager(metaclass=Singleton):
    class CacheEncoder(json.JSONEncoder):
        def default(self, obj):
            if type(obj) == datetime:
                return int(obj.timestamp() * 1000)
            elif isinstance(obj, APIObject):
                return {k: v for k, v in obj.__dict__.items() if v is not None}
            elif isinstance(obj, EnumMeta):
                return None

            return json.JSONEncoder.default(self, obj)

    class __CacheManagerInternal:
        server: Server
        playlists: Optional[List[Playlist]] = None
        playlist_details: Dict[int, PlaylistWithSongs] = {}
        permanently_cached_paths: Set[str] = set()
        song_details: Dict[int, Child] = {}

        def __init__(
                self,
                app_config: AppConfiguration,
                server_config: ServerConfiguration,
        ):
            self.app_config = app_config
            self.server = Server(
                name=server_config.name,
                hostname=server_config.server_address,
                username=server_config.username,
                password=server_config.password,
            )

            self.load_cache_info()

        def load_cache_info(self):
            cache_meta_file = self.calculate_abs_path('.cache_meta')

            if not cache_meta_file.exists():
                return

            with open(cache_meta_file, 'r') as f:
                try:
                    meta_json = json.load(f)
                except json.decoder.JSONDecodeError:
                    return

            self.playlists = [
                Playlist.from_json(p) for p in meta_json.get('playlists', [])
            ]
            self.playlist_details = {
                id: PlaylistWithSongs.from_json(v)
                for id, v in meta_json.get('playlist_details', {}).items()
            }
            self.song_details = {
                id: Child.from_json(v)
                for id, v in meta_json.get('song_details', {}).items()
            }
            self.permanently_cached_paths = set(
                meta_json.get('permanently_cached_paths', []))

        def save_cache_info(self):
            os.makedirs(self.app_config.cache_location, exist_ok=True)

            cache_meta_file = self.calculate_abs_path('.cache_meta')
            with open(cache_meta_file, 'w+') as f:
                cache_info = dict(
                    playlists=self.playlists,
                    playlist_details=self.playlist_details,
                    song_details=self.song_details,
                    permanently_cached_paths=list(
                        self.permanently_cached_paths),
                )
                f.write(
                    json.dumps(cache_info,
                               indent=2,
                               cls=CacheManager.CacheEncoder))

        def save_file(self, absolute_path: Path, data: bytes):
            # Make the necessary directories and write to file.
            os.makedirs(absolute_path.parent, exist_ok=True)
            with open(absolute_path, 'wb+') as f:
                f.write(data)

        def calculate_abs_path(self, relative_path):
            return Path(self.app_config.cache_location).joinpath(relative_path)

        def return_cache_or_download(
                self,
                relative_path: Union[Path, str],
                download_fn: Callable[[], bytes],
                force: bool = False,
        ):
            abs_path = self.calculate_abs_path(relative_path)
            if not abs_path.exists() or force:
                print(abs_path, 'not found. Downloading...')
                self.save_file(abs_path, download_fn())

            return str(abs_path)

        def get_playlists(self, force: bool = False) -> List[Playlist]:
            if not self.playlists or force:
                self.playlists = self.server.get_playlists().playlist
                self.save_cache_info()

            return self.playlists

        def get_playlist(
                self,
                playlist_id: int,
                force: bool = False,
        ) -> PlaylistWithSongs:
            if not self.playlist_details.get(playlist_id) or force:
                self.playlist_details[playlist_id] = self.server.get_playlist(
                    playlist_id)
                self.save_cache_info()

            return self.playlist_details[playlist_id]

        def get_cover_art_filename(
                self,
                id: str,
                size: Union[str, int] = 200,
                force: bool = False,
        ) -> str:
            return self.return_cache_or_download(
                f'cover_art/{id}_{size}',
                lambda: self.server.get_cover_art(id, str(size)),
                force=force,
            )

        def get_song(self, song_id: int, force: bool = False) -> Child:
            if not self.song_details.get(song_id) or force:
                self.song_details[song_id] = self.server.get_song(song_id)
                self.save_cache_info()

            return self.song_details[song_id]

        def get_song_filename(self, song: Child, force: bool = False) -> str:
            return self.return_cache_or_download(
                song.path,
                lambda: self.server.download(song.id),
                force=force,
            )

        def get_cached_status(self, song: Child) -> SongCacheStatus:
            path = self.calculate_abs_path(song.path)
            if path.exists():
                if path in self.permanently_cached_paths:
                    return SongCacheStatus.PERMANENTLY_CACHED
                else:
                    return SongCacheStatus.CACHED

            return SongCacheStatus.NOT_CACHED

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, app_config, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            app_config, server_config)
