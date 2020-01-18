import os
import keyring

from typing import List, Optional


class ServerConfiguration:
    version: int
    name: str
    server_address: str
    local_network_address: str
    local_network_ssid: str
    username: str
    sync_enabled: bool
    disable_cert_verify: bool

    def __init__(
        self,
        name='Default',
        server_address='http://yourhost',
        local_network_address='',
        local_network_ssid='',
        username='',
        password='',
        sync_enabled=True,
        disable_cert_verify=False,
    ):
        self.name = name
        self.server_address = server_address
        self.local_network_address = local_network_address
        self.local_network_ssid = local_network_ssid
        self.username = username
        keyring.set_password(
            'com.sumnerevans.SublimeMusic',
            f'{self.username}@{self.server_address}',
            password,
        )
        self.sync_enabled = sync_enabled
        self.disable_cert_verify = disable_cert_verify

    def migrate(self):
        pass

    @property
    def password(self):
        return keyring.get_password(
            'com.sumnerevans.SublimeMusic',
            f'{self.username}@{self.server_address}',
        )


class AppConfiguration:
    servers: List[ServerConfiguration] = []
    current_server: int = -1
    _cache_location: str = ''
    max_cache_size_mb: int = -1  # -1 means unlimited
    always_stream: bool = False  # always stream instead of downloading songs
    download_on_stream: bool = True  # also download when streaming a song
    song_play_notification: bool = True
    prefetch_amount: int = 3
    concurrent_download_limit: int = 5
    port_number: int = 8282
    version: int = 1

    def to_json(self):
        exclude = ('servers')
        json_object = {
            k: getattr(self, k)
            for k in self.__annotations__.keys()
            if k not in exclude
        }
        json_object.update({
            'servers': [s.__dict__ for s in self.servers],
        })
        return json_object

    def migrate(self):
        for server in self.servers:
            server.migrate()

    @property
    def cache_location(self):
        if (hasattr(self, '_cache_location')
                and self._cache_location is not None
                and self._cache_location != ''):
            return self._cache_location
        else:
            default_cache_location = (
                os.environ.get('XDG_DATA_HOME')
                or os.path.expanduser('~/.local/share'))
            return os.path.join(default_cache_location, 'sublime-music')

    @property
    def server(self) -> Optional[ServerConfiguration]:
        if 0 <= self.current_server < len(self.servers):
            return self.servers[self.current_server]

        return None
