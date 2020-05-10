import hashlib
import logging
import os
import pickle
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import List, Optional

import yaml

from sublime.ui.state import UIState


class ReplayGainType(Enum):
    NO = 0
    TRACK = 1
    ALBUM = 2

    def as_string(self) -> str:
        return ["no", "track", "album"][self.value]

    @staticmethod
    def from_string(replay_gain_type: str) -> "ReplayGainType":
        return {
            "no": ReplayGainType.NO,
            "disabled": ReplayGainType.NO,
            "track": ReplayGainType.TRACK,
            "album": ReplayGainType.ALBUM,
        }[replay_gain_type.lower()]


@dataclass(unsafe_hash=True)
class ServerConfiguration:
    name: str = "Default"
    server_address: str = "http://yourhost"
    local_network_address: str = ""
    local_network_ssid: str = ""
    username: str = ""
    password: str = ""
    sync_enabled: bool = True
    disable_cert_verify: bool = False
    version: int = 0

    def migrate(self):
        self.version = 0

    def strhash(self) -> str:
        # TODO: needs to change to something better
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
        server_info = self.name + self.server_address + self.username
        return hashlib.md5(server_info.encode("utf-8")).hexdigest()


@dataclass
class AppConfiguration:
    servers: List[ServerConfiguration] = field(default_factory=list)
    current_server_index: int = -1
    cache_location: str = ""
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
    filename: Optional[Path] = None

    @staticmethod
    def load_from_file(filename: Path) -> "AppConfiguration":
        args = {}
        if filename.exists():
            with open(filename, "r") as f:
                field_names = {f.name for f in fields(AppConfiguration)}
                args = yaml.load(f, Loader=yaml.CLoader).items()
                args = dict(filter(lambda kv: kv[0] in field_names, args))

        config = AppConfiguration(**args)
        config.filename = filename

        return config

    def __post_init__(self):
        # Default the cache_location to ~/.local/share/sublime-music
        if not self.cache_location:
            path = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share")
            path = path.expanduser().joinpath("sublime-music").resolve()
            self.cache_location = path.as_posix()

        # Deserialize the YAML into the ServerConfiguration object.
        if len(self.servers) > 0 and type(self.servers[0]) != ServerConfiguration:
            self.servers = [ServerConfiguration(**sc) for sc in self.servers]

        self._state = None
        self._current_server_hash = None

    def migrate(self):
        for server in self.servers:
            server.migrate()
        self.version = 3
        self.state.migrate()

    @property
    def server(self) -> Optional[ServerConfiguration]:
        if 0 <= self.current_server_index < len(self.servers):
            return self.servers[self.current_server_index]

        return None

    @property
    def state(self) -> UIState:
        server = self.server
        if not server:
            return UIState()

        # If the server has changed, then retrieve the new server's state.
        # TODO: if things are slow, then use a different hash
        if self._current_server_hash != server.strhash():
            self.load_state()

        return self._state

    def load_state(self):
        self._state = UIState()
        if not self.server:
            return

        self._current_server_hash = self.server.strhash()
        if self.state_file_location.exists():
            try:
                with open(self.state_file_location, "rb") as f:
                    self._state = UIState(**pickle.load(f))
            except Exception:
                logging.warning(f"Couldn't load state from {self.state_file_location}")
                # Just ignore any errors, it is only UI state.
                self._state = UIState()

        # Do the import in the function to avoid circular imports.
        from sublime.cache_manager import CacheManager
        from sublime.adapters import AdapterManager

        CacheManager.reset(self)
        AdapterManager.reset(self)

    @property
    def state_file_location(self) -> Path:
        assert self.server is not None
        server_hash = self.server.strhash()

        state_file_location = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share")
        return state_file_location.expanduser().joinpath(
            "sublime-music", server_hash, "state.pickle"
        )

    def save(self):
        # Save the config as YAML.
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w+") as f:
            f.write(yaml.dump(asdict(self)))

        # Save the state for the current server.
        self.state_file_location.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file_location, "wb+") as f:
            pickle.dump(asdict(self.state), f)
