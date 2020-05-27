import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep
from typing import Any, Generator, List, Tuple

import pytest
from dateutil.tz import tzutc

from sublime.adapters.subsonic import (
    api_objects as SubsonicAPI,
    SubsonicAdapter,
)

MOCK_DATA_FILES = Path(__file__).parent.joinpath("mock_data")


@pytest.fixture
def adapter(tmp_path: Path):
    adapter = SubsonicAdapter(
        {
            "server_address": "http://subsonic.example.com",
            "username": "test",
            "password": "testpass",
        },
        tmp_path,
    )
    adapter._is_mock = True
    yield adapter
    adapter.shutdown()


def mock_data_files(
    request_name: str, mode: str = "r"
) -> Generator[Tuple[Path, Any], None, None]:
    """
    Yields all of the files, and each of the elements of in the file (separated by a
    line of ='s), for all files in the mock_data directory that start with
    ``request_name``. This only works for text such as JSON.
    """
    sep_re = re.compile(r"=+\n")

    num_files = 0
    for file in MOCK_DATA_FILES.iterdir():
        if file.name.split("-")[0] == request_name:
            with open(file, mode) as f:
                parts: List[str] = []
                aggregate: List[str] = []
                for line in f:
                    if sep_re.match(line):
                        parts.append("\n".join(aggregate))
                        aggregate = []
                        continue
                    aggregate.append(line)

                parts.append("\n".join(aggregate))
                print(file)  # noqa: T001
                num_files += 1
                yield file, iter(parts)

    # Make sure that is at least one test file
    assert num_files > 0


def mock_json(**obj: Any) -> str:
    return json.dumps(
        {"subsonic-response": {"status": "ok", "version": "1.15.0", **obj}}
    )


def camel_to_snake(name: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def test_request_making_methods(adapter: SubsonicAdapter):
    expected = {
        "u": "test",
        "p": "testpass",
        "c": "Sublime Music",
        "f": "json",
        "v": "1.15.0",
    }
    assert sorted(expected.items()) == sorted(adapter._get_params().items())

    assert adapter._make_url("foo") == "http://subsonic.example.com/rest/foo.view"


def test_ping_status(adapter: SubsonicAdapter):
    # Mock a connection error
    adapter._set_mock_data(Exception())
    assert not adapter.ping_status

    # Simulate some sort of ping error
    for filename, data in mock_data_files("ping_failed"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)
        assert not adapter.ping_status

    # Simulate valid ping
    adapter._set_mock_data(mock_json())
    adapter._last_ping_timestamp.value = 0.0
    adapter._set_ping_status()
    assert adapter.ping_status


def test_get_playlists(adapter: SubsonicAdapter):
    expected = [
        SubsonicAPI.Playlist(
            id="2",
            name="Test",
            song_count=132,
            duration=timedelta(seconds=33072),
            created=datetime(2020, 3, 27, 5, 38, 45, 0, tzinfo=tzutc()),
            changed=datetime(2020, 4, 9, 16, 3, 26, 0, tzinfo=tzutc()),
            comment="Foo",
            owner="foo",
            public=True,
            cover_art="pl-2",
        ),
        SubsonicAPI.Playlist(
            id="3",
            name="Bar",
            song_count=23,
            duration=timedelta(seconds=847),
            created=datetime(2020, 3, 27, 5, 39, 4, 0, tzinfo=tzutc()),
            changed=datetime(2020, 3, 27, 5, 45, 23, 0, tzinfo=tzutc()),
            comment="",
            owner="foo",
            public=False,
            cover_art="pl-3",
        ),
    ]

    for filename, data in mock_data_files("get_playlists"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)
        assert adapter.get_playlists() == sorted(expected, key=lambda e: e.name)

    # When playlists is null, expect an empty list.
    adapter._set_mock_data(mock_json())
    assert adapter.get_playlists() == []


def test_get_playlist_details(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_playlist_details"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        playlist_details = adapter.get_playlist_details("2")

        # Make sure that the song count is correct even if it's not provided.
        # Old versions of Subsonic don't have these properties.
        assert len(playlist_details.songs) == 2
        assert playlist_details.duration == timedelta(seconds=470)

        # Make sure that at least the first song got decoded properly.
        assert playlist_details.songs[0] == SubsonicAPI.Song(
            id="202",
            parent_id="318",
            title="What a Beautiful Name",
            _album="What a Beautiful Name - Single",
            album_id="48",
            _artist="Hillsong Worship",
            artist_id="38",
            track=1,
            year=2016,
            _genre="Christian & Gospel",
            cover_art="318",
            duration=timedelta(seconds=238),
            path="/".join(
                (
                    "Hillsong Worship",
                    "What a Beautiful Name - Single",
                    "01 What a Beautiful Name.m4a",
                )
            ),
            disc_number=1,
        )


def test_create_playlist(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("create_playlist"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        adapter.create_playlist(
            name="Foo",
            songs=[
                SubsonicAPI.Song(
                    id="202",
                    parent_id="318",
                    title="What a Beautiful Name",
                    _album="What a Beautiful Name - Single",
                    album_id="48",
                    _artist="Hillsong Worship",
                    artist_id="38",
                    track=1,
                    year=2016,
                    _genre="Christian & Gospel",
                    cover_art="318",
                    duration=timedelta(seconds=238),
                    path="/".join(
                        (
                            "Hillsong Worship",
                            "What a Beautiful Name - Single",
                            "01 What a Beautiful Name.m4a",
                        )
                    ),
                    disc_number=1,
                )
            ],
        )


def test_update_playlist(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("update_playlist"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        result_playlist = adapter.update_playlist(
            "1", name="Foo", comment="Bar", public=True, song_ids=["202"]
        )

        assert result_playlist.comment == "Bar"
        assert result_playlist.public is False


def test_get_song_details(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_song_details"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        song = adapter.get_song_details("1")
        assert (song.id, song.title, song.year, song.cover_art, song.duration) == (
            "1",
            "Sweet Caroline",
            2017,
            "544",
            timedelta(seconds=203),
        )
        assert song.path and song.path.endswith("Sweet Caroline.mp3")
        assert song.parent_id == "544"
        assert song.artist
        assert (song.artist.id, song.artist.name) == ("60", "Neil Diamond")
        assert song.album
        assert (song.album.id, song.album.name) == ("88", "50th Anniversary Collection")
        assert song.genre and song.genre.name == "Pop"


def test_get_song_details_missing_data(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_song_details_no_albumid"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        song = adapter.get_song_details("1")
        assert (song.id, song.title, song.year, song.cover_art, song.duration) == (
            "1",
            "Sweet Caroline",
            2017,
            "544",
            timedelta(seconds=203),
        )
        assert song.path and song.path.endswith("Sweet Caroline.mp3")
        assert song.parent_id == "544"
        assert song.artist
        assert (song.artist.id, song.artist.name) == ("60", "Neil Diamond")
        assert song.album
        assert (song.album.id, song.album.name) == (None, "50th Anniversary Collection")
        assert song.genre and song.genre.name == "Pop"

    for filename, data in mock_data_files("get_song_details_no_artistid"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        song = adapter.get_song_details("1")
        assert (song.id, song.title, song.year, song.cover_art, song.duration) == (
            "1",
            "Sweet Caroline",
            2017,
            "544",
            timedelta(seconds=203),
        )
        assert song.path and song.path.endswith("Sweet Caroline.mp3")
        assert song.parent_id == "544"
        assert song.artist
        assert (song.artist.id, song.artist.name) == (None, "Neil Diamond")
        assert song.album
        assert (song.album.id, song.album.name) == ("88", "50th Anniversary Collection")
        assert song.genre and song.genre.name == "Pop"


def test_get_genres(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_genres"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        genres = adapter.get_genres()

        assert len(genres) == 2
        assert [g.name for g in genres] == ["Country", "Pop"]


def test_get_artists(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_artists"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        artists = adapter.get_artists()
        assert len(artists) == 7
        assert {a.name for a in artists} == {
            "Adele",
            "Austin  French",
            "The Afters",
            "The Band Perry",
            "Basshunter",
            "Zac Brown Band",
            "Zach Williams",
        }


def test_get_ignored_articles(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_artists"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        ignored_articles = adapter.get_ignored_articles()
        assert ignored_articles == {"The", "El", "La", "Los", "Las", "Le", "Les"}


def test_get_ignored_articles_from_cached_get_artists(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_artists"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        adapter.get_artists()
        ignored_articles = adapter.get_ignored_articles()
        assert ignored_articles == {"The", "El", "La", "Los", "Las", "Le", "Les"}


def test_get_artist(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_artist"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        artist = adapter.get_artist("3")
        assert artist.album_count == 1
        assert artist.albums and len(artist.albums) == 1
        assert ("3", "Kane Brown") == (artist.albums[0].id, artist.albums[0].name)
        assert artist.artist_image_url == "ar-3"
        assert artist.biography and len(artist.biography) > 0
        assert artist.name == "Kane Brown"
        assert artist.similar_artists
        assert len(artist.similar_artists) == 20
        assert (first_similar := artist.similar_artists[0])
        assert first_similar
        assert first_similar.name == "Luke Combs"
        assert first_similar.artist_image_url == "ar-158"


def test_get_artist_with_good_image_url(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_artist_good_image_url"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        artist = adapter.get_artist("3")
        assert artist.album_count == 1
        assert artist.albums and len(artist.albums) == 1
        assert artist.biography and len(artist.biography) > 0
        assert artist.name == "Kane Brown"
        assert ("3", "Kane Brown") == (artist.albums[0].id, artist.albums[0].name)
        assert (
            artist.artist_image_url
            == "http://entertainermag.com/wp-content/uploads/2017/04/Kane-Brown-Web-Optimized.jpg"  # noqa: E501
        )


def test_get_play_queue(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_play_queue"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        play_queue = adapter.get_play_queue()
        assert play_queue
        assert play_queue.current_index and play_queue.current_index == 1
        assert play_queue.position == timedelta(milliseconds=98914)
        assert play_queue.username == "sumner"
        assert play_queue.changed == datetime(
            2020, 5, 12, 5, 16, 32, 114000, tzinfo=timezone.utc
        )
        assert play_queue.songs and len(play_queue.songs) == 5

        song = play_queue.songs[0]
        assert song.album and song.album.name == "Despacito"
        assert song.artist and song.artist.name == "Peter Bence"
        assert song.genre and song.genre.name == "Classical"


def test_get_album(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_album"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        album = adapter.get_album("243")
        assert (
            album.id,
            album.name,
            album.cover_art,
            album.song_count,
            album.year,
            album.duration,
        ) == (
            "243",
            "What You See Is What You Get",
            "al-243",
            17,
            2019,
            timedelta(seconds=3576),
        )
        assert album.artist
        assert (album.artist.id, album.artist.name) == ("158", "Luke Combs")
        assert album.genre and album.genre.name == "Country"
        assert album.songs
        assert len(album.songs) == 17
        assert [s.title for s in album.songs] == [
            "Beer Never Broke My Heart",
            "Refrigerator Door",
            "Even Though I'm Leaving",
            "Lovin' On You",
            "Moon Over Mexico",
            "1, 2 Many",
            "Blue Collar Boys",
            "New Every Day",
            "Reasons",
            "Every Little Bit Helps",
            "Dear Today",
            "What You See Is What You Get",
            "Does To Me",
            "Angels Workin' Overtime",
            "All Over Again",
            "Nothing Like You",
            "Better Together",
        ]


def test_get_music_directory(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("get_music_directory"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        directory = adapter.get_directory("3")
        assert directory.id == "60"
        assert directory.name == "Luke Bryan"
        assert directory.parent_id == "root"
        assert directory.children and len(directory.children) == 1
        child = directory.children[0]
        assert isinstance(child, SubsonicAPI.Directory)
        assert child.id == "542"
        assert child.name == "Crash My Party"
        assert child.parent_id == "60"

    for filename, data in mock_data_files("get_indexes"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        directory = adapter.get_directory("root")
        assert directory.id == "root"
        assert directory.parent_id is None
        assert len(directory.children) == 7
        child = directory.children[0]
        assert isinstance(child, SubsonicAPI.Directory)
        assert child.id == "73"
        assert child.name == "The Afters"
        assert child.parent_id == "root"


def test_search(adapter: SubsonicAdapter):
    for filename, data in mock_data_files("search3"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        search_results = adapter.search("3")
        assert len(search_results._songs) == 7
        assert len(search_results._artists) == 2
        assert len(search_results._albums) == 4
