from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Generator, Tuple

import pytest

from sublime.adapters import CacheMissError
from sublime.adapters.filesystem import FilesystemAdapter
from sublime.adapters.subsonic import api_objects as SubsonicAPI

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


def test_caching_get_playlists(cache_adapter: FilesystemAdapter):
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


def test_no_caching_get_playlists(adapter: FilesystemAdapter):
    adapter.get_playlists()

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    adapter.get_playlists()
    # TODO: verify playlist


def test_caching_get_playlist_details(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details('1')

    # Simulate the playlist being retrieved from Subsonic.
    songs = [
        SubsonicAPI.Song(
            '2',
            'Song 2',
            parent='foo',
            album='foo',
            artist='foo',
            duration=timedelta(seconds=20.8),
            path='/foo/song2.mp3',
        ),
        SubsonicAPI.Song(
            '1',
            'Song 1',
            parent='foo',
            album='foo',
            artist='foo',
            duration=timedelta(seconds=10.2),
            path='/foo/song1.mp3',
        ),
    ]
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('1', ),
        SubsonicAPI.PlaylistWithSongs('1', 'test1', songs=songs),
    )

    playlist = cache_adapter.get_playlist_details('1')
    assert playlist.id == '1'
    assert playlist.name == 'test1'
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=31)
    for actual, song in zip(playlist.songs, songs):
        for k, v in asdict(song).items():
            assert getattr(actual, k, None) == v

    # "Force refresh" the playlist
    songs = [
        SubsonicAPI.Song(
            '3',
            'Song 3',
            parent='foo',
            album='foo',
            artist='foo',
            duration=timedelta(seconds=10.2),
            path='/foo/song3.mp3',
        ),
        SubsonicAPI.Song(
            '1',
            'Song 1',
            parent='foo',
            album='foo',
            artist='foo',
            duration=timedelta(seconds=21.8),
            path='/foo/song1.mp3',
        ),
    ]
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('1', ),
        SubsonicAPI.PlaylistWithSongs('1', 'foo', songs=songs),
    )

    playlist = cache_adapter.get_playlist_details('1')
    assert playlist.id == '1'
    assert playlist.name == 'foo'
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=32)
    for actual, song in zip(playlist.songs, songs):
        for k, v in asdict(song).items():
            assert getattr(actual, k, None) == v

    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details('2')


def test_no_caching_get_playlist_details(adapter: FilesystemAdapter):
    with pytest.raises(Exception):
        adapter.get_playlist_details('1')

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    # adapter.get_playlist_details('1')
    # TODO: verify playlist details


def test_caching_get_playlist_then_details(cache_adapter: FilesystemAdapter):
    # Ingest a list of playlists (like the sidebar, without songs)
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLISTS,
        (),
        [
            SubsonicAPI.Playlist('1', 'test1'),
            SubsonicAPI.Playlist('2', 'test2'),
        ],
    )

    # Trying to get playlist details should generate a cache miss, but should
    # include the data that we know about.
    try:
        cache_adapter.get_playlist_details('1')
        assert False, 'DID NOT raise CacheMissError'
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data.id == '1'
        assert e.partial_data.name == 'test1'

    # Simulate getting playlist details for id=1, then id=2
    songs = [
        SubsonicAPI.Song(
            '3',
            'Song 3',
            parent='foo',
            album='foo',
            artist='foo',
            duration=timedelta(seconds=10.2),
            path='/foo/song3.mp3',
        ),
    ]
    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('1', ),
        SubsonicAPI.PlaylistWithSongs('1', 'test1', songs=songs),
    )

    cache_adapter.ingest_new_data(
        FilesystemAdapter.FunctionNames.GET_PLAYLIST_DETAILS,
        ('2', ),
        SubsonicAPI.PlaylistWithSongs('2', 'test2', songs=songs),
    )

    # Going back and getting playlist details for the first one should not
    # cache miss.
    playlist = cache_adapter.get_playlist_details('1')
    assert playlist.id == '1'
    assert playlist.name == 'test1'
