import pytest

from datetime import datetime, timedelta

from sublime.adapters.api_objects import (Playlist, PlaylistDetails)


def test_playlist_inheritance():
    Playlist('foo', 'Bar')

    PlaylistDetails('foo', 'bar', 3, timedelta(seconds=720))
