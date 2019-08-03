from typing import Callable
from concurrent.futures import ThreadPoolExecutor, Future

import pychromecast
import mpv


class Player:
    def __init__(self, on_timepos_change: Callable[[float], None]):
        self.on_timepos_change = on_timepos_change

    @property
    def time_pos(self):
        return self._get_timepos()

    @property
    def volume(self):
        return self._get_volume()

    @volume.setter
    def volume(self, value):
        return self._set_volume(value)

    def play(self, file_or_url=None, progress=None):
        raise NotImplementedError(
            'play must be implemented by implementor of Player')

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

        @self.mpv.property_observer('time-pos')
        def time_observer(_name, value):
            self.on_timepos_change(value)

    def play(self, file_or_url=None, progress=None):
        self.mpv.pause = False
        if file_or_url:
            self.mpv.command(
                'loadfile',
                file_or_url,
                'replace',
                f'start={progress}',
            )

    def pause(self):
        self.mpv.pause = True

    def toggle_play(self):
        self.mpv.cycle('pause')

    def seek(self, value):
        self.mpv.seek(str(value), 'absolute')

    def _get_timepos(self):
        return self.mpv.time_pos

    def _set_volume(self, value):
        self.mpv.volume = value

    def _get_volume(self):
        return self.mpv.volume


class ChromecastPlayer(Player):
    chromecasts = []
    chromecast = None
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)

    def __init__(self, *args):
        super().__init__(args)

    @classmethod
    def get_chromecasts(self) -> Future:
        def do_get_chromecasts():
            self.chromecasts = pychromecast.get_chromecasts()
            return self.chromecasts

        return ChromecastPlayer.executor.submit(do_get_chromecasts)

    @classmethod
    def set_playing_chromecast(self, chromecast):
        self.chromecast = chromecast

    def play(self, file_or_url=None, progress=None):
        print('play')
        print(file_or_url)
        self.chromecast.media_controller.play_media('')
        if progress:
            print('ohea')

    def pause(self):
        print('pause')

    def toggle_play(self):
        print('toggle')

    def seek(self, value):
        print('seek')

    def _get_timepos(self):
        return 0

    def _set_volume(self, value):
        print('volume', value)

    def _get_volume(self, value):
        return 0
