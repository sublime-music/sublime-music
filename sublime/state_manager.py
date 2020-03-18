import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import gi
gi.require_version('NetworkManager', '1.0')
gi.require_version('NMClient', '1.0')
from gi.repository import NetworkManager, NMClient

from .cache_manager import CacheManager
from .config import AppConfiguration
from .from_json import from_json
from .server.api_objects import Child


class RepeatType(Enum):
    NO_REPEAT = 0
    REPEAT_QUEUE = 1
    REPEAT_SONG = 2

    @property
    def icon(self) -> str:
        icon_name = [
            'repeat-symbolic',
            'repeat-symbolic',
            'repeat-song-symbolic',
        ][self.value]
        return f'media-playlist-{icon_name}'

    def as_mpris_loop_status(self) -> str:
        return ['None', 'Playlist', 'Track'][self.value]

    @staticmethod
    def from_mpris_loop_status(loop_status: str) -> 'RepeatType':
        return {
            'None': RepeatType.NO_REPEAT,
            'Track': RepeatType.REPEAT_SONG,
            'Playlist': RepeatType.REPEAT_QUEUE,
        }[loop_status]


class ApplicationState:
    """
    Represents the state of the application. In general, there are two things
    that are stored here: configuration, and UI state.

    Configuration is stored in ``config`` which is an ``AppConfiguration``
    object. UI state is stored as separate properties on this class.

    Configuration is stored to disk in $XDG_CONFIG_HOME/sublime-music. State is
    stored in $XDG_CACHE_HOME. Nothing in state should be assumed to be
    permanent. State need not be saved, the ``to_json`` and ``from_json``
    functions define what part of the state will be saved across application
    loads.
    """
    version: int = 1
    config: AppConfiguration = AppConfiguration()
    config_file: Optional[str] = None
    playing: bool = False
    current_song_index: int = -1
    play_queue: List[str] = []
    old_play_queue: List[str] = []
    _volume: Dict[str, float] = {'this device': 100.0}
    is_muted: bool = False
    repeat_type: RepeatType = RepeatType.NO_REPEAT
    shuffle_on: bool = False
    song_progress: float = 0
    current_device: str = 'this device'
    current_tab: str = 'albums'
    selected_album_id: Optional[str] = None
    selected_artist_id: Optional[str] = None
    selected_browse_element_id: Optional[str] = None
    selected_playlist_id: Optional[str] = None

    # State for Album sort.
    current_album_sort: str = 'random'
    current_album_genre: str = 'Rock'
    current_album_alphabetical_sort: str = 'name'
    current_album_from_year: int = 2010
    current_album_to_year: int = 2020

    active_playlist_id: Optional[str] = None

    networkmanager_client = NMClient.Client.new()
    nmclient_initialized = False
    _current_ssids: Set[str] = set()

    def to_json(self) -> Dict[str, Any]:
        exclude = ('config', 'repeat_type', '_current_ssids')
        json_object = {
            k: getattr(self, k)
            for k in self.__annotations__.keys()
            if k not in exclude
        }
        json_object.update(
            {
                'repeat_type':
                getattr(self, 'repeat_type', RepeatType.NO_REPEAT).value,
            })
        return json_object

    def load_from_json(self, json_object: Dict[str, Any]):
        self.version = json_object.get('version', 0)
        self.current_song_index = json_object.get('current_song_index', -1)
        self.play_queue = json_object.get('play_queue', [])
        self.old_play_queue = json_object.get('old_play_queue', [])
        self._volume = json_object.get('_volume', {'this device': 100.0})
        self.is_muted = json_object.get('is_muted', False)
        self.repeat_type = RepeatType(json_object.get('repeat_type', 0))
        self.shuffle_on = json_object.get('shuffle_on', False)
        self.song_progress = json_object.get('song_progress', 0.0)
        self.current_device = json_object.get('current_device', 'this device')
        self.current_tab = json_object.get('current_tab', 'albums')
        self.selected_album_id = json_object.get('selected_album_id', None)
        self.selected_artist_id = json_object.get('selected_artist_id', None)
        self.selected_browse_element_id = json_object.get(
            'selected_browse_element_id', None)
        self.selected_playlist_id = json_object.get(
            'selected_playlist_id', None)
        self.current_album_sort = json_object.get(
            'current_album_sort', 'random')
        self.current_album_genre = json_object.get(
            'current_album_genre', 'Rock')
        self.current_album_alphabetical_sort = json_object.get(
            'current_album_alphabetical_sort', 'name')
        self.current_album_from_year = json_object.get(
            'current_album_from_year', 2010)
        self.current_album_to_year = json_object.get(
            'current_album_to_year', 2020)
        self.active_playlist_id = json_object.get('active_playlist_id', None)

    def load(self):
        self.config = self.get_config(self.config_file)

        if self.config.server is None:
            self.load_from_json({})
            self.migrate()
            return

        CacheManager.reset(self.config, self.config.server, self.current_ssids)

        if os.path.exists(self.state_filename):
            with open(self.state_filename, 'r') as f:
                try:
                    self.load_from_json(json.load(f))
                except json.decoder.JSONDecodeError:
                    # Who cares, it's just state.
                    self.load_from_json({})

        self.migrate()

    def migrate(self):
        """Use this function to migrate any state storage that has changed."""
        self.config.migrate()
        self.save_config()

    def save(self):
        # Make the necessary directories before writing the state.
        os.makedirs(os.path.dirname(self.state_filename), exist_ok=True)

        # Save the state
        state_json = json.dumps(self.to_json(), indent=2, sort_keys=True)
        if not state_json:
            return
        with open(self.state_filename, 'w+') as f:
            f.write(state_json)

    def save_config(self):
        # Make the necessary directories before writing the config.
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        config_json = json.dumps(
            self.config.to_json(), indent=2, sort_keys=True)
        if not config_json:
            return
        with open(self.config_file, 'w+') as f:
            f.write(config_json)

    def get_config(self, filename: str) -> AppConfiguration:
        if not os.path.exists(filename):
            return AppConfiguration()

        with open(filename, 'r') as f:
            try:
                return from_json(AppConfiguration, json.load(f))
            except json.decoder.JSONDecodeError:
                return AppConfiguration()

    @property
    def current_ssids(self) -> Set[str]:
        if not self.nmclient_initialized:
            # Only look at the active WiFi connections.
            for ac in self.networkmanager_client.get_active_connections():
                if ac.get_connection_type() != '802-11-wireless':
                    continue
                devs = ac.get_devices()
                if len(devs) != 1:
                    continue
                if devs[0].get_device_type() != NetworkManager.DeviceType.WIFI:
                    continue

                self._current_ssids.add(ac.get_id())

        return self._current_ssids

    @property
    def state_filename(self) -> str:
        server_hash = CacheManager.calculate_server_hash(self.config.server)
        if not server_hash:
            raise Exception("Could not calculate the current server's hash.")

        default_cache_location = (
            os.environ.get('XDG_DATA_HOME')
            or os.path.expanduser('~/.local/share'))
        return os.path.join(
            default_cache_location,
            'sublime-music',
            server_hash,
            'state.yaml',
        )

    @property
    def current_song(self) -> Optional[Child]:
        if (not self.play_queue or self.current_song_index < 0
                or not CacheManager.ready()):
            return None

        current_song_id = self.play_queue[self.current_song_index]
        return CacheManager.get_song_details(current_song_id).result()

    @property
    def volume(self) -> float:
        return self._volume.get(self.current_device, 100.0)

    @volume.setter
    def volume(self, value: float):
        self._volume[self.current_device] = value
