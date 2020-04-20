import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import pytest

from dateutil import parser

from sublime.adapters.subsonic import (
    SubsonicAdapter, api_objects as SubsonicAPI)


@pytest.fixture
def subsonic_adapter(tmp_path: Path):
    adapter = SubsonicAdapter(
        {
            'server_address': 'http://localhost:4533',
            'username': 'test',
            'password': 'testpass',
        },
        tmp_path,
    )
    adapter._is_mock = True
    yield adapter


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


def test_request_making_methods(subsonic_adapter: SubsonicAdapter):
    expected = {
        'u': 'test',
        'p': 'testpass',
        'c': 'Sublime Music',
        'f': 'json',
        'v': '1.15.0',
    }
    assert (
        sorted(expected.items()) == sorted(
            subsonic_adapter._get_params().items()))

    assert subsonic_adapter._make_url(
        'foo') == 'http://localhost:4533/rest/foo.view'


def test_can_service_requests(subsonic_adapter: SubsonicAdapter):
    # Mock a connection error
    subsonic_adapter._set_mock_data(Exception())
    assert subsonic_adapter.can_service_requests is False

    # Simulate some sort of ping error
    subsonic_adapter._set_mock_data(
        mock_json(
            status='failed',
            error={
                'code': '1',
                'message': 'Test message',
            },
        ))
    assert subsonic_adapter.can_service_requests is False

    # Simulate valid ping
    subsonic_adapter._set_mock_data(mock_json())
    assert subsonic_adapter.can_service_requests is True


def test_get_playlists(subsonic_adapter: SubsonicAdapter):
    playlists = [
        {
            "id": "6",
            "name": "Playlist 1",
            "comment": "Foo",
            "owner": "test",
            "public": True,
            "songCount": 2,
            "duration": 625,
            "created": "2020-03-27T05:39:35.188Z",
            "changed": "2020-04-08T00:07:01.748Z",
            "coverArt": "pl-6"
        },
        {
            "id": "7",
            "name": "Playlist 2",
            "comment": "",
            "owner": "test",
            "public": True,
            "songCount": 3,
            "duration": 952,
            "created": "2020-03-27T05:39:43.327Z",
            "changed": "2020-03-27T05:44:37.275Z",
            "coverArt": "pl-7"
        },
    ]
    subsonic_adapter._set_mock_data(
        mock_json(playlists={
            'playlist': playlists,
        }))

    expected = [
        SubsonicAPI.Playlist(
            id='6',
            name='Playlist 1',
            song_count=2,
            duration=timedelta(seconds=625),
            created=parser.parse('2020-03-27T05:39:35.188Z'),
            changed=parser.parse('2020-04-08T00:07:01.748Z'),
            comment='Foo',
            owner='test',
            public=True,
            cover_art='pl-6',
        ),
        SubsonicAPI.Playlist(
            id='7',
            name='Playlist 2',
            song_count=3,
            duration=timedelta(seconds=952),
            created=parser.parse('2020-03-27T05:39:43.327Z'),
            changed=parser.parse('2020-03-27T05:44:37.275Z'),
            comment='',
            owner='test',
            public=True,
            cover_art='pl-7',
        ),
    ]
    assert subsonic_adapter.get_playlists() == expected

    # When playlists is null, expect an empty list.
    subsonic_adapter._set_mock_data(mock_json())
    assert subsonic_adapter.get_playlists() == []


def test_get_playlist_details(subsonic_adapter: SubsonicAdapter):
    playlist = {
        "id":
        "6",
        "name":
        "Playlist 1",
        "comment":
        "Foo",
        "owner":
        "test",
        "public":
        True,
        "songCount":
        2,
        "duration":
        952,
        "created":
        "2020-03-27T05:39:43.327Z",
        "changed":
        "2020-03-27T05:44:37.275Z",
        "coverArt":
        "pl-6",
        "entry": [
            {
                "id": "202",
                "parent": "318",
                "isDir": False,
                "title": "What a Beautiful Name",
                "album": "What a Beautiful Name - Single",
                "artist": "Hillsong Worship",
                "track": 1,
                "year": 2016,
                "genre": "Christian & Gospel",
                "coverArt": "318",
                "size": 8381640,
                "contentType": "audio/mp4",
                "suffix": "m4a",
                "transcodedContentType": "audio/mpeg",
                "transcodedSuffix": "mp3",
                "duration": 238,
                "bitRate": 256,
                "path":
                "Hillsong Worship/What a Beautiful Name - Single/01 What a Beautiful Name.m4a",
                "isVideo": False,
                "playCount": 20,
                "discNumber": 1,
                "created": "2020-03-27T05:17:07.000Z",
                "albumId": "48",
                "artistId": "38",
                "type": "music"
            },
            {
                "id": "203",
                "parent": "319",
                "isDir": False,
                "title": "Great Are You Lord",
                "album": "Great Are You Lord EP",
                "artist": "one sonic society",
                "track": 1,
                "year": 2016,
                "genre": "Christian & Gospel",
                "coverArt": "319",
                "size": 8245813,
                "contentType": "audio/mp4",
                "suffix": "m4a",
                "transcodedContentType": "audio/mpeg",
                "transcodedSuffix": "mp3",
                "duration": 232,
                "bitRate": 256,
                "path":
                "one sonic society/Great Are You Lord EP/01 Great Are You Lord.m4a",
                "isVideo": False,
                "playCount": 18,
                "discNumber": 1,
                "created": "2020-03-27T05:32:42.000Z",
                "albumId": "10",
                "artistId": "8",
                "type": "music"
            },
        ],
    }
    subsonic_adapter._set_mock_data(mock_json(playlist=playlist))

    playlist_details = subsonic_adapter.get_playlist_details('6')
    assert len(playlist_details.songs) == 2
