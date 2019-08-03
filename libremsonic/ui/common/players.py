from typing import Callable, List, Any
from time import sleep
from concurrent.futures import ThreadPoolExecutor, Future

import pychromecast
import mpv


class Player:
    def __init__(
            self,
            on_timepos_change: Callable[[float], None],
            on_track_end: Callable[[], None],
    ):
        self.on_timepos_change = on_timepos_change
        self.on_track_end = on_track_end
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

    def play_media(self, file_or_url=None, progress=None):
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


class MPVPlayer(Player):
    def __init__(self, *args):
        super().__init__(*args)

        self.mpv = mpv.MPV()
        self.had_progress_value = False

        @self.mpv.property_observer('time-pos')
        def time_observer(_name, value):
            self.on_timepos_change(value)
            if value is None and self.had_progress_value:
                self.on_track_end()
                self.had_progress_value = False

            if value:
                self.had_progress_value = True

    def _is_playing(self):
        return not self.mpv.pause

    def play_media(self, file_or_url, progress=None):
        self.had_progress_value = False
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


class ChromecastPlayer(Player):
    chromecasts: List[Any] = []
    chromecast = None
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)

    def __init__(self, *args):
        super().__init__(*args)

        self._timepos = None

    @classmethod
    def get_chromecasts(self) -> Future:
        def do_get_chromecasts():
            self.chromecasts = pychromecast.get_chromecasts()
            return self.chromecasts

        return ChromecastPlayer.executor.submit(do_get_chromecasts)

    @classmethod
    def set_playing_chromecast(self, chromecast):
        self.chromecast = chromecast
        self.chromecast.wait()
        print(f'Using: {chromecast.device.friendly_name}')

    def time_incrementor(self):
        while True:
            if not self.playing:
                raise Exception()

            self._timepos += 0.5
            self.on_timepos_change(self._timepos)
            sleep(0.5)

    def start_time_incrementor(self):
        def wait_for_playing():
            while not self.playing:
                print('waiting for playing')
                sleep(0.1)

            ChromecastPlayer.executor.submit(self.time_incrementor)

        ChromecastPlayer.executor.submit(wait_for_playing)

    def _is_playing(self):
        print('_is_playing',
              self.chromecast.media_controller.status.player_is_playing)
        return self.chromecast.media_controller.status.player_is_playing

    def play_media(self, file_or_url=None, progress=None):
        self.chromecast.media_controller.play_media(file_or_url, 'audio/mp3')
        self.chromecast.media_controller.block_until_active()
        self._timepos = 0
        self.start_time_incrementor()
        self._song_loaded = True
        if progress:
            self.seek(progress)

    def pause(self):
        self.chromecast.media_controller.pause()

    def toggle_play(self):
        if self.playing:
            self.chromecast.media_controller.pause()
        else:
            self.chromecast.media_controller.play()

    def seek(self, value):
        self.chromecast.media_controller.seek(value)
        self._timepos = value

    def _set_volume(self, value):
        # Chromecast volume is in the range [0, 1], not [0, 100].
        if self.chromecast:
            self.chromecast.set_volume(value / 100)

    def _get_volume(self, value):
        if self.chromecast:
            return self.chromecast.status.volume_level * 100
        else:
            return 100
