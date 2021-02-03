from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set, Tuple, Type

from ..adapters import AlbumSearchQuery
from ..adapters.api_objects import Genre, Song
from ..util import this_decade


class RepeatType(Enum):
    NO_REPEAT = 0
    REPEAT_QUEUE = 1
    REPEAT_SONG = 2

    @property
    def icon(self) -> str:
        """
        Get the icon for the repeat type.

        >>> RepeatType.NO_REPEAT.icon, RepeatType.REPEAT_QUEUE.icon
        ('media-playlist-repeat-symbolic', 'media-playlist-repeat-symbolic')
        >>> RepeatType.REPEAT_SONG.icon
        'media-playlist-repeat-song-symbolic'
        """
        song_str = "-song" if self == RepeatType.REPEAT_SONG else ""
        return f"media-playlist-repeat{song_str}-symbolic"

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

    @dataclass(unsafe_hash=True)
    class UINotification:
        markup: str
        actions: Tuple[Tuple[str, Callable[[], None]], ...] = field(
            default_factory=tuple
        )
        icon: Optional[str] = None

    version: int = 1

    # Play state
    playing: bool = False
    current_song_index: int = -1
    play_queue: Tuple[str, ...] = field(default_factory=tuple)
    old_play_queue: Tuple[str, ...] = field(default_factory=tuple)
    _volume: Dict[str, float] = field(default_factory=lambda: {"this device": 100.0})
    is_muted: bool = False
    repeat_type: RepeatType = RepeatType.NO_REPEAT
    shuffle_on: bool = False
    song_progress: timedelta = timedelta()
    song_stream_cache_progress: Optional[timedelta] = timedelta()
    current_device: str = "this device"
    connecting_to_device: bool = False
    connected_device_name: Optional[str] = None
    available_players: Dict[Type, Set[Tuple[str, str]]] = field(default_factory=dict)

    # UI state
    current_tab: str = "albums"
    selected_album_id: Optional[str] = None
    selected_artist_id: Optional[str] = None
    selected_browse_element_id: Optional[str] = None
    selected_playlist_id: Optional[str] = None
    album_sort_direction: str = "ascending"
    album_page_size: int = 30
    album_page: int = 0
    current_notification: Optional[UINotification] = None
    playlist_details_expanded: bool = True
    artist_details_expanded: bool = True
    loading_play_queue: bool = False

    # State for Album sort.
    class _DefaultGenre(Genre):
        def __init__(self):
            self.name = "Rock"

    current_album_search_query: AlbumSearchQuery = AlbumSearchQuery(
        AlbumSearchQuery.Type.RANDOM,
        genre=_DefaultGenre(),
        year_range=this_decade(),
    )

    active_playlist_id: Optional[str] = None

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["song_stream_cache_progress"]
        del state["current_notification"]
        del state["playing"]
        del state["available_players"]
        return state

    def __setstate__(self, state: Dict[str, Any]):
        self.__dict__.update(state)
        self.song_stream_cache_progress = None
        self.current_notification = None
        self.playing = False

    def __init_available_players__(self):
        from sublime_music.players import PlayerManager

        self.available_players = {
            pt: set() for pt in PlayerManager.available_player_types
        }

    def migrate(self):
        pass

    _current_song: Optional[Song] = None

    @property
    def current_song(self) -> Optional[Song]:
        if not self.play_queue or self.current_song_index < 0:
            return None

        from sublime_music.adapters import AdapterManager

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
