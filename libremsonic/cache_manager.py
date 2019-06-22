from typing import Dict, List, Optional

from libremsonic.config import ServerConfiguration
from libremsonic.server import Server
from libremsonic.server.api_objects import Playlist, PlaylistWithSongs


class Singleton(type):
    def __getattr__(cls, name):
        if CacheManager._instance:
            return getattr(CacheManager._instance, name)
        return None


class CacheManager(metaclass=Singleton):
    class __CacheManagerInternal:
        server: Server
        playlists: Optional[List[Playlist]] = None
        playlist_details: Dict[int, PlaylistWithSongs] = {}

        def __init__(self, server_config: ServerConfiguration):
            self.server = Server(
                name=server_config.name,
                hostname=server_config.server_address,
                username=server_config.username,
                password=server_config.password,
            )

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

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            server_config)
