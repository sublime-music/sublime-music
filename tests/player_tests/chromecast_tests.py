from sublime_music.players.chromecast import ChromecastPlayer


def test_init():
    empty_fn = lambda *a, **k: None
    chromecast_player = ChromecastPlayer(
        empty_fn,
        empty_fn,
        empty_fn,
        empty_fn,
        {
            "Serve Local Files to Chromecasts on the LAN": True,
            "LAN Server Port Number": 6969,
        },
    )
    chromecast_player.shutdown()
