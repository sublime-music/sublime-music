import abc
import multiprocessing
from dataclasses import dataclass
from enum import Enum
from functools import partial
from time import sleep
from typing import (
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


@dataclass
class PlayerEvent:
    class EventType(Enum):
        PLAY_STATE_CHANGE = 0
        VOLUME_CHANGE = 1
        STREAM_CACHE_PROGRESS_CHANGE = 2
        CONNECTING = 3
        CONNECTED = 4

    type: EventType
    playing: Optional[bool] = None
    volume: Optional[float] = None
    stream_cache_duration: Optional[float] = None


class Player(abc.ABC):
    @property
    @abc.abstractmethod
    def enabled(self) -> bool:
        return True

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        :returns: returns the friendly name of the player for display in the UI.
        """

    @property
    def can_start_playing_with_no_latency(self) -> bool:
        """
        :returns: whether the player can start playing a song with no latency.
        """
        return False

    @staticmethod
    @abc.abstractmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        """
        :returns: a dictionary of configuration key -> type of the option or tuple of
            options (for a dropdown menu)
        """

    @abc.abstractmethod
    def __init__(self, config: Dict[str, Union[str, int, bool]]):
        """
        :param config: A dictionary of configuration key -> configuration value
        """

    @abc.abstractmethod
    def shutdown(self):
        """
        Do any cleanup of the player.
        """

    @abc.abstractmethod
    def get_available_player_devices(self) -> Iterator[Tuple[str, str]]:
        """
        :returns: an iterator of tuples containing the device ID and device name.
        """

    @property
    @abc.abstractmethod
    def playing(self) -> bool:
        """
        :returns: whether or not the player is currently playing a song.
        """

    @property
    @abc.abstractmethod
    def song_loaded(self) -> bool:
        """
        :returns: whether or not the player currently has a song loaded.
        """

    @property
    @abc.abstractmethod
    def volume(self) -> float:
        """
        :returns: the current volume on a scale of [0, 100]
        """

    @volume.setter
    @abc.abstractmethod
    def volume(self, value: float):
        """

        """

    @property
    def is_muted(self) -> bool:
        return self._get_is_muted()

    @is_muted.setter
    def is_muted(self, value: bool):
        self._set_is_muted(value)

    def reset(self):
        raise NotImplementedError("reset must be implemented by implementor of Player")

    def play_media(self, file_or_url: str, progress: timedelta, song: Song):
        raise NotImplementedError(
            "play_media must be implemented by implementor of Player"
        )

    def _is_playing(self):
        raise NotImplementedError(
            "_is_playing must be implemented by implementor of Player"
        )

    def pause(self):
        raise NotImplementedError("pause must be implemented by implementor of Player")

    def toggle_play(self):
        raise NotImplementedError(
            "toggle_play must be implemented by implementor of Player"
        )

    def seek(self, value: timedelta):
        raise NotImplementedError("seek must be implemented by implementor of Player")

    def _get_timepos(self):
        raise NotImplementedError(
            "get_timepos must be implemented by implementor of Player"
        )

    def _get_volume(self):
        raise NotImplementedError(
            "_get_volume must be implemented by implementor of Player"
        )

    def _set_volume(self, value: float):
        raise NotImplementedError(
            "_set_volume must be implemented by implementor of Player"
        )

    def _get_is_muted(self):
        raise NotImplementedError(
            "_get_is_muted must be implemented by implementor of Player"
        )

    def _set_is_muted(self, value: bool):
        raise NotImplementedError(
            "_set_is_muted must be implemented by implementor of Player"
        )

    def shutdown(self):
        raise NotImplementedError(
            "shutdown must be implemented by implementor of Player"
        )
