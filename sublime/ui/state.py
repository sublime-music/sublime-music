import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

try:
    import gi
    gi.require_version('NM', '1.0')
    from gi.repository import NM
    networkmanager_imported = True
except Exception:
    # I really don't care what kind of exception it is, all that matters is the
    # import failed for some reason.
    logging.warning(
        'Unable to import NM from GLib. Detection of SSID will be disabled.')
    networkmanager_imported = False

from sublime.server.api_objects import Child


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


@dataclass
class UIState:
    """Represents the UI state of the application."""
    version: int = 1
    playing: bool = False
    current_song_index: int = -1
    play_queue: List[str] = field(default_factory=list)
    old_play_queue: List[str] = field(default_factory=list)
    _volume: Dict[str, float] = field(
        default_factory=lambda: {'this device': 100.0})
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

    def __post_init__(self):
        if networkmanager_imported:
            self.networkmanager_client = NM.Client.new()
        self.nmclient_initialized = False
        self._current_ssids: Set[str] = set()

    def migrate(self):
        pass

    @property
    def current_ssids(self) -> Set[str]:
        if not networkmanager_imported:
            return set()
        if not self.nmclient_initialized:
            # Only look at the active WiFi connections.
            for ac in self.networkmanager_client.get_active_connections():
                if ac.get_connection_type() != '802-11-wireless':
                    continue
                devs = ac.get_devices()
                if len(devs) != 1:
                    continue
                if devs[0].get_device_type() != NM.DeviceType.WIFI:
                    continue

                self._current_ssids.add(ac.get_id())

        return self._current_ssids

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
