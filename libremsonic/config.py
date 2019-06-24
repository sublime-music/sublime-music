import os

from typing import Any, Dict, List
import json

from libremsonic.from_json import from_json


class ServerConfiguration:
    name: str
    server_address: str
    local_network_address: str
    local_network_ssid: str
    username: str
    password: str
    browse_by_tags: bool
    sync_enabled: bool

    def __init__(self,
                 name='Default',
                 server_address='http://yourhost',
                 local_network_address='',
                 local_network_ssid='',
                 username='',
                 password='',
                 browse_by_tags=False,
                 sync_enabled=True):

        self.name = name
        self.server_address = server_address
        self.local_network_address = local_network_address
        self.local_network_ssid = local_network_ssid
        self.username = username
        self.password = password
        self.browse_by_tags = browse_by_tags
        self.sync_enabled = sync_enabled


class AppConfiguration:
    servers: List[ServerConfiguration]
    current_server: int
    _cache_location: str
    max_cache_size_mb: int  # -1 means unlimited

    def to_json(self):
        return {
            'servers': [s.__dict__ for s in self.servers],
            'current_server': self.current_server,
            '_cache_location': self._cache_location,
            'max_cache_size_mb': self.max_cache_size_mb,
        }

    @classmethod
    def get_default_configuration(cls):
        config = AppConfiguration()
        config.servers = []
        config.current_server = -1
        config.max_cache_size_mb = -1
        return config

    @property
    def cache_location(self):
        if (hasattr(self, '_cache_location')
                and self._cache_location is not None):
            return self.cache_location
        else:
            default_cache_location = (os.environ.get('XDG_DATA_HOME')
                                      or os.path.expanduser('~/.local/share'))
            return os.path.join(default_cache_location, 'libremsonic')


def get_config(filename: str) -> AppConfiguration:
    if not os.path.exists(filename):
        return AppConfiguration.get_default_configuration()

    with open(filename, 'r') as f:
        try:
            return from_json(AppConfiguration, json.load(f))
        except json.decoder.JSONDecodeError:
            return AppConfiguration.get_default_configuration()


def save_config(config: AppConfiguration, filename: str):
    # Make the necessary directories before writing the config.
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w+') as f:
        f.write(json.dumps(config.to_json(), indent=2, sort_keys=True))
