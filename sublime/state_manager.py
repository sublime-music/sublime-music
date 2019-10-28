import os
from enum import Enum
import json
from typing import List

from .from_json import from_json
from .config import AppConfiguration
from .cache_manager import CacheManager
from .server.api_objects import Child


class RepeatType(Enum):
    NO_REPEAT = 0
    REPEAT_QUEUE = 1
    REPEAT_SONG = 2

    @property
    def icon(self):
        icon_name = [
            'repeat',
            'repeat-symbolic',
            'repeat-song-symbolic',
        ][self.value]
        return 'media-playlist-' + icon_name

    def as_mpris_loop_status(self):
        return ['None', 'Playlist', 'Track'][self.value]

    @staticmethod
    def from_mpris_loop_status(loop_status):
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
    config: AppConfiguration = AppConfiguration()
    current_song: Child = None
    config_file: str = None
    playing: bool = False
    play_queue: List[str] = []
    old_play_queue: List[str] = []
    _volume: dict = {'this device': 100}
    is_muted: bool = False
    repeat_type: RepeatType = RepeatType.NO_REPEAT
    shuffle_on: bool = False
    song_progress: float = 0
    current_device: str = 'this device'
    current_tab: str = 'albums'
    selected_album_id: str = None
    selected_artist_id: str = None
    selected_playlist_id: str = None

    # State for Album sort.
    current_album_sort: str = 'random'
    current_album_genre: str = 'Rock'
    current_album_alphabetical_sort: str = 'name'
    current_album_from_year: int = 2010
    current_album_to_year: int = 2020

    active_playlist_id: str = None

    def to_json(self):
        current_song = (
            self.current_song.id if
            (hasattr(self, 'current_song')
             and self.current_song is not None) else None)
        # TODO this really sucks. We should fix this.
        return {
            'current_song':
            current_song,
            'play_queue':
            getattr(self, 'play_queue', None),
            'old_play_queue':
            getattr(self, 'old_play_queue', None),
            '_volume':
            getattr(self, '_volume', {}),
            'is_muted':
            getattr(self, 'is_muted', None),
            'repeat_type':
            getattr(self, 'repeat_type', RepeatType.NO_REPEAT).value,
            'shuffle_on':
            getattr(self, 'shuffle_on', None),
            'song_progress':
            getattr(self, 'song_progress', None),
            'current_device':
            getattr(self, 'current_device', 'this device'),
            'current_tab':
            getattr(self, 'current_tab', 'albums'),
            'selected_album_id':
            getattr(self, 'selected_album_id', None),
            'selected_artist_id':
            getattr(self, 'selected_artist_id', None),
            'selected_playlist_id':
            getattr(self, 'selected_playlist_id', None),
            'current_album_sort':
            getattr(self, 'current_album_sort', None),
            'current_album_genre':
            getattr(self, 'current_album_genre', None),
            'current_album_alphabetical_sort':
            getattr(self, 'current_album_alphabetical_sort', None),
            'current_album_from_year':
            getattr(self, 'current_album_from_year', None),
            'current_album_to_year':
            getattr(self, 'current_album_to_year', None),
            'active_playlist_id':
            getattr(self, 'active_playlist_id', None),
        }

    def load_from_json(self, json_object):
        current_song_id = json_object.get('current_song') or None
        if current_song_id and CacheManager.cache:
            self.current_song = CacheManager.cache['song_details'].get(
                current_song_id)
        else:
            self.current_song = None

        self.play_queue = json_object.get('play_queue') or []
        self.old_play_queue = json_object.get('old_play_queue') or []
        self._volume = json_object.get('_volume') or {'this device': 100}
        self.is_muted = json_object.get('is_muted') or False
        self.repeat_type = (
            RepeatType(json_object.get('repeat_type')) or RepeatType.NO_REPEAT)
        self.shuffle_on = json_object.get('shuffle_on', False)
        self.song_progress = json_object.get('song_progress', 0.0)
        self.current_device = json_object.get('current_device', 'this device')
        self.current_tab = json_object.get('current_tab', 'albums')
        self.selected_album_id = json_object.get('selected_album_id', None)
        self.selected_artist_id = json_object.get('selected_artist_id', None)
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

        if self.config.current_server >= 0:
            # Reset the CacheManager.
            CacheManager.reset(
                self.config,
                self.config.servers[self.config.current_server]
                if self.config.current_server >= 0 else None,
            )

        if os.path.exists(self.state_filename):
            with open(self.state_filename, 'r') as f:
                try:
                    self.load_from_json(json.load(f))
                except json.decoder.JSONDecodeError:
                    # Who cares, it's just state.
                    pass

    def save(self):
        # Make the necessary directories before writing the config and state.
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.state_filename), exist_ok=True)

        # Save the config
        with open(self.config_file, 'w+') as f:
            f.write(
                json.dumps(self.config.to_json(), indent=2, sort_keys=True))

        # Save the state
        with open(self.state_filename, 'w+') as f:
            f.write(json.dumps(self.to_json(), indent=2, sort_keys=True))

    def get_config(self, filename: str) -> AppConfiguration:
        if not os.path.exists(filename):
            return AppConfiguration()

        with open(filename, 'r') as f:
            try:
                return from_json(AppConfiguration, json.load(f))
            except json.decoder.JSONDecodeError:
                return AppConfiguration()

    @property
    def state_filename(self):
        default_cache_location = (
            os.environ.get('XDG_DATA_HOME')
            or os.path.expanduser('~/.local/share'))
        return os.path.join(default_cache_location, 'sublime-music/state.yaml')

    @property
    def volume(self):
        return self._volume.get(self.current_device, 100)

    @volume.setter
    def volume(self, value):
        self._volume[self.current_device] = value
