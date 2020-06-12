import threading
from typing import (
    Callable,
    cast,
    Union,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
)

import mpv

from .base import Player

REPLAY_GAIN_KEY = "Replay Gain"


class MPVPlayer(Player):
    enabled = True
    name = "Local Playback"
    can_start_playing_with_no_latency = True
    supported_schemes = {"http", "https", "file"}

    @staticmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        return {REPLAY_GAIN_KEY: ("Disabled", "Track", "Album")}

    def __init__(self, config: Dict[str, Union[str, int, bool]]):
        self.mpv = mpv.MPV()
        self.mpv.audio_client_name = "sublime-music"
        self.mpv.replaygain = {
            "Disabled": "no",
            "Track": "track",
            "Album": "album",
        }.get(cast(str, config.get(REPLAY_GAIN_KEY, "Disabled")))

        self.progress_value_lock = threading.Lock()
        self.progress_value_count = 0
        self._muted = False
        self._volume = 100.0
        self._can_hotswap_source = True

        @self.mpv.property_observer("time-pos")
        def time_observer(_, value: Optional[float]):
            self.on_timepos_change(value)
            if value is None and self.progress_value_count > 1:
                self.on_track_end()
                with self.progress_value_lock:
                    self.progress_value_count = 0

            if value:
                with self.progress_value_lock:
                    self.progress_value_count += 1

        @self.mpv.property_observer("demuxer-cache-time")
        def cache_size_observer(_, value: Optional[float]):
            on_player_event(
                PlayerEvent(
                    PlayerEvent.Type.STREAM_CACHE_PROGRESS_CHANGE,
                    stream_cache_duration=value,
                )
            )

    def shutdown(self):
        pass

    def get_available_player_devices(self) -> Iterator[Tuple[str, str]]:
        yield ("this device", "This Device")
