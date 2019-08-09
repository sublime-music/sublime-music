import os

from typing import List


class ServerConfiguration:
    name: str
    server_address: str
    local_network_address: str
    local_network_ssid: str
    username: str
    password: str
    browse_by_tags: bool
    sync_enabled: bool

    def __init__(
            self,
            name='Default',
            server_address='http://yourhost',
            local_network_address='',
            local_network_ssid='',
            username='',
            password='',
            browse_by_tags=False,
            sync_enabled=True,
    ):
        self.name = name
        self.server_address = server_address
        self.local_network_address = local_network_address
        self.local_network_ssid = local_network_ssid
        self.username = username
        self.password = password
        self.browse_by_tags = browse_by_tags
        self.sync_enabled = sync_enabled


class AppConfiguration:
    servers: List[ServerConfiguration] = []
    current_server: int = -1
    _cache_location: str = ''
    max_cache_size_mb: int = -1  # -1 means unlimited
    show_headers: bool = True  # show the headers on song lists
    always_stream: bool = False  # always stream instead of downloading songs
    download_on_stream: bool = True  # also download when streaming a song
    prefetch_amount: int = 3
    concurrent_download_limit: int = 5

    def to_json(self):
        # TODO can we simplify?
        return {
            'servers': [s.__dict__ for s in self.servers],
            'current_server': self.current_server,
            '_cache_location': getattr(self, '_cache_location', None),
            'max_cache_size_mb': self.max_cache_size_mb,
            'show_headers': self.show_headers,
            'always_stream': self.always_stream,
            'download_on_stream': self.download_on_stream,
            'prefetch_amount': self.prefetch_amount,
            'concurrent_download_limit': self.concurrent_download_limit,
        }

    @property
    def cache_location(self):
        if (hasattr(self, '_cache_location')
                and self._cache_location is not None
                and self._cache_location != ''):
            return self._cache_location
        else:
            default_cache_location = (os.environ.get('XDG_DATA_HOME')
                                      or os.path.expanduser('~/.local/share'))
            return os.path.join(default_cache_location, 'libremsonic')
