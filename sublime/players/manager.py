import multiprocessing
from dataclasses import dataclass
from enum import Enum
from functools import partial
from time import sleep
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)


from .base import PlayerEvent
from .chromecast import ChromecastPlayer  # noqa: F401
from .mpv import MPVPlayer  # noqa: F401
from ..config import AppConfiguration


@dataclass
class PlayerDeviceEvent:
    class Delta(Enum):
        ADD = 0
        REMOVE = 1

    delta: Delta
    player_type: Type
    id: str
    name: Optional[str] = None


class PlayerManager:
    # Available Players
    available_player_types: List[Type] = [MPVPlayer, ChromecastPlayer]

    @staticmethod
    def get_configuration_options() -> Dict[
        str, Dict[str, Union[Type, Tuple[str, ...]]]
    ]:
        """
        :returns: Dictionary of the name of the player -> option configs (see
            :class:`sublime.players.base.Player.get_configuration_options` for details).
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
        self.on_timepos_change = on_timepos_change
        self.on_track_end = on_track_end
        self.on_player_event = on_player_event

        self.players = [
            player_type(config.get(player_type.name))
            for player_type in PlayerManager.available_player_types
        ]

        self.device_id_type_map: Dict[str, Type] = {}
        self.player_device_change_callback = player_device_change_callback
        self.player_device_retrieval_process = multiprocessing.Process(
            target=self._retrieve_available_player_devices
        )

    def shutdown(self):
        print("SHUTDOWN PLAYER MANAGER")
        self.player_device_retrieval_process.terminate()

    def _retrieve_available_player_devices(self):
        seen_ids = set()
        while True:
            new_ids = set()
            for t in PlayerManager.available_player_types:
                if not t.enabled:
                    continue
                for device_id, device_name in t.get_available_player_devices():
                    self.player_device_change_callback(
                        PlayerDeviceEvent(
                            PlayerDeviceEvent.Delta.ADD, t, device_id, device_name,
                        )
                    )
                    new_ids.add((t, device_id))
                    self.device_id_type_map[device_id] = t

            for t, device_id in seen_ids.difference(new_ids):
                self.player_device_change_callback(
                    PlayerDeviceEvent(PlayerDeviceEvent.Delta.REMOVE, t, device_id)
                )
                del self.device_id_type_map[device_id]

            seen_ids = new_ids
            sleep(15)

    def can_start_playing_with_no_latency(self, device_id: str) -> bool:
        return self.device_id_type_map[device_id].can_start_playing_with_no_latency

    _current_device_id = None

    @property
    def current_device_id(self) -> Optional[str]:
        return self._current_device_id

    @current_device_id.setter
    def current_device_id(self, value: str):
        print("SET CURRENT DEVICE")
        self._current_device_id = value
