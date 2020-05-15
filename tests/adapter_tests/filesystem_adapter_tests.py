import json
import shutil
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, cast, Generator, Iterable, Tuple

import pytest

from peewee import SelectQuery

from sublime.adapters import api_objects as SublimeAPI, CacheMissError, SongCacheStatus
from sublime.adapters.filesystem import FilesystemAdapter
from sublime.adapters.subsonic import api_objects as SubsonicAPI

MOCK_DATA_FILES = Path(__file__).parent.joinpath("mock_data")
MOCK_ALBUM_ART = MOCK_DATA_FILES.joinpath("album-art.png")
MOCK_ALBUM_ART2 = MOCK_DATA_FILES.joinpath("album-art2.png")
MOCK_ALBUM_ART3 = MOCK_DATA_FILES.joinpath("album-art3.png")
MOCK_SONG_FILE = MOCK_DATA_FILES.joinpath("test-song.mp3")
MOCK_SONG_FILE2 = MOCK_DATA_FILES.joinpath("test-song2.mp3")
MOCK_ALBUM_ART_HASH = "5d7bee4f3fe25b18cd2a66f1c9767e381bc64328"
MOCK_ALBUM_ART2_HASH = "031a8a1ca01f64f851a22d5478e693825a00fb23"
MOCK_ALBUM_ART3_HASH = "46a8af0f8fe370e59202a545803e8bbb3a4a41ee"
MOCK_SONG_FILE_HASH = "fe12d0712dbfd6ff7f75ef3783856a7122a78b0a"
MOCK_SONG_FILE2_HASH = "c32597c724e2e484dbf5856930b2e5bb80de13b7"

MOCK_SUBSONIC_SONGS = [
    SubsonicAPI.Song(
        "2",
        title="Song 2",
        parent_id="d1",
        _album="foo",
        album_id="a1",
        _artist="cool",
        artist_id="art1",
        duration=timedelta(seconds=20.8),
        path="foo/song2.mp3",
        cover_art="s2",
        _genre="Bar",
    ),
    SubsonicAPI.Song(
        "1",
        title="Song 1",
        parent_id="d1",
        _album="foo",
        album_id="a1",
        _artist="foo",
        artist_id="art2",
        duration=timedelta(seconds=10.2),
        path="foo/song1.mp3",
        cover_art="s1",
        _genre="Foo",
    ),
    SubsonicAPI.Song(
        "1",
        title="Song 1",
        parent_id="d1",
        _album="foo",
        album_id="a1",
        _artist="foo",
        artist_id="art2",
        duration=timedelta(seconds=10.2),
        path="foo/song1.mp3",
        cover_art="s1",
        _genre="Foo",
    ),
]

KEYS = FilesystemAdapter.CachedDataKey


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


def verify_songs(
    actual_songs: Iterable[SublimeAPI.Song], expected_songs: Iterable[SubsonicAPI.Song]
):
    actual_songs, expected_songs = (list(actual_songs), list(expected_songs))
    assert len(actual_songs) == len(expected_songs)
    for actual, song in zip(actual_songs, expected_songs):
        for k, v in asdict(song).items():
            if k in ("_genre", "_album", "_artist", "album_id", "artist_id"):
                continue
            print(k, "->", v)  # noqa: T001

            actual_value = getattr(actual, k, None)

            if k == "album":
                assert ("a1", "foo") == (actual_value.id, actual_value.name)
            elif k == "genre":
                assert v["name"] == actual_value.name
            elif k == "artist":
                assert (v["id"], v["name"]) == (actual_value.id, actual_value.name)
            else:
                assert actual_value == v


def test_caching_get_playlists(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_playlists()

    # Ingest an empty list (for example, no playlists added yet to server).
    cache_adapter.ingest_new_data(KEYS.PLAYLISTS, (), [])

    # After the first cache miss of get_playlists, even if an empty list is
    # returned, the next one should not be a cache miss.
    cache_adapter.get_playlists()

    # Ingest two playlists.
    cache_adapter.ingest_new_data(
        KEYS.PLAYLISTS,
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
        KEYS.PLAYLISTS,
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

    # Simulate the playlist being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "test1", songs=MOCK_SUBSONIC_SONGS[:2]),
    )

    playlist = cache_adapter.get_playlist_details("1")
    assert playlist.id == "1"
    assert playlist.name == "test1"
    assert playlist.song_count == 2
    assert playlist.duration == timedelta(seconds=31)
    verify_songs(playlist.songs, MOCK_SUBSONIC_SONGS[:2])

    # "Force refresh" the playlist and add a new song (duplicate).
    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "foo", songs=MOCK_SUBSONIC_SONGS),
    )

    playlist = cache_adapter.get_playlist_details("1")
    assert playlist.id == "1"
    assert playlist.name == "foo"
    assert playlist.song_count == 3
    assert playlist.duration == timedelta(seconds=41.2)
    verify_songs(playlist.songs, MOCK_SUBSONIC_SONGS)

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
        KEYS.PLAYLISTS,
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
        KEYS.PLAYLIST_DETAILS, ("1",), SubsonicAPI.PlaylistWithSongs("1", "test1"),
    )

    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
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
        KEYS.COVER_ART_FILE, ("pl_test1",), MOCK_ALBUM_ART,
    )
    with open(cache_adapter.get_cover_art_uri("pl_test1", "file"), "wb+") as cached:
        with open(MOCK_ALBUM_ART, "wb+") as expected:
            assert cached.read() == expected.read()


def test_invalidate_playlist(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        KEYS.PLAYLISTS,
        (),
        [SubsonicAPI.Playlist("1", "test1"), SubsonicAPI.Playlist("2", "test2")],
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("pl_test1",), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
        ("2",),
        SubsonicAPI.PlaylistWithSongs("2", "test2", cover_art="pl_2", songs=[]),
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("pl_2",), MOCK_ALBUM_ART2,
    )

    stale_uri_1 = cache_adapter.get_cover_art_uri("pl_test1", "file")
    stale_uri_2 = cache_adapter.get_cover_art_uri("pl_2", "file")

    cache_adapter.invalidate_data(KEYS.PLAYLISTS, ())
    cache_adapter.invalidate_data(KEYS.PLAYLIST_DETAILS, ("2",))
    cache_adapter.invalidate_data(KEYS.COVER_ART_FILE, ("pl_test1",))

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


def test_invalidate_song_file(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(KEYS.SONG, ("2",), MOCK_SUBSONIC_SONGS[0])
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("s1", "song"), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(KEYS.SONG_FILE, ("1",), (None, MOCK_SONG_FILE))
    cache_adapter.ingest_new_data(KEYS.SONG_FILE, ("2",), (None, MOCK_SONG_FILE2))

    cache_adapter.invalidate_data(KEYS.SONG_FILE, ("1",))
    cache_adapter.invalidate_data(KEYS.COVER_ART_FILE, ("s1", "song"))

    with pytest.raises(CacheMissError):
        cache_adapter.get_song_uri("1", "file")

    with pytest.raises(CacheMissError):
        cache_adapter.get_cover_art_uri("s1", "file")

    # Make sure it didn't delete the other song.
    assert cache_adapter.get_song_uri("2", "file").endswith("song2.mp3")


def test_malformed_song_path(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])
    cache_adapter.ingest_new_data(KEYS.SONG, ("2",), MOCK_SUBSONIC_SONGS[0])
    cache_adapter.ingest_new_data(
        KEYS.SONG_FILE, ("1",), ("/malformed/path", MOCK_SONG_FILE)
    )
    cache_adapter.ingest_new_data(
        KEYS.SONG_FILE, ("2",), ("fine/path/song2.mp3", MOCK_SONG_FILE2)
    )

    song_uri = cache_adapter.get_song_uri("1", "file")
    assert song_uri.endswith(f"/music/{MOCK_SONG_FILE_HASH}")

    song_uri2 = cache_adapter.get_song_uri("2", "file")
    assert song_uri2.endswith("fine/path/song2.mp3")


def test_get_cached_status(cache_adapter: FilesystemAdapter):
    print('ohea1')
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])
    assert (
        cache_adapter.get_cached_status(cache_adapter.get_song_details("1"))
        == SongCacheStatus.NOT_CACHED
    )

    print('ohea2')
    cache_adapter.ingest_new_data(KEYS.SONG_FILE, ("1",), (None, MOCK_SONG_FILE))
    assert (
        cache_adapter.get_cached_status(cache_adapter.get_song_details("1"))
        == SongCacheStatus.CACHED
    )

    print('ohea3')
    cache_adapter.ingest_new_data(KEYS.SONG_FILE_PERMANENT, ("1",), None)
    assert (
        cache_adapter.get_cached_status(cache_adapter.get_song_details("1"))
        == SongCacheStatus.PERMANENTLY_CACHED
    )

    print('ohea4')
    cache_adapter.invalidate_data(KEYS.SONG_FILE, ("1",))
    assert (
        cache_adapter.get_cached_status(cache_adapter.get_song_details("1"))
        == SongCacheStatus.CACHED_STALE
    )

    print('ohea5')
    cache_adapter.delete_data(KEYS.SONG_FILE, ("1",))
    assert (
        cache_adapter.get_cached_status(cache_adapter.get_song_details("1"))
        == SongCacheStatus.NOT_CACHED
    )


def test_delete_playlists(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
        ("1",),
        SubsonicAPI.PlaylistWithSongs("1", "test1", cover_art="pl_1", songs=[]),
    )
    cache_adapter.ingest_new_data(
        KEYS.PLAYLIST_DETAILS,
        ("2",),
        SubsonicAPI.PlaylistWithSongs("2", "test1", cover_art="pl_2", songs=[]),
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("pl_1",), MOCK_ALBUM_ART,
    )

    # Deleting a playlist should get rid of it entirely.
    cache_adapter.delete_data(KEYS.PLAYLIST_DETAILS, ("2",))
    try:
        cache_adapter.get_playlist_details("2")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    # Deleting a playlist with associated cover art should get rid the cover art too.
    cache_adapter.delete_data(KEYS.PLAYLIST_DETAILS, ("1",))
    try:
        cache_adapter.get_cover_art_uri("pl_1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    # Even if the cover art failed to be deleted, it should cache miss.
    shutil.copy(
        MOCK_ALBUM_ART, str(cache_adapter.cover_art_dir.joinpath(MOCK_ALBUM_ART_HASH)),
    )
    try:
        cache_adapter.get_cover_art_uri("pl_1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None


def test_delete_song_data(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])
    cache_adapter.ingest_new_data(KEYS.SONG_FILE, ("1",), (None, MOCK_SONG_FILE))
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("s1",), MOCK_ALBUM_ART,
    )

    music_file_path = cache_adapter.get_song_uri("1", "file")
    cover_art_path = cache_adapter.get_cover_art_uri("s1", "file")

    cache_adapter.delete_data(KEYS.SONG_FILE, ("1",))
    cache_adapter.delete_data(KEYS.COVER_ART_FILE, ("s1",))

    assert not Path(music_file_path).exists()
    assert not Path(cover_art_path).exists()

    try:
        cache_adapter.get_song_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None

    try:
        cache_adapter.get_cover_art_uri("s1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data is None


def test_caching_get_genres(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_genres()

    cache_adapter.ingest_new_data(KEYS.SONG, ("2",), MOCK_SUBSONIC_SONGS[0])
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])

    # Getting genres now should look at what's on the songs. This sould cache miss, but
    # still give some data.
    try:
        cache_adapter.get_genres()
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert [g.name for g in cast(Iterable, e.partial_data)] == ["Bar", "Foo"]

    # After we actually ingest the actual list, it should be returned instead.
    cache_adapter.ingest_new_data(
        KEYS.GENRES,
        (),
        [
            SubsonicAPI.Genre("Bar", 10, 20),
            SubsonicAPI.Genre("Baz", 10, 20),
            SubsonicAPI.Genre("Foo", 10, 20),
        ],
    )
    assert {g.name for g in cache_adapter.get_genres()} == {"Bar", "Baz", "Foo"}


def test_caching_get_song_details(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_song_details("1")

    # Simulate the song details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(KEYS.SONG, ("1",), MOCK_SUBSONIC_SONGS[1])

    song = cache_adapter.get_song_details("1")
    assert song.id == "1"
    assert song.title == "Song 1"
    assert song.album
    assert (song.album.id, song.album.name) == ("a1", "foo")
    assert song.artist and song.artist.name == "foo"
    assert song.parent_id == "d1"
    assert song.duration == timedelta(seconds=10.2)
    assert song.path == "foo/song1.mp3"
    assert song.genre and song.genre.name == "Foo"

    # "Force refresh" the song details
    cache_adapter.ingest_new_data(
        KEYS.SONG,
        ("1",),
        SubsonicAPI.Song(
            "1",
            title="Song 1",
            parent_id="bar",
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
    assert song.parent_id == "bar"
    assert song.duration == timedelta(seconds=10.2)
    assert song.path == "bar/song1.mp3"
    assert song.genre and song.genre.name == "Bar"

    with pytest.raises(CacheMissError):
        cache_adapter.get_playlist_details("2")


def test_caching_less_info(cache_adapter: FilesystemAdapter):
    cache_adapter.ingest_new_data(
        KEYS.SONG,
        ("1",),
        SubsonicAPI.Song(
            "1",
            title="Song 1",
            parent_id="bar",
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
        KEYS.SONG,
        ("1",),
        SubsonicAPI.Song(
            "1",
            title="Song 1",
            parent_id="bar",
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
        KEYS.ARTISTS,
        (),
        [
            SubsonicAPI.ArtistAndArtistInfo("1", "test1", album_count=3, albums=[]),
            SubsonicAPI.ArtistAndArtistInfo("2", "test2", album_count=4),
        ],
    )

    artists = cache_adapter.get_artists()
    assert len(artists) == 2
    assert (artists[0].id, artists[0].name, artists[0].album_count) == ("1", "test1", 3)
    assert (artists[1].id, artists[1].name, artists[1].album_count) == ("2", "test2", 4)

    # Ingest a new artists list with one of them deleted.
    cache_adapter.ingest_new_data(
        KEYS.ARTISTS,
        (),
        [
            SubsonicAPI.ArtistAndArtistInfo("1", "test1", album_count=3),
            SubsonicAPI.ArtistAndArtistInfo("3", "test3", album_count=8),
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
    cache_adapter.ingest_new_data(KEYS.IGNORED_ARTICLES, (), {"Foo", "Bar"})
    artists = cache_adapter.get_ignored_articles()
    assert {"Foo", "Bar"} == artists

    # Ingest a new artists list with one of them deleted.
    cache_adapter.ingest_new_data(KEYS.IGNORED_ARTICLES, (), {"Foo", "Baz"})
    artists = cache_adapter.get_ignored_articles()
    assert {"Foo", "Baz"} == artists


def test_caching_get_artist(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_artist("1")

    # Simulate the artist details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.ARTIST,
        ("1",),
        SubsonicAPI.ArtistAndArtistInfo(
            "1",
            "Bar",
            album_count=1,
            artist_image_url="image",
            similar_artists=[
                SubsonicAPI.ArtistAndArtistInfo("A", "B"),
                SubsonicAPI.ArtistAndArtistInfo("C", "D"),
            ],
            biography="this is a bio",
            music_brainz_id="mbid",
            albums=[SubsonicAPI.Album("1", "Foo", artist_id="1")],
        ),
    )

    artist = cache_adapter.get_artist("1")
    assert artist.artist_image_url and (
        artist.id,
        artist.name,
        artist.album_count,
        artist.artist_image_url,
        artist.biography,
        artist.music_brainz_id,
    ) == ("1", "Bar", 1, "image", "this is a bio", "mbid")
    assert artist.similar_artists == [
        SubsonicAPI.ArtistAndArtistInfo("A", "B"),
        SubsonicAPI.ArtistAndArtistInfo("C", "D"),
    ]
    assert artist.albums and len(artist.albums) == 1
    assert cast(SelectQuery, artist.albums).dicts() == [SubsonicAPI.Album("1", "Foo")]

    # Simulate "force refreshing" the artist details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.ARTIST,
        ("1",),
        SubsonicAPI.ArtistAndArtistInfo(
            "1",
            "Foo",
            album_count=2,
            artist_image_url="image2",
            similar_artists=[
                SubsonicAPI.ArtistAndArtistInfo("A", "B"),
                SubsonicAPI.ArtistAndArtistInfo("E", "F"),
            ],
            biography="this is a bio2",
            music_brainz_id="mbid2",
            albums=[
                SubsonicAPI.Album("1", "Foo", artist_id="1"),
                SubsonicAPI.Album("2", "Bar", artist_id="1"),
            ],
        ),
    )

    artist = cache_adapter.get_artist("1")
    assert artist.artist_image_url and (
        artist.id,
        artist.name,
        artist.album_count,
        artist.artist_image_url,
        artist.biography,
        artist.music_brainz_id,
    ) == ("1", "Foo", 2, "image2", "this is a bio2", "mbid2")
    assert artist.similar_artists == [
        SubsonicAPI.ArtistAndArtistInfo("A", "B"),
        SubsonicAPI.ArtistAndArtistInfo("E", "F"),
    ]
    assert artist.albums and len(artist.albums) == 2
    assert cast(SelectQuery, artist.albums).dicts() == [
        SubsonicAPI.Album("1", "Foo"),
        SubsonicAPI.Album("2", "Bar"),
    ]


def test_caching_get_album(cache_adapter: FilesystemAdapter):
    with pytest.raises(CacheMissError):
        cache_adapter.get_album("1")

    # Simulate the artist details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.ALBUM,
        ("a1",),
        SubsonicAPI.Album(
            "a1",
            "foo",
            cover_art="c",
            song_count=2,
            year=2020,
            duration=timedelta(seconds=31),
            play_count=20,
            _artist="cool",
            artist_id="art1",
            songs=MOCK_SUBSONIC_SONGS[:2],
        ),
    )

    album = cache_adapter.get_album("a1")
    assert album and album.cover_art
    assert (
        album.id,
        album.name,
        album.cover_art,
        album.song_count,
        album.year,
        album.play_count,
    ) == ("a1", "foo", "c", 2, 2020, 20,)
    assert album.artist
    assert (album.artist.id, album.artist.name) == ("art1", "cool")
    assert album.songs
    verify_songs(album.songs, MOCK_SUBSONIC_SONGS[:2])


def test_caching_invalidate_artist(cache_adapter: FilesystemAdapter):
    # Simulate the artist details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.ARTIST,
        ("artist1",),
        SubsonicAPI.ArtistAndArtistInfo(
            "artist1",
            "Bar",
            album_count=1,
            artist_image_url="image",
            similar_artists=[
                SubsonicAPI.ArtistAndArtistInfo("A", "B"),
                SubsonicAPI.ArtistAndArtistInfo("C", "D"),
            ],
            biography="this is a bio",
            music_brainz_id="mbid",
            albums=[
                SubsonicAPI.Album("1", "Foo", artist_id="1"),
                SubsonicAPI.Album("2", "Bar", artist_id="1"),
            ],
        ),
    )
    cache_adapter.ingest_new_data(
        KEYS.ALBUM,
        ("1",),
        SubsonicAPI.Album("1", "Foo", artist_id="artist1", cover_art="1"),
    )
    cache_adapter.ingest_new_data(
        KEYS.ALBUM,
        ("2",),
        SubsonicAPI.Album("2", "Bar", artist_id="artist1", cover_art="2"),
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("image",), MOCK_ALBUM_ART3,
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("1",), MOCK_ALBUM_ART,
    )
    cache_adapter.ingest_new_data(
        KEYS.COVER_ART_FILE, ("2",), MOCK_ALBUM_ART2,
    )

    stale_artist = cache_adapter.get_artist("artist1")
    stale_album_1 = cache_adapter.get_album("1")
    stale_album_2 = cache_adapter.get_album("2")
    stale_artist_artwork = cache_adapter.get_cover_art_uri("image", "file")
    stale_cover_art_1 = cache_adapter.get_cover_art_uri("1", "file")
    stale_cover_art_2 = cache_adapter.get_cover_art_uri("2", "file")

    cache_adapter.invalidate_data(KEYS.ARTIST, ("artist1",))

    # Test the cascade of cache invalidations.
    try:
        cache_adapter.get_artist("artist1")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_artist

    try:
        cache_adapter.get_album("1")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_album_1

    try:
        cache_adapter.get_album("2")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_album_2

    try:
        cache_adapter.get_cover_art_uri("image", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_artist_artwork

    try:
        cache_adapter.get_cover_art_uri("1", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_cover_art_1

    try:
        cache_adapter.get_cover_art_uri("2", "file")
        assert 0, "DID NOT raise CacheMissError"
    except CacheMissError as e:
        assert e.partial_data
        assert e.partial_data == stale_cover_art_2


def test_get_music_directory(cache_adapter: FilesystemAdapter):
    dir_id = "d1"
    with pytest.raises(CacheMissError):
        cache_adapter.get_directory(dir_id)

    # Simulate the directory details being retrieved from Subsonic.
    cache_adapter.ingest_new_data(
        KEYS.DIRECTORY,
        (dir_id,),
        SubsonicAPI.Directory(
            dir_id,
            title="foo",
            parent_id=None,
            _children=[json.loads(s.to_json()) for s in MOCK_SUBSONIC_SONGS[:2]]
            + [
                {
                    "id": "542",
                    "parent": dir_id,
                    "isDir": True,
                    "title": "Crash My Party",
                }
            ],
        ),
    )

    directory = cache_adapter.get_directory(dir_id)
    assert directory and directory.id == dir_id
    assert directory.name == "foo"
    assert directory.parent_id == "root"

    dir_child, *song_children = directory.children
    verify_songs(song_children, MOCK_SUBSONIC_SONGS[:2])
    assert dir_child.id == "542"
    assert dir_child.parent_id
    assert dir_child.name == "Crash My Party"


def test_search(adapter: FilesystemAdapter):
    # TODO
    pass
