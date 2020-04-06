import hashlib
import os
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

try:
    import keyring

    has_keyring = True
except ImportError:
    has_keyring = False

from sublime.state_manager import ApplicationState


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


@dataclass
class ServerConfiguration:
    name: str = 'Default'
    server_address: str = 'http://yourhost'
    local_network_address: str = ''
    local_network_ssid: str = ''
    username: str = ''
    password: str = ''
    sync_enabled: bool = True
    disable_cert_verify: bool = False
    version: int = 0

    def migrate(self):
        self.version = 0

    def strhash(self) -> str:
        """
        Returns the MD5 hash of the server's name, server address, and
        username. This should be used whenever it's necessary to uniquely
        identify the server, rather than using the name (which is not
        necessarily unique).

        >>> sc = ServerConfiguration(
        ...     name='foo',
        ...     server_address='bar',
        ...     username='baz',
        ... )
        >>> sc.strhash()
        '6df23dc03f9b54cc38a0fc1483df6e21'
        """
        server_info = (self.name + self.server_address + self.username)
        return hashlib.md5(server_info.encode('utf-8')).hexdigest()


@dataclass
class AppConfiguration:
    servers: List[ServerConfiguration] = field(default_factory=list)
    current_server: int = -1
    cache_location: str = ''
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

    @staticmethod
    def load_from_file(filename: str) -> 'AppConfiguration':
        if not Path(filename).exists():
            return AppConfiguration()

        with open(filename, 'r') as f:
            return AppConfiguration(**yaml.load(f, Loader=yaml.CLoader))

    def __post_init__(self):
        # Default the cache_location to ~/.local/share/sublime-music
        if not self.cache_location:
            path = Path(os.environ.get('XDG_DATA_HOME') or '~/.local/share')
            path = path.expanduser().joinpath('sublime-music').resolve()
            self.cache_location = path.as_posix()

        # Deserialize the YAML into the ServerConfiguration object.
        if (len(self.servers) > 0
                and type(self.servers[0]) != ServerConfiguration):
            self.servers = [ServerConfiguration(**sc) for sc in self.servers]

        self._state = None

    def migrate(self):
        for server in self.servers:
            server.migrate()
        self.version = 3

    @property
    def server(self) -> Optional[ServerConfiguration]:
        if 0 <= self.current_server < len(self.servers):
            return self.servers[self.current_server]

        return None

    @property
    def state(self) -> ApplicationState:
        pass
