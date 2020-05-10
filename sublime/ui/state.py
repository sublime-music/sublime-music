from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from sublime.adapters.api_objects import Song


class RepeatType(Enum):
    NO_REPEAT = 0
    REPEAT_QUEUE = 1
    REPEAT_SONG = 2

    @property
    def icon(self) -> str:
        icon_name = ["repeat-symbolic", "repeat-symbolic", "repeat-song-symbolic"][
            self.value
        ]
        return f"media-playlist-{icon_name}"

    def as_mpris_loop_status(self) -> str:
        return ["None", "Playlist", "Track"][self.value]

    @staticmethod
    def from_mpris_loop_status(loop_status: str) -> "RepeatType":
        return {
            "None": RepeatType.NO_REPEAT,
            "Track": RepeatType.REPEAT_SONG,
            "Playlist": RepeatType.REPEAT_QUEUE,
        }[loop_status]


@dataclass
class UIState:
    """Represents the UI state of the application."""

    version: int = 1
    playing: bool = False
    current_song_index: int = -1
    play_queue: Tuple[str, ...] = field(default_factory=tuple)
    old_play_queue: Tuple[str, ...] = field(default_factory=tuple)
    _volume: Dict[str, float] = field(default_factory=lambda: {"this device": 100.0})
    is_muted: bool = False
    repeat_type: RepeatType = RepeatType.NO_REPEAT
    shuffle_on: bool = False
    song_progress: float = 0
    current_device: str = "this device"
    current_tab: str = "albums"
    selected_album_id: Optional[str] = None
    selected_artist_id: Optional[str] = None
    selected_browse_element_id: Optional[str] = None
    selected_playlist_id: Optional[str] = None

    # State for Album sort.
    current_album_sort: str = "random"
    current_album_genre: str = "Rock"
    current_album_alphabetical_sort: str = "name"
    current_album_from_year: int = 2010
    current_album_to_year: int = 2020

    active_playlist_id: Optional[str] = None

    def migrate(self):
        pass

    _current_song: Optional[Song] = None

    @property
    def current_song(self) -> Optional[Song]:
        from sublime.adapters import AdapterManager

        if not self.play_queue or self.current_song_index < 0:
            return None

        current_song_id = self.play_queue[self.current_song_index]

        if not self._current_song or self._current_song.id != current_song_id:
            self._current_song = AdapterManager.get_song_details(
                current_song_id
            ).result()

        return self._current_song

    @property
    def volume(self) -> float:
        return self._volume.get(self.current_device, 100.0)

    @volume.setter
    def volume(self, value: float):
        self._volume[self.current_device] = value
