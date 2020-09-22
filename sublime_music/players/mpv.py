import threading
from datetime import timedelta
from typing import Callable, cast, Dict, Optional, Tuple, Type, Union

import mpv

from .base import Player, PlayerDeviceEvent, PlayerEvent
from ..adapters.api_objects import Song

REPLAY_GAIN_KEY = "Replay Gain"


class MPVPlayer(Player):
    enabled = True
    name = "Local Playback"
    can_start_playing_with_no_latency = True
    supported_schemes = {"http", "https", "file"}
    song_loaded = False

    _progress_value_lock = threading.Lock()
    _progress_value_count = 0

    _volume = 100.0
    _muted = False

    _is_mock = False

    @staticmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        return {REPLAY_GAIN_KEY: ("Disabled", "Track", "Album")}

    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        player_device_change_callback: Callable[[PlayerDeviceEvent], None],
        config: Dict[str, Union[str, int, bool]],
    ):
        self.mpv = mpv.MPV()
        if MPVPlayer._is_mock:
            self.mpv.audio_device = "null"
        self.mpv.audio_client_name = "sublime-music"
        self.change_settings(config)

        @self.mpv.property_observer("time-pos")
        def time_observer(_, value: Optional[float]):
            on_timepos_change(value)
            if value is None and self._progress_value_count > 1:
                on_track_end()
                with self._progress_value_lock:
                    self._progress_value_count = 0

            if value:
                with self._progress_value_lock:
                    self._progress_value_count += 1

        @self.mpv.property_observer("demuxer-cache-time")
        def cache_size_observer(_, value: Optional[float]):
            on_player_event(
                PlayerEvent(
                    PlayerEvent.EventType.STREAM_CACHE_PROGRESS_CHANGE,
                    "this device",
                    stream_cache_duration=value,
                )
            )

        # Indicate to the UI that we exist.
        player_device_change_callback(
            PlayerDeviceEvent(
                PlayerDeviceEvent.Delta.ADD, type(self), "this device", "This Device"
            )
        )

    def change_settings(self, config: Dict[str, Union[str, int, bool]]):
        self.config = config
        self.mpv.replaygain = {
            "Disabled": "no",
            "Track": "track",
            "Album": "album",
        }.get(cast(str, config.get(REPLAY_GAIN_KEY, "Disabled")), "no")

    def refresh_players(self):
        # Don't do anything
        pass

    def set_current_device_id(self, device_id: str):
        # Don't do anything beacuse it should always be the "this device" ID.
        pass

    def shutdown(self):
        pass

    def reset(self):
        self.song_loaded = False
        with self._progress_value_lock:
            self._progress_value_count = 0

    @property
    def playing(self) -> bool:
        return not self.mpv.pause

    def get_volume(self) -> float:
        return self._volume

    def set_volume(self, volume: float):
        if not self._muted:
            self.mpv.volume = volume
        self._volume = volume

    def get_is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool):
        self.mpv.volume = 0 if muted else self._volume
        self._muted = muted

    def play_media(self, uri: str, progress: timedelta, song: Song):
        with self._progress_value_lock:
            self._progress_value_count = 0

        options = {
            "force-seekable": "yes",
            "start": str(progress.total_seconds()),
        }
        self.mpv.command(
            "loadfile", uri, "replace", ",".join(f"{k}={v}" for k, v in options.items())
        )
        self.mpv.pause = False
        self.song_loaded = True

    def pause(self):
        self.mpv.pause = True

    def play(self):
        self.mpv.pause = False

    def seek(self, position: timedelta):
        self.mpv.seek(str(position.total_seconds()), "absolute")
