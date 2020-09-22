import logging
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

from .base import PlayerDeviceEvent, PlayerEvent
from .chromecast import ChromecastPlayer  # noqa: F401
from .mpv import MPVPlayer  # noqa: F401
from ..adapters.api_objects import Song


class PlayerManager:
    # Available Players. Order matters for UI display.
    available_player_types: List[Type] = [MPVPlayer, ChromecastPlayer]

    @staticmethod
    def get_configuration_options() -> Dict[
        str, Dict[str, Union[Type, Tuple[str, ...]]]
    ]:
        """
        :returns: Dictionary of the name of the player -> option configs (see
            :class:`sublime_music.players.base.Player.get_configuration_options` for
            details).
        """
        return {
            p.name: p.get_configuration_options()
            for p in PlayerManager.available_player_types
        }

    # Initialization and Shutdown
    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        player_device_change_callback: Callable[[PlayerDeviceEvent], None],
        config: Dict[str, Dict[str, Union[Type, Tuple[str, ...]]]],
    ):
        self.current_song: Optional[Song] = None
        self.on_timepos_change = on_timepos_change
        self.on_track_end = on_track_end
        self.config = config
        self.players: Dict[Type, Any] = {}
        self.device_id_type_map: Dict[str, Type] = {}
        self._current_device_id: Optional[str] = None

        def player_event_wrapper(pe: PlayerEvent):
            if pe.device_id == self._current_device_id:
                on_player_event(pe)

        self.on_player_event = player_event_wrapper

        def callback_wrapper(pde: PlayerDeviceEvent):
            self.device_id_type_map[pde.id] = pde.player_type
            player_device_change_callback(pde)

        self.player_device_change_callback = callback_wrapper

        self.players = {
            player_type: player_type(
                self.on_timepos_change,
                self.on_track_end,
                self.on_player_event,
                self.player_device_change_callback,
                self.config.get(player_type.name),
            )
            for player_type in PlayerManager.available_player_types
        }

    def change_settings(
        self,
        config: Dict[str, Dict[str, Union[Type, Tuple[str, ...]]]],
    ):
        self.config = config
        for player_type, player in self.players.items():
            player.change_settings(config.get(player_type.name))

    def refresh_players(self):
        for player in self.players.values():
            player.refresh_players()

    def shutdown(self):
        for p in self.players.values():
            p.shutdown()

    def _get_current_player_type(self) -> Any:
        device_id = self._current_device_id
        if device_id:
            return self.device_id_type_map.get(device_id)

    def _get_current_player(self) -> Any:
        if current_player_type := self._get_current_player_type():
            return self.players.get(current_player_type)

    @property
    def supported_schemes(self) -> Set[str]:
        if cp := self._get_current_player():
            return cp.supported_schemes
        return set()

    @property
    def can_start_playing_with_no_latency(self) -> bool:
        if self._current_device_id:
            return self._get_current_player_type().can_start_playing_with_no_latency
        else:
            return False

    @property
    def current_device_id(self) -> Optional[str]:
        return self._current_device_id

    def set_current_device_id(self, device_id: str):
        logging.info(f"Setting current device id to '{device_id}'")
        if cp := self._get_current_player():
            cp.pause()
            cp.song_loaded = False

        self._current_device_id = device_id

        if cp := self._get_current_player():
            cp.set_current_device_id(device_id)
            cp.song_loaded = False

    def reset(self):
        if current_player := self._get_current_player():
            current_player.reset()

    @property
    def song_loaded(self) -> bool:
        if current_player := self._get_current_player():
            return current_player.song_loaded
        return False

    @property
    def playing(self) -> bool:
        if current_player := self._get_current_player():
            return current_player.playing
        return False

    def get_volume(self) -> float:
        if current_player := self._get_current_player():
            return current_player.get_volume()
        return 100

    def set_volume(self, volume: float):
        if current_player := self._get_current_player():
            current_player.set_volume(volume)

    def get_is_muted(self) -> bool:
        if current_player := self._get_current_player():
            return current_player.get_is_muted()
        return False

    def set_muted(self, muted: bool):
        if current_player := self._get_current_player():
            current_player.set_muted(muted)

    def play_media(self, uri: str, progress: timedelta, song: Song):
        self.current_song = song
        if current_player := self._get_current_player():
            current_player.play_media(uri, progress, song)

    def pause(self):
        if current_player := self._get_current_player():
            current_player.pause()

    def toggle_play(self):
        if current_player := self._get_current_player():
            if self.playing:
                current_player.pause()
            else:
                current_player.play()

    def seek(self, position: timedelta):
        if current_player := self._get_current_player():
            current_player.seek(position)
