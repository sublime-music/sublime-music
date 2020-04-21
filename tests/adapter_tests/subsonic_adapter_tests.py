import importlib
import importlib.util
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

import pytest

from sublime.adapters.subsonic import (
    api_objects as SubsonicAPI,
    SubsonicAdapter,
)

MOCK_DATA_FILES = Path(__file__).parent.joinpath('mock_data')


@pytest.fixture
def adapter(tmp_path: Path):
    adapter = SubsonicAdapter(
        {
            'server_address': 'http://subsonic.example.com',
            'username': 'test',
            'password': 'testpass',
        },
        tmp_path,
    )
    adapter._is_mock = True
    yield adapter


def mock_data_files(
        request_name: str,
        mode: str = 'r',
) -> Generator[str, None, None]:
    """
    Yields all of the files in the mock_data directory that start with
    ``request_name``.
    """
    for file in MOCK_DATA_FILES.iterdir():
        if file.name.split('-')[0] in request_name:
            with open(file, mode) as f:
                yield file, f.read()


def mock_json(**obj: Any) -> str:
    return json.dumps(
        {
            'subsonic-response': {
                'status': 'ok',
                'version': '1.15.0',
                **obj,
            },
        })


def camel_to_snake(name: str) -> str:
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def test_request_making_methods(adapter: SubsonicAdapter):
    expected = {
        'u': 'test',
        'p': 'testpass',
        'c': 'Sublime Music',
        'f': 'json',
        'v': '1.15.0',
    }
    assert (sorted(expected.items()) == sorted(adapter._get_params().items()))

    assert adapter._make_url(
        'foo') == 'http://subsonic.example.com/rest/foo.view'


def test_can_service_requests(adapter: SubsonicAdapter):
    # Mock a connection error
    adapter._set_mock_data(Exception())
    assert adapter.can_service_requests is False

    # Simulate some sort of ping error
    for filename, data in mock_data_files('ping_failed'):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)
        assert adapter.can_service_requests is False

    # Simulate valid ping
    adapter._set_mock_data(mock_json())
    assert adapter.can_service_requests is True


def test_get_playlists(adapter: SubsonicAdapter):
    expected = [
        SubsonicAPI.Playlist(
            id='2',
            name='Test',
            song_count=132,
            duration=timedelta(seconds=33072),
            created=datetime(2020, 3, 27, 5, 38, 45, 0, tzinfo=timezone.utc),
            changed=datetime(2020, 4, 9, 16, 3, 26, 0, tzinfo=timezone.utc),
            comment='Foo',
            owner='foo',
            public=True,
            cover_art='pl-2',
        ),
        SubsonicAPI.Playlist(
            id='3',
            name='Bar',
            song_count=23,
            duration=timedelta(seconds=847),
            created=datetime(2020, 3, 27, 5, 39, 4, 0, tzinfo=timezone.utc),
            changed=datetime(2020, 3, 27, 5, 45, 23, 0, tzinfo=timezone.utc),
            comment='',
            owner='foo',
            public=False,
            cover_art='pl-3',
        ),
    ]

    for filename, data in mock_data_files('get_playlists'):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)
        assert adapter.get_playlists() == expected

    # When playlists is null, expect an empty list.
    adapter._set_mock_data(mock_json())
    assert adapter.get_playlists() == []


def test_get_playlist_details(adapter: SubsonicAdapter):
    for filename, data in mock_data_files('get_playlist_details'):
        logging.info(filename)
        logging.debug(data)
        adapter._set_mock_data(data)

        playlist_details = adapter.get_playlist_details('2')

        # Make sure that the song count is correct even if it's not provided.
        # Old versions of Subsonic don't have these properties.
        assert len(playlist_details.songs) == 2
        assert playlist_details.duration == timedelta(seconds=470)

        # Make sure that at least the first song got decoded properly.
        assert playlist_details.songs[0] == SubsonicAPI.Child(
            id='202',
            parent='318',
            title='What a Beautiful Name',
            album='What a Beautiful Name - Single',
            artist='Hillsong Worship',
            track=1,
            year=2016,
            genre='Christian & Gospel',
            cover_art='318',
            size=8381640,
            content_type="audio/mp4",
            suffix="m4a",
            transcoded_content_type="audio/mpeg",
            transcoded_suffix="mp3",
            duration=238,
            bit_rate=256,
            path='/'.join(
                (
                    'Hillsong Worship',
                    'What a Beautiful Name - Single',
                    '01 What a Beautiful Name.m4a',
                )),
            is_video=False,
            play_count=20,
            disc_number=1,
            created=datetime(2020, 3, 27, 5, 17, 7, tzinfo=timezone.utc),
            album_id="48",
            artist_id="38",
            type=SubsonicAPI.SublimeAPI.MediaType.MUSIC,
        )
