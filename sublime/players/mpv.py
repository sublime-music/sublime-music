import threading
from datetime import timedelta
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

from sublime.adapters.api_objects import Song

from .base import Player, PlayerEvent

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

    @staticmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        return {REPLAY_GAIN_KEY: ("Disabled", "Track", "Album")}

    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        config: Dict[str, Union[str, int, bool]],
    ):
        self.mpv = mpv.MPV()
        self.mpv.audio_client_name = "sublime-music"
        self.mpv.replaygain = {
            "Disabled": "no",
            "Track": "track",
            "Album": "album",
        }.get(cast(str, config.get(REPLAY_GAIN_KEY, "Disabled")), "no")

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
                    stream_cache_duration=value,
                )
            )

    def shutdown(self):
        pass

    def reset(self):
        self.song_loaded = False
        with self._progress_value_lock:
            self._progress_value_count = 0

    def get_available_player_devices(self) -> Iterator[Tuple[str, str]]:
        yield ("this device", "This Device")

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

    def toggle_play(self):
        self.mpv.cycle("pause")

    def seek(self, position: timedelta):
        print(position)
        print(self.mpv.time_pos)
        self.mpv.seek(str(position.total_seconds()), "absolute")
