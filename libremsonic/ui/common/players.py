import threading
from urllib.parse import urlparse, quote
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Callable, List, Any
from time import sleep
from concurrent.futures import ThreadPoolExecutor, Future

import pychromecast
import mpv

from libremsonic.config import AppConfiguration
from libremsonic.cache_manager import CacheManager
from libremsonic.server.api_objects import Child


class PlayerEvent:
    name: str
    value: Any

    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value


class Player:
    def __init__(
            self,
            on_timepos_change: Callable[[float], None],
            on_track_end: Callable[[], None],
            on_player_event: Callable[[PlayerEvent], None],
            config: AppConfiguration,
    ):
        self.on_timepos_change = on_timepos_change
        self.on_track_end = on_track_end
        self.on_player_event = on_player_event
        self.config = config
        self._song_loaded = False

    @property
    def playing(self):
        return self._is_playing()

    @property
    def song_loaded(self):
        return self._song_loaded

    @property
    def volume(self):
        return self._get_volume()

    @volume.setter
    def volume(self, value):
        return self._set_volume(value)

    def reset(self):
        raise NotImplementedError(
            'reset must be implemented by implementor of Player')

    def play_media(self, file_or_url, progress, song):
        raise NotImplementedError(
            'play_media must be implemented by implementor of Player')

    def _is_playing(self):
        raise NotImplementedError(
            '_is_playing must be implemented by implementor of Player')

    def pause(self):
        raise NotImplementedError(
            'pause must be implemented by implementor of Player')

    def toggle_play(self):
        raise NotImplementedError(
            'toggle_play must be implemented by implementor of Player')

    def seek(self, value):
        raise NotImplementedError(
            'seek must be implemented by implementor of Player')

    def _get_timepos(self):
        raise NotImplementedError(
            'get_timepos must be implemented by implementor of Player')

    def _get_volume(self):
        raise NotImplementedError(
            '_get_volume must be implemented by implementor of Player')

    def _set_volume(self):
        raise NotImplementedError(
            '_set_volume must be implemented by implementor of Player')

    def shutdown(self):
        raise NotImplementedError(
            'shutdown must be implemented by implementor of Player')


class MPVPlayer(Player):
    def __init__(self, *args):
        super().__init__(*args)

        self.mpv = mpv.MPV()
        self.progress_value_lock = threading.Lock()
        self.progress_value_count = 0

        @self.mpv.property_observer('time-pos')
        def time_observer(_name, value):
            self.on_timepos_change(value)
            if value is None and self.progress_value_count > 1:
                self.on_track_end()
                with self.progress_value_lock:
                    self.progress_value_count = 0

            if value:
                with self.progress_value_lock:
                    self.progress_value_count += 1

    def _is_playing(self):
        return not self.mpv.pause

    def reset(self):
        self._song_loaded = False
        with self.progress_value_lock:
            self.progress_value_count = 0

    def play_media(self, file_or_url, progress, song):
        self.had_progress_value = False
        with self.progress_value_lock:
            self.progress_value_count = 0

        self.mpv.pause = False
        self.mpv.command(
            'loadfile',
            file_or_url,
            'replace',
            f'start={progress}' if progress else '',
        )
        self._song_loaded = True

    def pause(self):
        self.mpv.pause = True

    def toggle_play(self):
        self.mpv.cycle('pause')

    def seek(self, value):
        self.mpv.seek(str(value), 'absolute')

    def _set_volume(self, value):
        self.mpv.volume = value

    def _get_volume(self):
        return self.mpv.volume

    def shutdown(self):
        pass


class ChromecastPlayer(Player):
    chromecasts: List[Any] = []
    chromecast = None
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)

    class CastStatusListener:
        on_new_cast_status = None

        def new_cast_status(self, status):
            if self.on_new_cast_status:
                self.on_new_cast_status(status)

    class MediaStatusListener:
        on_new_media_status = None

        def new_media_status(self, status):
            if self.on_new_media_status:
                self.on_new_media_status(status)

    cast_status_listener = CastStatusListener()
    media_status_listener = MediaStatusListener()

    class ServerThread(threading.Thread):
        def __init__(self, host, port, directory):
            super().__init__()
            self.host = host
            self.port = port
            self.directory = directory

        def generate_handler(self, directory):
            class ServerHandler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=directory, **kwargs)

            return ServerHandler

        def run(self):
            self.server = HTTPServer(
                (self.host, self.port),
                self.generate_handler(self.directory),
            )
            # TODO figure out how to make this stop when the app closes.
            self.server.serve_forever()

    @classmethod
    def get_chromecasts(self) -> Future:
        def do_get_chromecasts():
            self.chromecasts = pychromecast.get_chromecasts()
            return self.chromecasts

        return ChromecastPlayer.executor.submit(do_get_chromecasts)

    @classmethod
    def set_playing_chromecast(self, chromecast):
        self.chromecast = chromecast
        self.chromecast.media_controller.register_status_listener(
            ChromecastPlayer.media_status_listener)
        self.chromecast.register_status_listener(
            ChromecastPlayer.cast_status_listener)
        self.chromecast.wait()
        print(f'Using: {chromecast.device.friendly_name}')

    def __init__(self, *args):
        super().__init__(*args)
        self._timepos = None
        self.time_incrementor_running = False
        ChromecastPlayer.cast_status_listener.on_new_cast_status = self.on_new_cast_status
        ChromecastPlayer.media_status_listener.on_new_media_status = self.on_new_media_status

        # Set host_ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        self.host_ip = s.getsockname()[0]
        s.close()

        # TODO make the port come from the app config
        self.server_thread = ChromecastPlayer.ServerThread(
            '0.0.0.0',
            8080,
            self.config.cache_location,
        )
        self.server_thread.daemon = True
        self.server_thread.start()

    def on_new_cast_status(self, status):
        print('new cast status')
        print(status)
        self.on_player_event(
            PlayerEvent(
                'volume_change',
                status.volume_level * 100 if not status.volume_muted else 0,
            ))

    def on_new_media_status(self, status):
        # Detect the end of a track and go to the next one.
        if (status.idle_reason == 'FINISHED' and status.player_state == 'IDLE'
                and self._timepos > 0):
            self.on_track_end()
        self._timepos = status.current_time

        print('new status')
        print(status)

        self.on_player_event(
            PlayerEvent(
                'play_state_change',
                status.player_state in ('PLAYING', 'BUFFERING'),
            ))

        # Start the time incrementor just in case this was a play notification.
        self.start_time_incrementor()

    def time_incrementor(self):
        if self.time_incrementor_running:
            return

        self.time_incrementor_running = True
        while True:
            if not self.playing:
                self.time_incrementor_running = False
                raise Exception()

            self._timepos += 0.5
            self.on_timepos_change(self._timepos)
            sleep(0.5)

    def start_time_incrementor(self):
        ChromecastPlayer.executor.submit(self.time_incrementor)

    def wait_for_playing(self, callback, url=None):
        def do_wait_for_playing():
            while (not self.playing
                   or (url is not None and url !=
                       self.chromecast.media_controller.status.content_id)):
                sleep(0.1)

            callback()

        ChromecastPlayer.executor.submit(do_wait_for_playing)

    def _is_playing(self):
        return self.chromecast.media_controller.status.player_is_playing

    def reset(self):
        self._song_loaded = False

    def play_media(self, file_or_url: str, progress: float, song: Child):
        stream_scheme = urlparse(file_or_url).scheme
        if not stream_scheme:
            # TODO make this come from the app config
            strlen = len('/home/sumner/.local/share/libremsonic/')
            file_or_url = file_or_url[strlen:]
            file_or_url = f'http://{self.host_ip}:8080/{quote(file_or_url)}'

        cover_art_url = CacheManager.get_cover_art_url(song.id, 1000)
        self.chromecast.media_controller.play_media(
            file_or_url,
            'audio/mp3',
            current_time=progress,
            title=song.title,
            thumb=cover_art_url,
            metadata=dict(
                metadataType=3,
                albumName=song.album,
                artist=song.artist,
                trackNumber=song.track,
            ),
        )
        self._timepos = progress

        def on_play_begin():
            self._song_loaded = True
            self.start_time_incrementor()

        self.wait_for_playing(on_play_begin, url=file_or_url)

    def pause(self):
        self.chromecast.media_controller.pause()

    def toggle_play(self):
        if self.playing:
            self.chromecast.media_controller.pause()
        else:
            self.chromecast.media_controller.play()
            self.wait_for_playing(self.start_time_incrementor)

    def seek(self, value):
        do_pause = not self.playing
        self.chromecast.media_controller.seek(value)
        if do_pause:
            self.pause()

    def _set_volume(self, value):
        # Chromecast volume is in the range [0, 1], not [0, 100].
        if self.chromecast:
            if value == 0:
                self.chromecast.set_volume_muted(True)
            else:
                self.chromecast.set_volume_muted(False)
                self.chromecast.set_volume(value / 100)

    def _get_volume(self, value):
        if self.chromecast:
            if self.chromecast.status.volume_muted:
                return 0
            return self.chromecast.status.volume_level * 100
        else:
            return 100

    def shutdown(self):
        self.chromecast.disconnect(blocking=True)
