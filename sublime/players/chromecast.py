import io
import mimetypes
import multiprocessing
from typing import (
    Any,
    Callable,
    Union,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
)

from sublime.adapters import AdapterManager

from .base import Player

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

    @staticmethod
    def get_configuration_options() -> Dict[str, Union[Type, Tuple[str, ...]]]:
        if not bottle_imported:
            return {}
        return {SERVE_FILES_KEY: bool, LAN_PORT_KEY: int}

    def __init__(self, config: Dict[str, Union[str, int, bool]]):
        self.supported_schemes = {"http", "https"}
        self.server_process = None
        if bottle_imported and config.get(SERVE_FILES_KEY):
            self.supported_schemes.add("file")
            self.server_process = multiprocessing.Process(
                target=self._run_server_process,
                args=("0.0.0.0", config.get(LAN_PORT_KEY)),
            )

        self._chromecasts: List[Any] = []

    def shutdown(self):
        if self.server_process:
            self.server_process.terminate()

    _serving_song_id = multiprocessing.Value("s")
    _serving_token = multiprocessing.Value("s")

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
