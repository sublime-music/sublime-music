import os
import json

from enum import EnumMeta
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Tuple

from libremsonic.config import AppConfiguration, ServerConfiguration
from libremsonic.server import Server
from libremsonic.server.api_object import APIObject
from libremsonic.server.api_objects import Playlist, PlaylistWithSongs, Child


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

        # {id -> {size -> file_location}}
        cover_art: DefaultDict[str, Dict[str, str]] = defaultdict(dict)

        # {id -> Child}
        song_details: Dict[int, Child] = {}

        # { (artist, album, title) -> file_location }
        song_cache: Dict[str, str] = {}

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
            cache_location = Path(self.app_config.cache_location)
            cache_meta_file = cache_location.joinpath('.cache_meta')

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
            self.cover_art = defaultdict(dict,
                                         **meta_json.get('cover_art', {}))
            self.song_details = {
                id: Child.from_json(v)
                for id, v in meta_json.get('song_details', {}).items()
            }
            self.song_cache = dict(**meta_json.get('song_cache', {}))

        def save_cache_info(self):
            cache_location = Path(self.app_config.cache_location)
            os.makedirs(cache_location, exist_ok=True)

            cache_meta_file = cache_location.joinpath('.cache_meta')
            with open(cache_meta_file, 'w+') as f:
                f.write(
                    json.dumps(
                        dict(
                            playlists=self.playlists,
                            playlist_details=self.playlist_details,
                            cover_art=self.cover_art,
                            song_details=self.song_details,
                            song_cache=self.song_cache,
                        ),
                        indent=2,
                        cls=CacheManager.CacheEncoder,
                    ))

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
                size: str = '200',
                force: bool = False,
        ) -> str:
            if not self.cover_art[id].get(size):
                raw_cover = self.server.get_cover_art(id, size)
                abs_path = self.save_file(f'cover_art/{id}_{size}', raw_cover)
                self.cover_art[id][size] = str(abs_path)
                self.save_cache_info()
                print('cover art cache not hit')

            return self.cover_art[id][size]

        def get_song(self, song_id: int, force: bool = False):
            if not self.song_details.get(song_id) or force:
                self.song_details[song_id] = self.server.get_song(song_id)
                self.save_cache_info()
                print('song info cache not hit')

            return self.song_details[song_id]

        def get_song_filename(self, song: Child, force: bool = False):
            if not self.song_cache.get(song.id) or force:
                raw_song = self.server.download(song.id)
                abs_path = self.save_file(song.path, raw_song)
                self.song_cache[song.id] = str(abs_path)
                self.save_cache_info()
                print('song file cache not hit')

            return self.song_cache[song.id]

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, app_config, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            app_config, server_config)
