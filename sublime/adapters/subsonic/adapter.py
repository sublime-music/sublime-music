import json
import logging
import multiprocessing
import os
import random
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlencode, urlparse

import requests

from .api_objects import Response
from .. import Adapter, api_objects as API, ConfigParamDescriptor


class SubsonicAdapter(Adapter):
    """
    Defines an adapter which retrieves its data from a Subsonic server
    """

    # Configuration and Initialization Properties
    # ==================================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        # TODO some way to test the connection to the server and a way to open the
        # server URL in a browser
        return {
            "server_address": ConfigParamDescriptor(str, "Server address"),
            "username": ConfigParamDescriptor(str, "Username"),
            "password": ConfigParamDescriptor("password", "Password"),
            "disable_cert_verify": ConfigParamDescriptor("password", "Password", False),
        }

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        errors: Dict[str, Optional[str]] = {}

        # TODO: verify the URL
        return errors

    def __init__(self, config: dict, data_directory: Path):
        self.hostname = config["server_address"]
        self.username = config["username"]
        self.password = config["password"]
        self.disable_cert_verify = config.get("disable_cert_verify")

        self.is_shutting_down = False
        self.ping_process = multiprocessing.Process(target=self._check_ping_thread)
        self.ping_process.start()

        # Wait for the first ping.
        # TODO this is kinda dumb. Should probably fix it somehow.
        while not self._first_ping_happened.value:
            sleep(0.1)

        # TODO support XML | JSON

    def shutdown(self):
        self.ping_process.terminate()

    # Availability Properties
    # ==================================================================================
    _first_ping_happened = multiprocessing.Value("b", False)
    _server_available = multiprocessing.Value("b", False)

    def _check_ping_thread(self):
        # TODO: also use other requests in place of ping if they come in. If the time
        # since the last successful request is high, then do another ping.
        # TODO: also use NM to detect when the connection changes and update
        # accordingly.
        while True:
            self._set_ping_status()
            self._first_ping_happened.value = True
            sleep(15)

    # TODO maybe expose something like this on the API?
    def _set_ping_status(self):
        try:
            # Try to ping the server with a timeout of 2 seconds.
            self._get_json(self._make_url("ping"), timeout=2)
            self._server_available.value = True
        except Exception:
            logging.exception(f"Could not connect to {self.hostname}")
            self._server_available.value = False

    @property
    def can_service_requests(self) -> bool:
        return self._server_available.value

    can_get_playlists = True
    can_get_playlist_details = True
    can_create_playlist = True
    can_update_playlist = True
    can_delete_playlist = True
    can_get_cover_art_uri = True
    can_get_song_uri = True
    can_get_song_details = True
    can_scrobble_song = True
    can_get_genres = True
    supports_streaming = True

    _schemas = None

    @property
    def supported_schemes(self) -> Iterable[str]:
        if not self._schemas:
            self._schemas = (urlparse(self.hostname)[0],)
        return self._schemas

    # Helper mothods for making requests
    # ==================================================================================
    def _get_params(self) -> Dict[str, str]:
        """
        Gets the parameters that are needed for all requests to the Subsonic API. See
        Subsonic API Introduction for details.
        """
        return {
            "u": self.username,
            "p": self.password,
            "c": "Sublime Music",
            "f": "json",
            "v": "1.15.0",
        }

    def _make_url(self, endpoint: str) -> str:
        return f"{self.hostname}/rest/{endpoint}.view"

    # TODO figure out some way of rate limiting requests. They often come in too fast.
    def _get(
        self,
        url: str,
        timeout: Union[float, Tuple[float, float], None] = None,
        # TODO: retry count
        **params,
    ) -> Any:
        params = {**self._get_params(), **params}
        logging.info(f"[START] get: {url}")

        if delay_str := os.environ.get("SUBSONIC_ADAPTER_DEBUG_DELAY"):
            delay = (
                random.uniform(*map(float, delay_str.split(",")))
                if "," in delay_str
                else float(delay_str)
            )

            logging.info(
                "SUBSONIC_ADAPTER_DEBUG_DELAY enabled. Pausing for {delay} seconds"
            )
            sleep(delay)

        # Deal with datetime parameters (convert to milliseconds since 1970)
        for k, v in params.items():
            if isinstance(v, datetime):
                params[k] = int(v.timestamp() * 1000)

        if self._is_mock:
            logging.info("Using mock data")
            return self._get_mock_data()

        result = requests.get(
            url, params=params, verify=not self.disable_cert_verify, timeout=timeout
        )

        # TODO (#122): make better
        if result.status_code != 200:
            raise Exception(f"[FAIL] get: {url} status={result.status_code}")

        logging.info(f"[FINISH] get: {url}")
        return result

    def _get_json(
        self,
        url: str,
        timeout: Union[float, Tuple[float, float], None] = None,
        **params: Union[None, str, datetime, int, Sequence[int], Sequence[str]],
    ) -> Response:
        """
        Make a get request to a *Sonic REST API. Handle all types of errors including
        *Sonic ``<error>`` responses.

        :returns: a dictionary of the subsonic response.
        :raises Exception: needs some work TODO
        """
        result = self._get(url, timeout=timeout, **params)
        subsonic_response = result.json().get("subsonic-response")

        # TODO (#122):  make better
        if not subsonic_response:
            raise Exception(f"[FAIL] get: invalid JSON from {url}")

        if subsonic_response["status"] == "failed":
            code, message = (
                subsonic_response["error"].get("code"),
                subsonic_response["error"].get("message"),
            )
            raise Exception(f"Subsonic API Error #{code}: {message}")

        logging.debug(f"Response from {url}", subsonic_response)
        return Response.from_dict(subsonic_response)

    # Helper Methods for Testing
    _get_mock_data: Any = None
    _is_mock: bool = False

    def _set_mock_data(self, data: Any):
        class MockResult:
            def __init__(self, content: Any):
                self._content = content

            def content(self) -> Any:
                return self._content

            def json(self) -> Any:
                return json.loads(self._content)

        def get_mock_data() -> Any:
            if type(data) == Exception:
                raise data
            if hasattr(data, "__next__"):
                if d := next(data):
                    logging.info("MOCK DATA", d)
                    return MockResult(d)

            logging.info("MOCK DATA", data)
            return MockResult(data)

        self._get_mock_data = get_mock_data

    # Data Retrieval Methods
    # ==================================================================================
    def get_playlists(self) -> Sequence[API.Playlist]:
        if playlists := self._get_json(self._make_url("getPlaylists")).playlists:
            return playlists.playlist
        return []

    def get_playlist_details(self, playlist_id: str) -> API.PlaylistDetails:
        result = self._get_json(self._make_url("getPlaylist"), id=playlist_id).playlist
        # TODO better error
        assert result, f"Error getting playlist {playlist_id}"
        return result

    def create_playlist(
        self, name: str, songs: List[API.Song] = None,
    ) -> Optional[API.PlaylistDetails]:
        return self._get_json(
            self._make_url("createPlaylist"),
            name=name,
            songId=[s.id for s in songs or []],
        ).playlist

    def update_playlist(
        self,
        playlist_id: str,
        name: str = None,
        comment: str = None,
        public: bool = None,
        song_ids: List[str] = None,
        append_song_ids: List[str] = None,
    ) -> API.PlaylistDetails:
        if name is not None or comment is not None or public is not None:
            self._get_json(
                self._make_url("updatePlaylist"),
                playlistId=playlist_id,
                name=name,
                comment=comment,
                public=public,
                songIdToAdd=append_song_ids,
            )

        playlist = None
        if song_ids is not None:
            playlist = self._get_json(
                self._make_url("createPlaylist"),
                playlistId=playlist_id,
                songId=song_ids,
            ).playlist

        # If the call to createPlaylist to update the song IDs returned the playlist,
        # return it.
        return playlist or self.get_playlist_details(playlist_id)

    def delete_playlist(self, playlist_id: str):
        self._get_json(self._make_url("deletePlaylist"), id=playlist_id)

    def get_cover_art_uri(self, cover_art_id: str, scheme: str) -> str:
        params = {"id": cover_art_id, "size": 2000, **self._get_params()}
        return self._make_url("getCoverArt") + "?" + urlencode(params)

    def get_song_uri(self, song_id: str, scheme: str, stream: bool = False) -> str:
        params = {"id": song_id, **self._get_params()}
        endpoint = "stream" if stream else "download"
        return self._make_url(endpoint) + "?" + urlencode(params)

    def get_song_details(self, song_id: str) -> API.Song:
        song = self._get_json(self._make_url("getSong"), id=song_id).song
        assert song, f"Error getting song {song_id}"
        return song

    def scrobble_song(self, song: API.Song):
        self._get(self._make_url("scrobble"), id=song.id)

    def get_genres(self) -> Sequence[API.Genre]:
        if genres := self._get_json(self._make_url("getGenres")).genres:
            return genres.genre
        return []
