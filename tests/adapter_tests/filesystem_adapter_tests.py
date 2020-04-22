import json
from time import sleep
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

import pytest

from sublime.adapters import CacheMissError
from sublime.adapters.subsonic import api_objects as SubsonicAPI
from sublime.adapters.filesystem import (
    models,
    FilesystemAdapter,
)

MOCK_DATA_FILES = Path(__file__).parent.joinpath('mock_data')


@pytest.fixture
def adapter(tmp_path: Path):
    adapter = FilesystemAdapter({}, tmp_path)
    yield adapter
    adapter.shutdown()


@pytest.fixture
def cache_adapter(tmp_path: Path):
    adapter = FilesystemAdapter({}, tmp_path, is_cache=True)
    yield adapter
    adapter.shutdown()


def mock_data_files(
        request_name: str,
        mode: str = 'r',
) -> Generator[Tuple[Path, Any], None, None]:
    """
    Yields all of the files in the mock_data directory that start with
    ``request_name``.
    """
    for file in MOCK_DATA_FILES.iterdir():
        if file.name.split('-')[0] in request_name:
            with open(file, mode) as f:
                yield file, f.read()


def test_caching_get_playlists(
    cache_adapter: FilesystemAdapter,
    tmp_path: Path,
):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlists()

    # Ingest an empty list (for example, no playlists added yet to server).
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLISTS, (), [])

    # After the first cache miss of get_playlists, even if an empty list is
    # returned, the next one should not be a cache miss.
    cache_adapter.get_playlists()

    # Ingest two playlists.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLISTS,
        (),
        [
            SubsonicAPI.Playlist('1', 'test1', comment='comment'),
            SubsonicAPI.Playlist('2', 'test2'),
        ],
    )

    playlists = cache_adapter.get_playlists()
    assert len(playlists) == 2
    assert (playlists[0].id, playlists[0].name,
            playlists[0].comment) == ('1', 'test1', 'comment')
    assert (playlists[1].id, playlists[1].name) == ('2', 'test2')


def test_no_caching_get_playlists(adapter: FilesystemAdapter, tmp_path: Path):
    adapter.get_playlists()

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    adapter.get_playlists()
    # TODO: verify playlist


def test_caching_get_playlist_details(
    cache_adapter: FilesystemAdapter,
    tmp_path: Path,
):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details('1')

    # Create the playlist
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('1', ),
        SubsonicAPI.PlaylistWithSongs(
            '1',
            'test1',
            songs=[
                SubsonicAPI.Child(
                    '1', 'Song 1', duration=timedelta(seconds=10.2)),
                SubsonicAPI.Child(
                    '2', 'Song 2', duration=timedelta(seconds=20.8)),
            ],
        ),
    )

    playlist = cache_adapter.get_playlist_details('1')
    assert playlist.id == '1'
    assert playlist.name == 'test1'
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=31)
    assert (playlist.songs[0].id, playlist.songs[0].title) == ('1', 'Song 1')
    assert (playlist.songs[1].id, playlist.songs[1].title) == ('2', 'Song 2')

    # "Force refresh" the playlist
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('1', ),
        SubsonicAPI.PlaylistWithSongs(
            '1',
            'foo',
            songs=[
                SubsonicAPI.Child(
                    '1', 'Song 1', duration=timedelta(seconds=10.2)),
                SubsonicAPI.Child(
                    '3', 'Song 3', duration=timedelta(seconds=20.8)),
            ],
        ),
    )

    playlist = cache_adapter.get_playlist_details('1')
    assert playlist.id == '1'
    assert playlist.name == 'foo'
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=31)
    assert (playlist.songs[0].id, playlist.songs[0].title) == ('1', 'Song 1')
    assert (playlist.songs[1].id, playlist.songs[1].title) == ('3', 'Song 3')

    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details('2')


def test_no_caching_get_playlist_details(
    adapter: FilesystemAdapter,
    tmp_path: Path,
):
    with pytest.raises(Exception):
        adapter.get_playlist_details('1')

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    # adapter.get_playlist_details('1')
    # TODO: verify playlist details
