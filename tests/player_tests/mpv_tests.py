from datetime import timedelta
from pathlib import Path
from time import sleep

from sublime.players.mpv import MPVPlayer


def test_init():
    empty_fn = lambda *a, **k: None
    MPVPlayer(empty_fn, empty_fn, empty_fn, empty_fn, {"Replay Gain": "Disabled"})


def is_close(expected: float, value: float, delta: float = 0.5) -> bool:
    return abs(value - expected) < delta


def test_play():
    empty_fn = lambda *a, **k: None
    mpv_player = MPVPlayer(
        empty_fn, empty_fn, empty_fn, empty_fn, {"Replay Gain": "Disabled"}
    )

    song_path = Path(__file__).parent.joinpath("mock_data/test-song.mp3")
    mpv_player.play_media(str(song_path), timedelta(seconds=10), None)

    # Test Mute and volume
    # ==================================================================================
    # Test normal volume change.
    assert mpv_player.get_volume() == 100
    mpv_player.set_volume(70)
    assert mpv_player.get_volume() == 70

    # Test mute
    assert not mpv_player.get_is_muted()
    mpv_player.set_muted(True)
    assert mpv_player.get_is_muted()

    # Test volume change when muted
    mpv_player.set_volume(50)
    assert mpv_player.get_volume() == 50
    # The volume of the actual player should still be muted.
    assert mpv_player.mpv.volume == 0

    # Unmute and the volume of the actual player should be what we set (50)
    mpv_player.set_muted(False)
    assert mpv_player.mpv.volume == 50

    # Test Play/Pause
    # ==================================================================================
    # Test Pause
    assert mpv_player.playing
    mpv_player.pause()
    assert not mpv_player.playing

    # Test play
    mpv_player.play()
    assert mpv_player.playing

    # Test seek
    sleep(0.1)
    assert is_close(10, mpv_player.mpv.time_pos)
    mpv_player.seek(timedelta(seconds=20))
    assert is_close(20, mpv_player.mpv.time_pos)

    # Pause so that it doesn't keep playing while testing
    mpv_player.pause()
    mpv_player.shutdown()
