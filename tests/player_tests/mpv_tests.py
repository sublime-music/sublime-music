from sublime.players.mpv import MPVPlayer


def test_init():
    empty_fn = lambda *a, **k: None
    MPVPlayer(empty_fn, empty_fn, empty_fn, {"Replay Gain": "no"})
