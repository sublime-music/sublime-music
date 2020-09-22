import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, Dict, Optional, Tuple, Type, Union

import dataclasses_json
from dataclasses_json import config, DataClassJsonMixin

from .adapters import ConfigurationStore
from .ui.state import UIState


# JSON decoder and encoder translations
def encode_path(path: Path) -> str:
    return str(path.resolve())


dataclasses_json.cfg.global_config.decoders[Path] = Path
dataclasses_json.cfg.global_config.decoders[Optional[Path]] = (  # type: ignore
    lambda p: Path(p) if p else None
)


dataclasses_json.cfg.global_config.encoders[Path] = encode_path
dataclasses_json.cfg.global_config.encoders[
    Optional[Path]  # type: ignore
] = encode_path


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

    def clone(self) -> "ProviderConfiguration":
        return ProviderConfiguration(
            self.id,
            self.name,
            self.ground_truth_adapter_type,
            self.ground_truth_adapter_config.clone(),
            self.caching_adapter_type,
            (
                self.caching_adapter_config.clone()
                if self.caching_adapter_config
                else None
            ),
        )

    def persist_secrets(self):
        self.ground_truth_adapter_config.persist_secrets()
        if self.caching_adapter_config:
            self.caching_adapter_config.persist_secrets()


def encode_providers(
    providers_dict: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    return {
        id_: {
            **config,
            "ground_truth_adapter_type": config["ground_truth_adapter_type"].__name__,
            "caching_adapter_type": (
                cast(type, config.get("caching_adapter_type")).__name__
                if config.get("caching_adapter_type")
                else None
            ),
        }
        for id_, config in providers_dict.items()
    }


def decode_providers(
    providers_dict: Dict[str, Dict[str, Any]]
) -> Dict[str, ProviderConfiguration]:
    from sublime_music.adapters import AdapterManager

    def find_adapter_type(type_name: str) -> Type:
        for available_adapter in AdapterManager.available_adapters:
            if available_adapter.__name__ == type_name:
                return available_adapter
        raise Exception(f"Couldn't find adapter of type {type_name}")

    return {
        id_: ProviderConfiguration(
            config["id"],
            config["name"],
            ground_truth_adapter_type=find_adapter_type(
                config["ground_truth_adapter_type"]
            ),
            ground_truth_adapter_config=ConfigurationStore(
                **config["ground_truth_adapter_config"]
            ),
            caching_adapter_type=(
                find_adapter_type(cat)
                if (cat := config.get("caching_adapter_type"))
                else None
            ),
            caching_adapter_config=(
                ConfigurationStore(**(config.get("caching_adapter_config") or {}))
            ),
        )
        for id_, config in providers_dict.items()
    }


@dataclass
class AppConfiguration(DataClassJsonMixin):
    version: int = 5
    cache_location: Optional[Path] = None
    filename: Optional[Path] = None

    # Providers
    providers: Dict[str, ProviderConfiguration] = field(
        default_factory=dict,
        metadata=config(encoder=encode_providers, decoder=decode_providers),
    )
    current_provider_id: Optional[str] = None
    _loaded_provider_id: Optional[str] = field(default=None, init=False)

    # Players
    player_config: Dict[str, Dict[str, Union[Type, Tuple[str, ...]]]] = field(
        default_factory=dict
    )

    # Global Settings
    song_play_notification: bool = True
    offline_mode: bool = False
    allow_song_downloads: bool = True
    download_on_stream: bool = True  # also download when streaming a song
    prefetch_amount: int = 3
    concurrent_download_limit: int = 5

    # Deprecated. These have also been renamed to avoid using them elsewhere in the app.
    _sol: bool = field(default=True, metadata=config(field_name="serve_over_lan"))
    _pn: int = field(default=8282, metadata=config(field_name="port_number"))
    _rg: int = field(default=0, metadata=config(field_name="replay_gain"))

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
        return config

    def __post_init__(self):
        # Default the cache_location to ~/.local/share/sublime-music
        if not self.cache_location:
            path = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share")
            path = path.expanduser().joinpath("sublime-music").resolve()
            self.cache_location = path

        self._state = None
        self._loaded_provider_id = None
        self.migrate()

    def migrate(self):
        for _, provider in self.providers.items():
            provider.migrate()

        if self.version < 6:
            self.player_config = {
                "Local Playback": {"Replay Gain": ["no", "track", "album"][self._rg]},
                "Chromecast": {
                    "Serve Local Files to Chromecasts on the LAN": self._sol,
                    "LAN Server Port Number": self._pn,
                },
            }

        self.version = 6
        self.state.migrate()

    @property
    def provider(self) -> Optional[ProviderConfiguration]:
        return self.providers.get(self.current_provider_id or "")

    @property
    def state(self) -> UIState:
        if not (provider := self.provider):
            return UIState()

        # If the provider has changed, then retrieve the new provider's state.
        if self._loaded_provider_id != provider.id:
            self.load_state()

        return self._state

    def load_state(self):
        self._state = UIState()
        if not (provider := self.provider):
            return

        self._loaded_provider_id = provider.id
        if (state_filename := self._state_file_location) and state_filename.exists():
            try:
                with open(state_filename, "rb") as f:
                    self._state = pickle.load(f)
            except Exception:
                logging.exception(f"Couldn't load state from {state_filename}")
                # Just ignore any errors, it is only UI state.
                self._state = UIState()

        self._state.__init_available_players__()

    @property
    def _state_file_location(self) -> Optional[Path]:
        if not (provider := self.provider):
            return None

        assert self.cache_location
        return self.cache_location.joinpath(provider.id, "state.pickle")

    def save(self):
        # Save the config as YAML.
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        json = self.to_json(indent=2, sort_keys=True)
        with open(self.filename, "w+") as f:
            f.write(json)

        # Save the state for the current provider.
        if state_filename := self._state_file_location:
            state_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(state_filename, "wb+") as f:
                pickle.dump(self.state, f)
