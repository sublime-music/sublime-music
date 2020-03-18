import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional

import keyring


class ReplayGainType(Enum):
    NO = 0
    TRACK = 1
    ALBUM = 2

    def as_string(self) -> str:
        return ['no', 'track', 'album'][self.value]

    @staticmethod
    def from_string(replay_gain_type: str) -> 'ReplayGainType':
        return {
            'no': ReplayGainType.NO,
            'disabled': ReplayGainType.NO,
            'track': ReplayGainType.TRACK,
            'album': ReplayGainType.ALBUM,
        }[replay_gain_type.lower()]


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
        name: str = 'Default',
        server_address: str = 'http://yourhost',
        local_network_address: str = '',
        local_network_ssid: str = '',
        username: str = '',
        password: str = '',
        sync_enabled: bool = True,
        disable_cert_verify: bool = False,
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
    def password(self) -> str:
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
    version: int = 3
    serve_over_lan: bool = True
    replay_gain: ReplayGainType = ReplayGainType.NO

    def to_json(self) -> Dict[str, Any]:
        exclude = ('servers', 'replay_gain')
        json_object = {
            k: getattr(self, k)
            for k in self.__annotations__.keys()
            if k not in exclude
        }
        json_object.update(
            {
                'servers': [s.__dict__ for s in self.servers],
                'replay_gain':
                getattr(self, 'replay_gain', ReplayGainType.NO).value,
            })
        return json_object

    def migrate(self):
        for server in self.servers:
            server.migrate()

        if (getattr(self, 'version') or 0) < 2:
            logging.info('Migrating app configuration to version 2.')
            logging.info('Setting serve_over_lan to True')
            self.serve_over_lan = True

        if (getattr(self, 'version') or 0) < 3:
            logging.info('Migrating app configuration to version 3.')
            logging.info('Setting replay_gain to ReplayGainType.NO')
            self.replay_gain = ReplayGainType.NO

        self.version = 3

    @property
    def cache_location(self) -> str:
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
