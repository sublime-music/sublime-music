import base64
import io
import mimetypes
import multiprocessing
import os
import socket
from datetime import timedelta
from typing import (
    Any,
    Callable,
    Union,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)
from urllib.parse import urlparse

from sublime.adapters import AdapterManager
from sublime.adapters.api_objects import Song

from .base import Player, PlayerEvent

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

    def supported_schemes(self) -> Set[str]:
        schemes = {"http", "https"}
        if bottle_imported and self.config.get(SERVE_FILES_KEY):
            schemes.add("file")
        return schemes

    def __init__(
        self,
        on_timepos_change: Callable[[Optional[float]], None],
        on_track_end: Callable[[], None],
        on_player_event: Callable[[PlayerEvent], None],
        config: Dict[str, Union[str, int, bool]],
    ):
        self.server_process = None
        self.config = config
        if bottle_imported and self.config.get(SERVE_FILES_KEY):
            self.server_process = multiprocessing.Process(
                target=self._run_server_process,
                args=("0.0.0.0", self.config.get(LAN_PORT_KEY)),
            )

        if chromecast_imported:
            self._chromecasts: List[Any] = []
            self._current_chromecast = pychromecast.Chromecast

    def shutdown(self):
        if self._current_chromecast:
            self._current_chromecast.disconnect()
        if self.server_process:
            self.server_process.terminate()

    _serving_song_id = multiprocessing.Array("c", 1024)  # huge buffer, just in case
    _serving_token = multiprocessing.Array("c", 12)

    def _run_server_process(self, host: str, port: int):
        app = bottle.Bottle()

        @app.route("/")
        def index() -> str:
            return """
            <h1>Sublime Music Local Music Server</h1>
            <p>
                Sublime Music uses this port as a server for serving music Chromecasts
                on the same LAN.
            </p>
            """

        @app.route("/s/<token>")
        def stream_song(token: str) -> bytes:
            if token != self._serving_token.value:
                raise bottle.HTTPError(status=401, body="Invalid token.")

            song = AdapterManager.get_song_details(self._serving_song_id.value).result()
            filename = AdapterManager.get_song_filename_or_stream(song)
            with open(filename, "rb") as fin:
                song_buffer = io.BytesIO(fin.read())

            content_type = mimetypes.guess_type(filename)[0]
            bottle.response.set_header("Content-Type", content_type)
            bottle.response.set_header("Accept-Ranges", "bytes")
            return song_buffer.read()

        bottle.run(app, host=host, port=port)

    def get_available_player_devices(self) -> Iterator[Tuple[str, str]]:
        if not chromecast_imported:
            return

        self._chromecasts = pychromecast.get_chromecasts()
        for chromecast in self._chromecasts:
            yield (str(chromecast.device.uuid), chromecast.device.friendly_name)

    @property
    def playing(self) -> bool:
        if (
            not self._current_chromecast
            or not self._current_chromecast.media_controller
        ):
            return False
        return self._current_chromecast.media_controller.player_is_playing

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
        return self._current_chromecast.volume_muted

    def set_muted(self, muted: bool):
        self._current_chromecast.set_volume_muted(muted)

    def play_media(self, uri: str, progress: timedelta, song: Song):
        scheme = urlparse(uri).scheme
        if scheme == "file":
            token = base64.b64encode(os.urandom(8)).decode("ascii")
            for r in (("+", "."), ("/", "-"), ("=", "_")):
                token = token.replace(*r)
            self._serving_token.value = token
            self._serving_song_id.value = song.id

            # If this fails, then we are basically screwed, so don't care if it blows
            # up.
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
            s.close()

            uri = f"http://{host_ip}:{self.config.get(LAN_PORT_KEY)}/s/{token}"

        cover_art_url = AdapterManager.get_cover_art_uri(song.cover_art, size=1000)
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

    def pause(self):
        if self._current_chromecast and self._current_chromecast.media_controller:
            self._current_chromecast.media_controller.pause()

    def toggle_play(self):
        if self.playing:
            self._current_chromecast.media_controller.pause()
        else:
            self._current_chromecast.media_controller.play()
            # self._wait_for_playing(self._start_time_incrementor)

    def seek(self, position: timedelta):
        do_pause = not self.playing
        self._current_chromecast.media_controller.seek(position.total_seconds())
        if do_pause:
            self.pause()

    def _wait_for_playing(self):
        pass
