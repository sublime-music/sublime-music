from sublime.players.chromecast import ChromecastPlayer


def test_init():
    empty_fn = lambda *a, **k: None
    ChromecastPlayer(
        empty_fn,
        empty_fn,
        empty_fn,
        {
            "Serve Local Files to Chromecasts on the LAN": True,
            "LAN Server Port Number": 6969,
        },
    )
