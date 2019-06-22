from libremsonic.config import ServerConfiguration
from libremsonic.server import Server


class CacheManager:
    server: Server

    def __init__(self, server_config: ServerConfiguration):
        self.server = Server(
            name=server_config.name,
            hostname=server_config.server_address,
            username=server_config.username,
            password=server_config.password,
        )

    def get_playlists(self):
        return self.server.get_playlists()
