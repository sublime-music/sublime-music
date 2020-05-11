import shutil
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, cast, Generator, Iterable, Tuple

import pytest

from sublime import util
from sublime.adapters import api_objects as SublimeAPI, CacheMissError
from sublime.adapters.filesystem import FilesystemAdapter
from sublime.adapters.subsonic import api_objects as SubsonicAPI

MOCK_DATA_FILES = Path(__file__).parent.joinpath("mock_data")
MOCK_ALBUM_ART = MOCK_DATA_FILES.joinpath("album-art.png")
MOCK_SONG_FILE = MOCK_DATA_FILES.joinpath("test-song.mp3")

MOCK_SUBSONIC_SONGS = [
    SubsonicAPI.Song(
        "2",
        "Song 2",
        _parent="foo",
        _album="foo",
        album_id="a1",
        _artist="cool",
        artist_id="art1",
        duration=timedelta(seconds=20.8),
        path="foo/song2.mp3",
        cover_art="2",
        _genre="Bar",
    ),
    SubsonicAPI.Song(
        "1",
        "Song 1",
        _parent="foo",
        _album="foo",
        album_id="a1",
        _artist="foo",
        artist_id="art2",
        duration=timedelta(seconds=10.2),
        path="foo/song1.mp3",
        cover_art="1",
        _genre="Foo",
    ),
    SubsonicAPI.Song(
        "1",
        "Song 1",
        _parent="foo",
        _album="foo",
        album_id="a1",
        _artist="foo",
        artist_id="art2",
        duration=timedelta(seconds=10.2),
        path="foo/song1.mp3",
        cover_art="1",
        _genre="Foo",
    ),
]


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
    request_name: str, mode: str = "r",
) -> Generator[Tuple[Path, Any], None, None]:
    """
    Yields all of the files in the mock_data directory that start with ``request_name``.
    """
    for file in MOCK_DATA_FILES.iterdir():
        if file.name.split("-")[0] in request_name:
            with open(file, mode) as f:
                yield file, f.read()


def test_caching_get_playlists(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlists()

    # Ingest an empty list (for example, no playlists added yet to server).
    cache_adapter.ingest_new_data(FilesystemAdapter.CachedDataKey.PLAYLISTS, (), [])

    # After the first cache miss of get_playlists, even if an empty list is
    # returned, the next one should not be a cache miss.
    cache_adapter.get_playlists()

    # Ingest two playlists.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLISTS,
        (),
        [
            SubsonicAPI.Playlist("1", "test1", comment="comment"),
            SubsonicAPI.Playlist("2", "test2"),
        ],
    )

    playlists = cache_adapter.get_playlists()
    assert len(playlists) == 2
    assert (playlists[0].id, playlists[0].name, playlists[0].comment) == (
        "1",
        "test1",
        "comment",
    )
    assert (playlists[1].id, playlists[1].name) == ("2", "test2")

    # Ingest a new playlist list with one of them deleted.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLISTS,
        (),
        [
            SubsonicAPI.Playlist("1", "test1", comment="comment"),
            SubsonicAPI.Playlist("3", "test3"),
        ],
    )

    # Now, Playlist 2 should be gone.
    playlists = cache_adapter.get_playlists()
    assert len(playlists) == 2
    assert (playlists[0].id, playlists[0].name, playlists[0].comment) == (
        "1",
        "test1",
        "comment",
    )
    assert (playlists[1].id, playlists[1].name) == ("3", "test3")


def test_no_caching_get_playlists(adapter: FilesystemAdapter):
    adapter.get_playlists()

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    adapter.get_playlists()
    # TODO: verify playlist


def test_caching_get_playlist_details(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details("1")

    def verify_playlists(
        actual_songs: Iterable[SublimeAPI.Song],
        expected_songs: Iterable[SubsonicAPI.Song],
    ):
        for actual, song in zip(actual_songs, expected_songs):
            for k, v in asdict(song).items():
                ignore = (
                    "_genre",
                    "_album",
                    "_artist",
                    "_parent",
                    "album_id",
                    "artist_id",
                )
                if k in ignore:
                    continue
                print(k)  # noqa: T001

                actual_value = getattr(actual, k, None)
                if k == "album":
                    assert ("a1", "foo") == (actual_value.id, actual_value.name)
                elif k == "genre":
                    assert v["name"] == actual_value.name
                elif k == "parent":
                    assert "foo" == actual_value.id
                elif k == "artist":
                    assert (v["id"], v["name"]) == (actual_value.id, actual_value.name)
                else:
                    assert actual_value == v

    # Simulate the playlist being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "test1", songs=MOCK_SUBSONIC_SONGS[:2]),
    )

    playlist = cache_adapter.get_playlist_details("1")
    assert playlist.id == "1"
    assert playlist.name == "test1"
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=31)
    verify_playlists(playlist.songs, MOCK_SUBSONIC_SONGS[:2])

    # "Force refresh" the playlist and add a new song (duplicate).
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "foo", songs=MOCK_SUBSONIC_SONGS),
    )

    playlist = cache_adapter.get_playlist_details("1")
    assert playlist.id == "1"
    assert playlist.name == "foo"
    assert playlist.song_count == 3
    assert playlist.duration == timedelta(seconds=41.2)
    verify_playlists(playlist.songs, MOCK_SUBSONIC_SONGS)

    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details("2")


def test_no_caching_get_playlist_details(adapter: FilesystemAdapter):
    with pytest.raises(Exception):
        adapter.get_playlist_details("1")

    # TODO: Create a playlist (that should be allowed only if this is acting as
    # a ground truth adapter)
    # cache_adapter.create_playlist()

    # adapter.get_playlist_details('1')
    # TODO: verify playlist details


def test_caching_get_playlist_then_details(cache_adapter: FilesystemAdapter):
    # Ingest a list of playlists (like the sidebar, without songs)
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLISTS,
        (),
        [SubsonicAPI.Playlist("1", "test1"), SubsonicAPI.Playlist("2", "test2")],
    )

    # Trying to get playlist details should generate a cache miss, but should
    # include the data that we know about.
    try:
        cache_adapter.get_playlist_details("1")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data.id == "1"
        assert e.partial_data.name == "test1"

    # Simulate getting playlist details for id=1, then id=2
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "test1"),
    )

    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("2",),
        SubsonicAPI.PlaylistWithSongs("2", "test2", songs=MOCK_SUBSONIC_SONGS),
    )

    # Going back and getting playlist details for the first one should not
    # cache miss.
    playlist = cache_adapter.get_playlist_details("1")
    assert playlist.id == "1"
    assert playlist.name == "test1"


def test_cache_cover_art(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_cover_art_uri("pl_test1", "file")

    # After ingesting the data, reading from the cache should give the exact same file.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("pl_test1",), MOCK_ALBUM_ART,
    )
    with open(cache_adapter.get_cover_art_uri("pl_test1", "file"), "wb+") as cached:
        with open(MOCK_ALBUM_ART, "wb+") as expected:
            assert cached.read() == expected.read()


def test_invalidate_playlist(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLISTS,
        (),
        [SubsonicAPI.Playlist("1", "test1"), SubsonicAPI.Playlist("2", "test2")],
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("pl_test1",), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("2",),
        SubsonicAPI.PlaylistWithSongs("2", "test2", cover_art="pl_2", songs=[]),
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("pl_2",), MOCK_ALBUM_ART,
    )

    stale_uri_1 = cache_adapter.get_cover_art_uri("pl_test1", "file")
    stale_uri_2 = cache_adapter.get_cover_art_uri("pl_2", "file")

    cache_adapter.invalidate_data(FilesystemAdapter.CachedDataKey.PLAYLISTS, ())
    cache_adapter.invalidate_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS, ("2",)
    )
    cache_adapter.invalidate_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("pl_test1",)
    )

    # After invalidating the data, it should cache miss, but still have the old, stale,
    # data.
    try:
        cache_adapter.get_playlists()
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert len(e.partial_data) == 2

    try:
        cache_adapter.get_cover_art_uri("pl_test1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_uri_1

    try:
        cache_adapter.get_playlist_details("2")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data

    # Even though the pl_2 cover art file wasn't explicitly invalidated, it should have
    # been invalidated with the playlist details invalidation.
    try:
        cache_adapter.get_cover_art_uri("pl_2", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_uri_2


def test_invalidate_song_data(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("2",), MOCK_SUBSONIC_SONGS[0]
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("1",), MOCK_SUBSONIC_SONGS[1]
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("1",), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_FILE, ("1",), MOCK_SONG_FILE
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_FILE, ("2",), MOCK_SONG_FILE
    )

    stale_song_file = cache_adapter.get_song_uri("1", "file")
    stale_cover_art_file = cache_adapter.get_cover_art_uri("1", "file")
    cache_adapter.invalidate_data(FilesystemAdapter.CachedDataKey.SONG_FILE, ("1",))

    try:
        cache_adapter.get_song_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_song_file

    try:
        cache_adapter.get_cover_art_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_cover_art_file

    # Make sure it didn't delete the other ones.
    assert cache_adapter.get_song_uri("2", "file").endswith("song2.mp3")


def test_delete_playlists(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "test1", cover_art="pl_1", songs=[]),
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS,
        ("2",),
        SubsonicAPI.PlaylistWithSongs("2", "test1", cover_art="pl_2", songs=[]),
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("pl_1",), MOCK_ALBUM_ART,
    )

    # Deleting a playlist should get rid of it entirely.
    cache_adapter.delete_data(FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS, ("2",))
    try:
        cache_adapter.get_playlist_details("2")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    # Deleting a playlist with associated cover art should get rid the cover art too.
    cache_adapter.delete_data(FilesystemAdapter.CachedDataKey.PLAYLIST_DETAILS, ("1",))
    try:
        cache_adapter.get_cover_art_uri("pl_1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    # Even if the cover art failed to be deleted, it should cache miss.
    shutil.copy(
        MOCK_ALBUM_ART,
        str(cache_adapter.cover_art_dir.joinpath(util.params_hash("pl_1"))),
    )
    with pytest.raises(CacheMissError):
        cache_adapter.get_cover_art_uri("pl_1", "file")


def test_delete_song_data(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("1",), MOCK_SUBSONIC_SONGS[1]
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.COVER_ART_FILE, ("1",), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_FILE, ("1",), MOCK_SONG_FILE
    )

    music_file_path = cache_adapter.get_song_uri("1", "file")
    cover_art_path = cache_adapter.get_cover_art_uri("1", "file")

    cache_adapter.delete_data(FilesystemAdapter.CachedDataKey.SONG_FILE, ("1",))

    assert not Path(music_file_path).exists()
    assert not Path(cover_art_path).exists()

    try:
        cache_adapter.get_song_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    try:
        cache_adapter.get_cover_art_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None


def test_caching_get_genres(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_genres()

    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("2",), MOCK_SUBSONIC_SONGS[0]
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("1",), MOCK_SUBSONIC_SONGS[1]
    )

    # Getting genres now should look at what's on the songs. This sould cache miss, but
    # still give some data.
    try:
        cache_adapter.get_genres()
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert [g.name for g in cast(Iterable, e.partial_data)] == ["Bar", "Foo"]

    # After we actually ingest the actual list, it should be returned instead.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.GENRES,
        (),
        [
            SubsonicAPI.Genre("Bar", 10, 20),
            SubsonicAPI.Genre("Baz", 10, 20),
            SubsonicAPI.Genre("Foo", 10, 20),
        ],
    )
    assert [g.name for g in cache_adapter.get_genres()] == ["Bar", "Baz", "Foo"]


def test_caching_get_song_details(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_song_details("1")

    # Simulate the song details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS, ("1",), MOCK_SUBSONIC_SONGS[1]
    )

    song = cache_adapter.get_song_details("1")
    assert song.id == "1"
    assert song.title == "Song 1"
    assert song.album
    assert (song.album.id, song.album.name) == ("a1", "foo")
    assert song.artist and song.artist.name == "foo"
    assert song.parent.id == "foo"
    assert song.duration == timedelta(seconds=10.2)
    assert song.path == "foo/song1.mp3"
    assert song.genre and song.genre.name == "Foo"

    # "Force refresh" the song details
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS,
        ("1",),
        SubsonicAPI.Song(
            "1",
            "Song 1",
            _parent="bar",
            _album="bar",
            album_id="a2",
            _artist="bar",
            artist_id="art2",
            duration=timedelta(seconds=10.2),
            path="bar/song1.mp3",
            _genre="Bar",
        ),
    )

    song = cache_adapter.get_song_details("1")
    assert song.id == "1"
    assert song.title == "Song 1"
    assert song.album
    assert (song.album.id, song.album.name) == ("a2", "bar")
    assert song.artist and song.artist.name == "bar"
    assert song.parent.id == "bar"
    assert song.duration == timedelta(seconds=10.2)
    assert song.path == "bar/song1.mp3"
    assert song.genre and song.genre.name == "Bar"

    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details("2")


def test_caching_less_info(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS,
        ("1",),
        SubsonicAPI.Song(
            "1",
            "Song 1",
            _parent="bar",
            _album="bar",
            album_id="a2",
            _artist="bar",
            artist_id="art2",
            duration=timedelta(seconds=10.2),
            path="bar/song1.mp3",
            _genre="Bar",
        ),
    )
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.SONG_DETAILS,
        ("1",),
        SubsonicAPI.Song(
            "1",
            "Song 1",
            _parent="bar",
            duration=timedelta(seconds=10.2),
            path="bar/song1.mp3",
        ),
    )

    song = cache_adapter.get_song_details("1")
    assert song.album and song.album.name == "bar"
    assert song.artist and song.artist.name == "bar"
    assert song.genre and song.genre.name == "Bar"


def test_caching_get_artists(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_artists()

    # Ingest artists.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.ARTISTS,
        (),
        [
            SubsonicAPI.Artist("1", "test1", album_count=3),
            SubsonicAPI.Artist("2", "test2", album_count=4),
        ],
    )

    artists = cache_adapter.get_artists()
    assert len(artists) == 2
    assert (artists[0].id, artists[0].name, artists[0].album_count) == ("1", "test1", 3)
    assert (artists[1].id, artists[1].name, artists[1].album_count) == ("2", "test2", 4)

    # Ingest a new artists list with one of them deleted.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.ARTISTS,
        (),
        [
            SubsonicAPI.Artist("1", "test1", album_count=3),
            SubsonicAPI.Artist("3", "test3", album_count=8),
        ],
    )

    # Now, artist 2 should be gone.
    artists = cache_adapter.get_artists()
    assert len(artists) == 2
    assert (artists[0].id, artists[0].name, artists[0].album_count) == ("1", "test1", 3)
    assert (artists[1].id, artists[1].name, artists[1].album_count) == ("3", "test3", 8)


def test_caching_get_ignored_articles(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_ignored_articles()

    # Ingest ignored_articles.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.IGNORED_ARTICLES, (), {"Foo", "Bar"}
    )
    artists = cache_adapter.get_ignored_articles()
    assert {"Foo", "Bar"} == artists

    # Ingest a new artists list with one of them deleted.
    cache_adapter.ingest_new_data(
        FilesystemAdapter.CachedDataKey.IGNORED_ARTICLES, (), {"Foo", "Baz"}
    )
    artists = cache_adapter.get_ignored_articles()
    assert {"Foo", "Baz"} == artists
