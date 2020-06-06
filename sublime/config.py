import logging
import os
import pickle
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Type

import dataclasses_json
from dataclasses_json import dataclass_json, DataClassJsonMixin

from sublime.adapters import ConfigurationStore
from sublime.ui.state import UIState


# JSON decoder and encoder translations
decoder_functions = {
    Path: (lambda p: Path(p) if p else None),
}
encoder_functions = {
    Path: (lambda p: str(p.resolve()) if p else None),
}

for type_, translation_function in decoder_functions.items():
    dataclasses_json.cfg.global_config.decoders[type_] = translation_function
    dataclasses_json.cfg.global_config.decoders[Optional[type_]] = translation_function

for type_, translation_function in encoder_functions.items():
    dataclasses_json.cfg.global_config.encoders[type_] = translation_function
    dataclasses_json.cfg.global_config.encoders[Optional[type_]] = translation_function


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


@dataclass_json
@dataclass
class ProviderConfiguration:
    id: str
    name: str
    ground_truth_adapter_type: Type
    ground_truth_adapter_config: ConfigurationStore
    caching_adapter_type: Optional[Type] = None
    caching_adapter_config: Optional[ConfigurationStore] = None

    def migrate(self):
        self.ground_truth_adapter_type.migrate_configuration(
            self.ground_truth_adapter_config
        )
        if self.caching_adapter_type:
            self.caching_adapter_type.migrate_configuration(self.caching_adapter_config)


@dataclass
class AppConfiguration(DataClassJsonMixin):
    version: int = 5
    cache_location: Optional[Path] = None
    filename: Optional[Path] = None

    # Providers
    providers: Dict[str, ProviderConfiguration] = field(default_factory=dict)
    current_provider_id: Optional[str] = None

    # Global Settings
    song_play_notification: bool = True
    offline_mode: bool = False
    serve_over_lan: bool = True
    port_number: int = 8282
    replay_gain: ReplayGainType = ReplayGainType.NO
    allow_song_downloads: bool = True
    download_on_stream: bool = True  # also download when streaming a song
    prefetch_amount: int = 3
    concurrent_download_limit: int = 5

    # Deprecated
    always_stream: bool = False  # always stream instead of downloading songs

    @staticmethod
    def load_from_file(filename: Path) -> "AppConfiguration":
        config = AppConfiguration()
        try:
            if filename.exists():
                with open(filename, "r") as f:
                    config = AppConfiguration.from_json(f.read())
        except Exception:
            pass

        config.filename = filename
        config.save()
        return config

    def __post_init__(self):
        # Default the cache_location to ~/.local/share/sublime-music
        if not self.cache_location:
            path = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share")
            path = path.expanduser().joinpath("sublime-music").resolve()
            self.cache_location = str(path)

        self._state = None
        self._current_provider_id = None
        self.migrate()

    def migrate(self):
        for _, provider in self.providers.items():
            provider.migrate()

        self.version = 5
        self.state.migrate()

    @property
    def provider(self) -> Optional[ProviderConfiguration]:
        return self.providers.get(self._current_provider_id or "")

    @property
    def state(self) -> UIState:
        if not (provider := self.provider):
            return UIState()

        # If the provider has changed, then retrieve the new provider's state.
        if self._current_provider_id != provider.id:
            self.load_state()

        return self._state

    def load_state(self):
        self._state = UIState()
        if not (provider := self.provider):
            return

        self._current_provider_id = provider.id
        if (state_filename := self._state_file_location) and state_filename.exists():
            try:
                with open(state_filename, "rb") as f:
                    self._state = pickle.load(f)
            except Exception:
                logging.warning(f"Couldn't load state from {state_filename}")
                # Just ignore any errors, it is only UI state.
                self._state = UIState()

    @property
    def _state_file_location(self) -> Optional[Path]:
        if not (provider := self.provider):
            return None

        state_filename = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share")
        return state_filename.expanduser().joinpath(
            "sublime-music", provider.id, "state.pickle"
        )

    def save(self):
        # Save the config as YAML.
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w+") as f:
            f.write(self.to_json(indent=2, sort_keys=True))

        # Save the state for the current provider.
        if state_filename := self._state_file_location:
            state_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(state_filename, "wb+") as f:
                pickle.dump(self.state, f)
