import os
from pathlib import Path
import json
from typing import List

from libremsonic.from_json import from_json
from .config import AppConfiguration
from .server.api_objects import Child


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
    volume: int = 100
    old_volume: int = 100

    def to_json(self):
        return {
            'current_song': getattr(self, 'current_song', None),
            'play_queue': getattr(self, 'play_queue', None),
            'volume': getattr(self, 'volume', None),
        }

    def load_from_json(self, json_object):
        self.current_song = json_object.get('current_song') or None
        self.play_queue = json_object.get('play_queue') or []
        self.volume = json_object.get('volume') or 100

    def load(self):
        self.config = self.get_config(self.config_file)

        if os.path.exists(self.state_filename):
            with open(self.state_filename, 'r') as f:
                self.load_from_json(json.load(f))

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
