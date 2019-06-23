import os
from pathlib import Path
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Tuple

from libremsonic.config import AppConfiguration, ServerConfiguration
from libremsonic.server import Server
from libremsonic.server.api_objects import Playlist, PlaylistWithSongs


class Singleton(type):
    def __getattr__(cls, name):
        if CacheManager._instance:
            # If the cache has a function to do the thing we want, use it. If
            # not, then go directly to the server (this is useful for things
            # that just send data  to the server.)
            if hasattr(CacheManager._instance, name):
                return getattr(CacheManager._instance, name)
            else:
                return getattr(CacheManager._instance.server, name)
        return None


class CacheManager(metaclass=Singleton):
    class __CacheManagerInternal:
        server: Server
        playlists: Optional[List[Playlist]] = None
        playlist_details: Dict[int, PlaylistWithSongs] = {}

        # {id -> {size -> file_location}}
        cover_art: DefaultDict[str, Dict[str, Path]] = defaultdict(dict)

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

        def save_file(self, relative_path: str, data: bytes) -> Path:
            cache_location = Path(self.app_config.cache_location)
            absolute_path = cache_location.joinpath(relative_path)

            # Make the necessary directories and write to file.
            os.makedirs(absolute_path.parent, exist_ok=True)
            with open(absolute_path, 'wb+') as f:
                f.write(data)
            return absolute_path

        def get_playlists(self, force: bool = False) -> List[Playlist]:
            if not self.playlists or force:
                self.playlists = self.server.get_playlists().playlist

            return self.playlists

        def get_playlist(
                self,
                playlist_id: int,
                force: bool = False,
        ) -> PlaylistWithSongs:
            if not self.playlist_details.get(playlist_id) or force:
                self.playlist_details[playlist_id] = self.server.get_playlist(
                    playlist_id)

            return self.playlist_details[playlist_id]

        def get_cover_art(
                self,
                id: str,
                size: str = '200',
                force: bool = False,
        ) -> str:
            if not self.cover_art[id].get(size):
                raw_cover = self.server.get_cover_art(id, size)
                abs_path = self.save_file(f'cover_art/{id}_{size}', raw_cover)
                self.cover_art[id][size] = abs_path

            return str(self.cover_art[id][size])

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, app_config, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            app_config, server_config)
