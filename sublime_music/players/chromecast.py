import base64
import io
import logging
import mimetypes
import multiprocessing
import os
import socket
from datetime import timedelta
from typing import Any, Callable, cast, Dict, Optional, Set, Tuple, Type, Union
from urllib.parse import urlparse
from uuid import UUID

from gi.repository import GLib

from .base import Player, PlayerDeviceEvent, PlayerEvent
from ..adapters import AdapterManager
from ..adapters.api_objects import Song

try:
    import pychromecast

    chromecast_imported = True
except Exception:
    chromecast_imported = False

try:
    import bottle

    bottle_imported = True
except Exception:
    bottle_imported = False

SERVE_FILES_KEY = "Serve Local Files to Chromecasts on the LAN"
LAN_PORT_KEY = "LAN Server Port Number"


class ChromecastPlayer(Player):
    name = "Chromecast"
    can_start_playing_with_no_latency = False

    @property
    def enabled(self) -> bool:
        return chromecast_imported

    @staticmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        if not bottle_imported:
            return {}
        return {SERVE_FILES_KEY: bool, LAN_PORT_KEY: int}

    @property
    def supported_schemes(self) -> Set[str]:
        schemes = {"http", "https"}
        if bottle_imported and self.config.get(SERVE_FILES_KEY):
            schemes.add("file")
        return schemes

    _timepos = 0.0

    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        player_device_change_callback: Callable[[PlayerDeviceEvent], None],
        config: Dict[str, Union[str, int, bool]],
    ):
        self.server_process: Optional[multiprocessing.Process] = None
        self.on_timepos_change = on_timepos_change
        self.on_track_end = on_track_end
        self.on_player_event = on_player_event
        self.player_device_change_callback = player_device_change_callback

        self.change_settings(config)

        if chromecast_imported:
            self._chromecasts: Dict[UUID, pychromecast.Chromecast] = {}
            self._current_chromecast: Optional[pychromecast.Chromecast] = None

            self.stop_get_chromecasts = None
            self.refresh_players()

    def chromecast_discovered_callback(self, chromecast: Any):
        chromecast = cast(pychromecast.Chromecast, chromecast)
        self._chromecasts[chromecast.device.uuid] = chromecast
        self.player_device_change_callback(
            PlayerDeviceEvent(
                PlayerDeviceEvent.Delta.ADD,
                type(self),
                str(chromecast.device.uuid),
                chromecast.device.friendly_name,
            )
        )

    def change_settings(self, config: Dict[str, Union[str, int, bool]]):
        if not chromecast_imported:
            return

        self.config = config
        if bottle_imported and self.config.get(SERVE_FILES_KEY):
            # Try and terminate the existing process if it exists.
            if self.server_process is not None:
                try:
                    self.server_process.terminate()
                except Exception:
                    pass

            self.server_process = multiprocessing.Process(
                target=self._run_server_process,
                args=("0.0.0.0", self.config.get(LAN_PORT_KEY)),
            )
            self.server_process.start()

    def refresh_players(self):
        if not chromecast_imported:
            return

        if self.stop_get_chromecasts is not None:
            self.stop_get_chromecasts.cancel()

        for id_, chromecast in self._chromecasts.items():
            self.player_device_change_callback(
                PlayerDeviceEvent(
                    PlayerDeviceEvent.Delta.REMOVE,
                    type(self),
                    str(id_),
                    chromecast.device.friendly_name,
                )
            )

        self._chromecasts = {}

        self.stop_get_chromecasts = pychromecast.get_chromecasts(
            blocking=False, callback=self.chromecast_discovered_callback
        )

    def set_current_device_id(self, device_id: str):
        self._current_chromecast = self._chromecasts[UUID(device_id)]
        self._current_chromecast.media_controller.register_status_listener(self)
        self._current_chromecast.register_status_listener(self)
        self._current_chromecast.wait()

    def new_cast_status(self, status: Any):
        assert self._current_chromecast
        self.on_player_event(
            PlayerEvent(
                PlayerEvent.EventType.VOLUME_CHANGE,
                str(self._current_chromecast.device.uuid),
                volume=(status.volume_level * 100 if not status.volume_muted else 0),
            )
        )

        # This happens when the Chromecast is first activated or after "Stop Casting" is
        # pressed in the Google Home app. Reset `song_loaded` so that it calls
        # `play_media` the next time around rather than trying to toggle the play state.
        if status.session_id is None:
            self.song_loaded = False

    time_increment_order_token = 0

    def new_media_status(self, status: Any):
        # Detect the end of a track and go to the next one.
        if (
            status.idle_reason == "FINISHED"
            and status.player_state == "IDLE"
            and self._timepos > 0
        ):
            logging.debug("Chromecast track ended")
            self.on_track_end()
            return

        self.song_loaded = True

        self._timepos = status.current_time

        assert self._current_chromecast
        self.on_player_event(
            PlayerEvent(
                PlayerEvent.EventType.PLAY_STATE_CHANGE,
                str(self._current_chromecast.device.uuid),
                playing=(status.player_state in ("PLAYING", "BUFFERING")),
            )
        )

        def increment_time(order_token: int):
            if self.time_increment_order_token != order_token or not self.playing:
                return

            self._timepos += 0.5
            self.on_timepos_change(self._timepos)
            GLib.timeout_add(500, increment_time, order_token)

        self.time_increment_order_token += 1
        GLib.timeout_add(500, increment_time, self.time_increment_order_token)

    def shutdown(self):
        if self.server_process:
            self.server_process.terminate()

        try:
            self._current_chromecast.quit_app()
        except Exception:
            pass

    _serving_song_id = multiprocessing.Array("c", 1024)  # huge buffer, just in case
    _serving_token = multiprocessing.Array("c", 16)

    def _run_server_process(self, host: str, port: int):
        app = bottle.Bottle()

        @app.route("/")
        def index() -> str:
            return """
            <h1>Sublime Music Local Music Server</h1>
            <p>
                Sublime Music uses this port as a server for serving music to
                Chromecasts on the same LAN.
            </p>
            """

        @app.route("/s/<token>")
        def stream_song(token: str) -> bytes:
            if token != self._serving_token.value.decode():
                raise bottle.HTTPError(status=401, body="Invalid token.")

            song = AdapterManager.get_song_details(
                self._serving_song_id.value.decode()
            ).result()
            filename = AdapterManager.get_song_file_uri(song)
            with open(filename[7:], "rb") as fin:
                song_buffer = io.BytesIO(fin.read())

            content_type = mimetypes.guess_type(filename)[0]
            bottle.response.set_header("Content-Type", content_type)
            bottle.response.set_header("Accept-Ranges", "bytes")
            return song_buffer.read()

        bottle.run(app, host=host, port=port)

    @property
    def playing(self) -> bool:
        if (
            not self._current_chromecast
            or not self._current_chromecast.media_controller
        ):
            return False
        return self._current_chromecast.media_controller.status.player_is_playing

    def get_volume(self) -> float:
        if self._current_chromecast:
            # The volume is in the range [0, 1]. Multiply by 100 to get to [0, 100].
            return self._current_chromecast.status.volume_level * 100
        else:
            return 100

    def set_volume(self, volume: float):
        if self._current_chromecast:
            # volume value is in [0, 100]. Convert to [0, 1] for Chromecast.
            self._current_chromecast.set_volume(volume / 100)

    def get_is_muted(self) -> bool:
        if not self._current_chromecast:
            return False
        return self._current_chromecast.volume_muted

    def set_muted(self, muted: bool):
        if not self._current_chromecast:
            return
        self._current_chromecast.set_volume_muted(muted)

    def play_media(self, uri: str, progress: timedelta, song: Song):
        assert self._current_chromecast
        scheme = urlparse(uri).scheme
        if scheme == "file":
            token = base64.b16encode(os.urandom(8))
            self._serving_token.value = token
            self._serving_song_id.value = song.id.encode()

            # If this fails, then we are basically screwed, so don't care if it blows
            # up.
            # TODO (#129): this does not work properly when on VPNs when the DNS is
            # piped over the VPN tunnel.
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
            s.close()

            uri = f"http://{host_ip}:{self.config.get(LAN_PORT_KEY)}/s/{token.decode()}"
            logging.info("Serving {song.name} at {uri}")

        assert AdapterManager._instance
        networked_scheme_priority = ("https", "http")
        scheme = sorted(
            AdapterManager._instance.ground_truth_adapter.supported_schemes,
            key=lambda s: networked_scheme_priority.index(s),
        )[0]
        cover_art_url = AdapterManager.get_cover_art_uri(
            song.cover_art, scheme, size=1000
        ).result()
        self._current_chromecast.media_controller.play_media(
            uri,
            # Just pretend that whatever we send it is mp3, even if it isn't.
            "audio/mp3",
            current_time=progress.total_seconds(),
            title=song.title,
            thumb=cover_art_url,
            metadata={
                "metadataType": 3,
                "albumName": song.album.name if song.album else None,
                "artist": song.artist.name if song.artist else None,
                "trackNumber": song.track,
            },
        )

        # Make sure to clear out the cache duration state.
        self.on_player_event(
            PlayerEvent(
                PlayerEvent.EventType.STREAM_CACHE_PROGRESS_CHANGE,
                str(self._current_chromecast.device.uuid),
                stream_cache_duration=0,
            )
        )
        self._timepos = progress.total_seconds()

    def pause(self):
        if self._current_chromecast and self._current_chromecast.media_controller:
            self._current_chromecast.media_controller.pause()

    def play(self):
        if self._current_chromecast and self._current_chromecast.media_controller:
            self._current_chromecast.media_controller.play()

    def seek(self, position: timedelta):
        if not self._current_chromecast:
            return

        do_pause = not self.playing
        self._current_chromecast.media_controller.seek(position.total_seconds())
        if do_pause:
            self.pause()

    def _wait_for_playing(self):
        pass
