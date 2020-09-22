from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: F401

from sublime_music.ui import common


def test_icon_buttons():
    common.IconButton("cloud-offline")
    common.IconToggleButton("cloud-offline")
    common.IconMenuButton("cloud-offline")


def test_load_error():
    test_cases = [
        (
            (True, True),
            "cloud-offline",
            "Song list may be incomplete.\nGo online to load song list.",
        ),
        ((True, False), "network-error", "Error attempting to load song list."),
        ((False, True), "cloud-offline", "Go online to load song list."),
        ((False, False), "network-error", "Error attempting to load song list."),
    ]
    for (has_data, offline_mode), icon_name, label_text in test_cases:

        load_error = common.LoadError(
            "Song list", "load song list", has_data=has_data, offline_mode=offline_mode
        )
        assert load_error.image.get_icon_name().icon_name == f"{icon_name}-symbolic"
        assert load_error.label.get_text() == label_text


def test_song_list_column():
    common.SongListColumn("H", 1, bold=True, align=1.0, width=30)


def test_spinner_image():
    initial_size = 300
    image = common.SpinnerImage(
        loading=False,
        image_name="test",
        spinner_name="ohea",
        image_size=initial_size,
    )
    image.set_from_file(None)
    assert image.image.get_pixbuf() is None

    image.set_from_file("")
    assert image.image.get_pixbuf() is None

    image.set_from_file(
        str(Path(__file__).parent.joinpath("mock_data", "album-art.png"))
    )
    assert (pixbuf := image.image.get_pixbuf()) is not None
    assert pixbuf.get_width() == pixbuf.get_height() == initial_size

    smaller_size = 70
    image.set_image_size(smaller_size)
    assert (pixbuf := image.image.get_pixbuf()) is not None
    assert pixbuf.get_width() == pixbuf.get_height() == smaller_size

    # Just make sure these don't raise exceptions.
    image.set_loading(True)
    image.set_loading(False)
