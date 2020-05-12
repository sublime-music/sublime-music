import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, List, Tuple

import pytest

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


def test_can_service_requests(adapter: SubsonicAdapter):
    # Mock a connection error
    adapter._set_mock_data(Exception())
    assert not adapter.can_service_requests

    # Simulate some sort of ping error
    for filename, data in mock_data_files("ping_failed"):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)
        assert not adapter.can_service_requests

    # Simulate valid ping
    adapter._set_mock_data(mock_json())
    adapter._set_ping_status()
    assert adapter.can_service_requests


def test_get_playlists(adapter: SubsonicAdapter):
    expected = [
        SubsonicAPI.Playlist(
            id="2",
            name="Test",
            song_count=132,
            duration=timedelta(seconds=33072),
            created=datetime(2020, 3, 27, 5, 38, 45, 0, tzinfo=timezone.utc),
            changed=datetime(2020, 4, 9, 16, 3, 26, 0, tzinfo=timezone.utc),
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
            created=datetime(2020, 3, 27, 5, 39, 4, 0, tzinfo=timezone.utc),
            changed=datetime(2020, 3, 27, 5, 45, 23, 0, tzinfo=timezone.utc),
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
        assert adapter.get_playlists() == expected

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
            _parent="318",
            title="What a Beautiful Name",
            _album="What a Beautiful Name - Single",
            album_id="48",
            _artist="Hillsong Worship",
            artist_id="38",
            track=1,
            year=2016,
            _genre="Christian & Gospel",
            cover_art="318",
            size=8381640,
            content_type="audio/mp4",
            suffix="m4a",
            transcoded_content_type="audio/mpeg",
            transcoded_suffix="mp3",
            duration=timedelta(seconds=238),
            bit_rate=256,
            path="/".join(
                (
                    "Hillsong Worship",
                    "What a Beautiful Name - Single",
                    "01 What a Beautiful Name.m4a",
                )
            ),
            is_video=False,
            play_count=20,
            disc_number=1,
            created=datetime(2020, 3, 27, 5, 17, 7, tzinfo=timezone.utc),
            type=SubsonicAPI.SublimeAPI.MediaType.MUSIC,
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
                    _parent="318",
                    title="What a Beautiful Name",
                    _album="What a Beautiful Name - Single",
                    album_id="48",
                    _artist="Hillsong Worship",
                    artist_id="38",
                    track=1,
                    year=2016,
                    _genre="Christian & Gospel",
                    cover_art="318",
                    size=8381640,
                    content_type="audio/mp4",
                    suffix="m4a",
                    transcoded_content_type="audio/mpeg",
                    transcoded_suffix="mp3",
                    duration=timedelta(seconds=238),
                    bit_rate=256,
                    path="/".join(
                        (
                            "Hillsong Worship",
                            "What a Beautiful Name - Single",
                            "01 What a Beautiful Name.m4a",
                        )
                    ),
                    is_video=False,
                    play_count=20,
                    disc_number=1,
                    created=datetime(2020, 3, 27, 5, 17, 7, tzinfo=timezone.utc),
                    type=SubsonicAPI.SublimeAPI.MediaType.MUSIC,
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
        assert song.path.endswith("Sweet Caroline.mp3")
        assert song.parent and song.parent.id == "544"
        assert song.artist
        assert (song.artist.id, song.artist.name) == ("60", "Neil Diamond")
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
        assert artist.artist_image_url == "ar-3"
        assert artist.biography and len(artist.biography) > 0
        assert artist.name == "Kane Brown"
        assert ("3", "Kane Brown") == (artist.albums[0].id, artist.albums[0].name)


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
