import abc
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Callable, Dict, Optional, Set, Tuple, Type, Union

from ..adapters.api_objects import Song


@dataclass
class PlayerEvent:
    """
    Represents an event triggered by the player. This is a way to signal state changes
    to Sublime Music if the player can be controlled outside of Sublime Music (for
    example, Chromecast player).

    Each player event has a :class:`PlayerEvent.EventType`. Additionally, each event
    type has additional information in the form of additional properties on the
    :class:`PlayerEvent` object.

    * :class:`PlayerEvent.EventType.PLAY_STATE_CHANGE` -- indicates that the play state
      of the player has changed. The :class:`PlayerEvent.playing` property is required
      for this event type.
    * :class:`PlayerEvent.EventType.VOLUME_CHANGE` -- indicates that the player's volume
      has changed. The :classs`PlayerEvent.volume` property is required for this event
      type and should be in the range [0, 100].
    * :class:`PlayerEvent.EventType.STREAM_CACHE_PROGRESS_CHANGE` -- indicates that the
      stream cache progress has changed. When streaming a song, this will be used to
      show how much of the song has been loaded into the player. The
      :class:`PlayerEvent.stream_cache_duration` property is required for this event
      type and should be a float represent the number of seconds of the song that have
      been cached.
    * :class:`PlayerEvent.EventType.CONNECTING` -- indicates that a device is being
      connected to. The :class:`PlayerEvent.device_id` property is required for this
      event type and indicates the device ID that is being connected to.
    * :class:`PlayerEvent.EventType.CONNECTED` -- indicates that a device has been
      connected to. The :class:`PlayerEvent.device_id` property is required for this
      event type and indicates the device ID that has been connected to.
    """

    class EventType(Enum):
        PLAY_STATE_CHANGE = 0
        VOLUME_CHANGE = 1
        STREAM_CACHE_PROGRESS_CHANGE = 2
        CONNECTING = 3
        CONNECTED = 4
        DISCONNECT = 5

    type: EventType
    device_id: str
    playing: Optional[bool] = None
    volume: Optional[float] = None
    stream_cache_duration: Optional[float] = None


@dataclass
class PlayerDeviceEvent:
    class Delta(Enum):
        ADD = 0
        REMOVE = 1

    delta: Delta
    player_type: Type
    id: str
    name: str


class Player(abc.ABC):
    song_loaded = False

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
    @abc.abstractmethod
    def supported_schemes(self) -> Set[str]:
        """
        :returns: a set of all the schemes that the player can play.
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
            options (for a dropdown menu).
        """

    @abc.abstractmethod
    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        player_device_change_callback: Callable[[PlayerDeviceEvent], None],
        config: Dict[str, Union[str, int, bool]],
    ):
        """
        Initialize the player.

        :param config: A dictionary of configuration key -> configuration value.
        """

    @abc.abstractmethod
    def change_settings(self, config: Dict[str, Union[str, int, bool]]):
        """
        This function is called when the player settings are changed (normally this
        happens when the user changes the settings in the UI).

        :param config: A dictionary of configuration key -> configuration value.
        """

    @abc.abstractmethod
    def refresh_players(self):
        """
        This function is called when the user requests the player list to be refreshed
        in the UI.

        This function should call the ``player_device_change_callback`` with the delta
        events to indicate changes to the UI. If there is no reason to refresh (for
        example, the MPV player), then this function can do nothing.
        """

    @abc.abstractmethod
    def set_current_device_id(self, device_id: str):
        """
        Switch to the given device ID.
        """

    def reset(self):
        """
        Reset the player.
        """

    @abc.abstractmethod
    def shutdown(self):
        """
        Do any cleanup of the player.
        """

    @property
    @abc.abstractmethod
    def playing(self) -> bool:
        """
        :returns: whether or not the player is currently playing a song.
        """

    @abc.abstractmethod
    def get_volume(self) -> float:
        """
        :returns: the current volume on a scale of [0, 100]
        """

    @abc.abstractmethod
    def set_volume(self, volume: float):
        """
        Set the volume of the player to the given value.

        :param volume: the value to set the volume to. Will be in the range [0, 100]
        """

    @abc.abstractmethod
    def get_is_muted(self) -> bool:
        """
        :returns: whether or not the player is muted.
        """

    @abc.abstractmethod
    def set_muted(self, muted: bool):
        """
        :param muted: set the player's "muted" property to the given value.
        """

    @abc.abstractmethod
    def play_media(self, uri: str, progress: timedelta, song: Song):
        """
        :param uri: the URI to play. The URI is guaranteed to be one of the schemes in
            the :class:`supported_schemes` set for this adapter.
        :param progress: the time at which to start playing the song.
        :param song: the actual song. This could be used to set metadata and such on the
            player.
        """

    @abc.abstractmethod
    def pause(self):
        """
        Pause the player.
        """

    @abc.abstractmethod
    def play(self):
        """
        Play the current media.
        """

    def seek(self, position: timedelta):
        """
        :param position: seek to the given position in the song.
        """
