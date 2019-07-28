import os
from enum import Enum
import json
from typing import List

from libremsonic.from_json import from_json
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


class ApplicationState:
    """
    Represents the state of the application. In general, there are two things
    that are stored here: configuration, and UI state.

    Configuration is stored in ``config`` which is an ``AppConfiguration``
    object. UI state is stored as separate properties on this class.

    Configuration is stored to disk in $XDG_CONFIG_HOME/libremsonic. State is
    stored in $XDG_CACHE_HOME. Nothing in state should be assumed to be
    permanent. State need not be saved, the ``to_json`` and ``from_json``
    functions define what part of the state will be saved across application
    loads.
    """
    config: AppConfiguration = AppConfiguration.get_default_configuration()
    current_song: Child
    config_file: str
    playing: bool = False
    play_queue: List[str]
    old_play_queue: List[str]
    volume: int = 100
    old_volume: int = 100
    repeat_type: RepeatType = RepeatType.NO_REPEAT
    shuffle_on: bool = False
    song_progress: float = 0

    def to_json(self):
        current_song = (self.current_song.id if
                        (hasattr(self, 'current_song')
                         and self.current_song is not None) else None)
        return {
            'current_song': current_song,
            'play_queue': getattr(self, 'play_queue', None),
            'old_play_queue': getattr(self, 'old_play_queue', None),
            'volume': getattr(self, 'volume', None),
            'repeat_type': getattr(self, 'repeat_type',
                                   RepeatType.NO_REPEAT).value,
            'shuffle_on': getattr(self, 'shuffle_on', None),
            'song_progress': getattr(self, 'song_progress', None),
        }

    def load_from_json(self, json_object):
        current_song_id = json_object.get('current_song') or None
        if current_song_id:
            self.current_song = CacheManager.cache['song_details'].get(
                current_song_id)
        else:
            self.current_song = None

        self.play_queue = json_object.get('play_queue') or []
        self.old_play_queue = json_object.get('old_play_queue') or []
        self.volume = json_object.get('volume') or 100
        self.repeat_type = (RepeatType(json_object.get('repeat_type'))
                            or RepeatType.NO_REPEAT)
        self.shuffle_on = json_object.get('shuffle_on', False)
        self.song_progress = json_object.get('song_progress', 0.0)

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
            f.write(json.dumps(self.config.to_json(), indent=2,
                               sort_keys=True))

        # Save the state
        with open(self.state_filename, 'w+') as f:
            f.write(json.dumps(self.to_json(), indent=2, sort_keys=True))

    def get_config(self, filename: str) -> AppConfiguration:
        if not os.path.exists(filename):
            return AppConfiguration.get_default_configuration()

        with open(filename, 'r') as f:
            try:
                return from_json(AppConfiguration, json.load(f))
            except json.decoder.JSONDecodeError:
                return AppConfiguration.get_default_configuration()

    @property
    def state_filename(self):
        state_filename = (os.environ.get('XDG_CACHE_HOME')
                          or os.path.expanduser('~/.cache'))
        return os.path.join(state_filename, 'libremsonic/state.yaml')
