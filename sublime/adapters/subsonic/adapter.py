import json
import logging
import math
import multiprocessing
import os
import pickle
import random
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import (
    Any,
    cast,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from urllib.parse import urlencode, urlparse

import requests

from .api_objects import Directory, Response
from .. import Adapter, AlbumSearchQuery, api_objects as API, ConfigParamDescriptor

try:
    import gi

    gi.require_version("NM", "1.0")
    from gi.repository import NM

    networkmanager_imported = True
except Exception:
    # I really don't care what kind of exception it is, all that matters is the
    # import failed for some reason.
    logging.warning(
        "Unable to import NM from GLib. Detection of SSID will be disabled."
    )
    networkmanager_imported = False

REQUEST_DELAY: Optional[Tuple[float, float]] = None
if delay_str := os.environ.get("REQUEST_DELAY"):
    if "," in delay_str:
        high, low = map(float, delay_str.split(","))
        REQUEST_DELAY = (high, low)
    else:
        REQUEST_DELAY = (float(delay_str), float(delay_str))

NETWORK_ALWAYS_ERROR: bool = False
if always_error := os.environ.get("NETWORK_ALWAYS_ERROR"):
    NETWORK_ALWAYS_ERROR = True


class SubsonicAdapter(Adapter):
    """
    Defines an adapter which retrieves its data from a Subsonic server
    """

    # Configuration and Initialization Properties
    # ==================================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        # TODO (#197) some way to test the connection to the server and a way to open
        # the server URL in a browser
        configs = {
            "server_address": ConfigParamDescriptor(str, "Server address"),
            "disable_cert_verify": ConfigParamDescriptor("password", "Password", False),
            "username": ConfigParamDescriptor(str, "Username"),
            "password": ConfigParamDescriptor("password", "Password"),
        }
        if networkmanager_imported:
            configs.update(
                {
                    "local_network_ssid": ConfigParamDescriptor(
                        str, "Local Network SSID"
                    ),
                    "local_network_address": ConfigParamDescriptor(
                        str, "Local Network Address"
                    ),
                }
            )
        return configs

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        errors: Dict[str, Optional[str]] = {}

        # TODO (#197): verify the URL and ping it.
        # Maybe have a special key like __ping_future__ or something along those lines
        # to add a function that allows the UI to check whether or not connecting to the
        # server will work?
        return errors

    def __init__(self, config: dict, data_directory: Path):
        self.data_directory = data_directory
        self.ignored_articles_cache_file = self.data_directory.joinpath(
            "ignored_articles.pickle"
        )

        self.hostname = config["server_address"]
        if ssid := config.get("local_network_ssid") and networkmanager_imported:
            networkmanager_client = NM.Client.new()

            # Only look at the active WiFi connections.
            for ac in networkmanager_client.get_active_connections():
                if ac.get_connection_type() != "802-11-wireless":
                    continue
                devs = ac.get_devices()
                if len(devs) != 1:
                    continue
                if devs[0].get_device_type() != NM.DeviceType.WIFI:
                    continue

                # If connected to the Local Network SSID, then change the hostname to
                # the Local Network Address.
                if ssid == ac.get_id():
                    self.hostname = config["local_network_address"]
                    break

        self.username = config["username"]
        self.password = config["password"]
        self.disable_cert_verify = config.get("disable_cert_verify")

        self.is_shutting_down = False
        self.ping_process = multiprocessing.Process(target=self._check_ping_thread)
        self.ping_process.start()

        # TODO (#112): support XML?

    def initial_sync(self):
        # Wait for the ping to happen.
        tries = 0
        while not self._server_available.value and tries < 5:
            self._set_ping_status()
            tries += 1

    def shutdown(self):
        self.ping_process.terminate()

    # Availability Properties
    # ==================================================================================
    _server_available = multiprocessing.Value("b", False)

    def _check_ping_thread(self):
        # TODO (#198): also use other requests in place of ping if they come in. If the
        # time since the last successful request is high, then do another ping.
        # TODO (#198): also use NM to detect when the connection changes and update
        # accordingly.

        while True:
            self._set_ping_status()
            sleep(15)

    def _set_ping_status(self):
        # TODO don't ping in offline mode
        try:
            # Try to ping the server with a timeout of 2 seconds.
            self._get_json(self._make_url("ping"), timeout=2)
            self._server_available.value = True
        except Exception:
            logging.exception(f"Could not connect to {self.hostname}")
            self._server_available.value = False

    @property
    def ping_status(self) -> bool:
        return self._server_available.value

    @property
    def can_service_requests(self) -> bool:
        return self._server_available.value

    # TODO (#199) make these way smarter
    can_get_playlists = True
    can_get_playlist_details = True
    can_create_playlist = True
    can_update_playlist = True
    can_delete_playlist = True
    can_get_cover_art_uri = True
    can_get_song_uri = True
    can_stream = True
    can_get_song_details = True
    can_scrobble_song = True
    can_get_artists = True
    can_get_artist = True
    can_get_ignored_articles = True
    can_get_albums = True
    can_get_album = True
    can_get_directory = True
    can_get_genres = True
    can_get_play_queue = True
    can_save_play_queue = True
    can_search = True

    _schemes = None

    @property
    def supported_schemes(self) -> Iterable[str]:
        if not self._schemes:
            self._schemes = (urlparse(self.hostname)[0],)
        return self._schemes

    # TODO (#203) make this way smarter
    supported_artist_query_types = {
        AlbumSearchQuery.Type.RANDOM,
        AlbumSearchQuery.Type.NEWEST,
        AlbumSearchQuery.Type.FREQUENT,
        AlbumSearchQuery.Type.RECENT,
        AlbumSearchQuery.Type.STARRED,
        AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME,
        AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST,
        AlbumSearchQuery.Type.YEAR_RANGE,
        AlbumSearchQuery.Type.GENRE,
    }

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

    # TODO (#196) figure out some way of rate limiting requests. They often come in too
    # fast.
    def _get(
        self,
        url: str,
        timeout: Union[float, Tuple[float, float], None] = None,
        # TODO (#122): retry count
        **params,
    ) -> Any:
        params = {**self._get_params(), **params}
        logging.info(f"[START] get: {url}")

        if REQUEST_DELAY:
            delay = random.uniform(*REQUEST_DELAY)
            logging.info(f"REQUEST_DELAY enabled. Pausing for {delay} seconds")
            sleep(delay)
            if timeout:
                if type(timeout) == tuple:
                    if delay > cast(Tuple[float, float], timeout)[0]:
                        raise TimeoutError("DUMMY TIMEOUT ERROR")
                else:
                    if delay > cast(float, timeout):
                        raise TimeoutError("DUMMY TIMEOUT ERROR")

        if NETWORK_ALWAYS_ERROR:
            raise Exception("NETWORK_ALWAYS_ERROR enabled")

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
        :raises Exception: needs some work
        """
        result = self._get(url, timeout=timeout, **params)
        subsonic_response = result.json().get("subsonic-response")

        # TODO (#122): make better
        if not subsonic_response:
            raise Exception(f"[FAIL] get: invalid JSON from {url}")

        if subsonic_response["status"] == "failed":
            code, message = (
                subsonic_response["error"].get("code"),
                subsonic_response["error"].get("message"),
            )
            raise Exception(f"Subsonic API Error #{code}: {message}")

        logging.debug(f"Response from {url}: {subsonic_response}")
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
            return sorted(playlists.playlist, key=lambda p: p.name.lower())
        return []

    def get_playlist_details(self, playlist_id: str) -> API.Playlist:
        result = self._get_json(self._make_url("getPlaylist"), id=playlist_id).playlist
        # TODO (#122) better error (here and elsewhere)
        assert result, f"Error getting playlist {playlist_id}"
        return result

    def create_playlist(
        self, name: str, songs: Sequence[API.Song] = None,
    ) -> Optional[API.Playlist]:
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
        song_ids: Sequence[str] = None,
        append_song_ids: Sequence[str] = None,
    ) -> API.Playlist:
        if any(x is not None for x in (name, comment, public, append_song_ids)):
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

    def get_cover_art_uri(self, cover_art_id: str, scheme: str, size: int) -> str:
        params = {"id": cover_art_id, "size": size, **self._get_params()}
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

    def get_artists(self) -> Sequence[API.Artist]:
        if artist_index := self._get_json(self._make_url("getArtists")).artists:
            with open(self.ignored_articles_cache_file, "wb+") as f:
                pickle.dump(artist_index.ignored_articles, f)

            artists = []
            for index in artist_index.index:
                artists.extend(index.artist)
            return cast(Sequence[API.Artist], artists)
        return []

    def get_artist(self, artist_id: str) -> API.Artist:
        artist = self._get_json(self._make_url("getArtist"), id=artist_id).artist
        assert artist, f"Error getting artist {artist_id}"
        artist.augment_with_artist_info(
            self._get_json(self._make_url("getArtistInfo2"), id=artist_id).artist_info
        )
        return artist

    def get_ignored_articles(self) -> Set[str]:
        ignored_articles = ""
        try:
            # If we already got the ignored articles from the get_artists, do that here.
            with open(self.ignored_articles_cache_file, "rb+") as f:
                ignored_articles = pickle.load(f)
        except Exception:
            # Whatever the exception, fall back on getting from the server.
            if artists := self._get_json(self._make_url("getArtists")).artists:
                ignored_articles = artists.ignored_articles

        return set(ignored_articles.split())

    def get_albums(
        self, query: AlbumSearchQuery, sort_direction: str = "ascending"
    ) -> Sequence[API.Album]:
        type_ = {
            AlbumSearchQuery.Type.RANDOM: "random",
            AlbumSearchQuery.Type.NEWEST: "newest",
            AlbumSearchQuery.Type.FREQUENT: "frequent",
            AlbumSearchQuery.Type.RECENT: "recent",
            AlbumSearchQuery.Type.STARRED: "starred",
            AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME: "alphabeticalByName",
            AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST: "alphabeticalByArtist",
            AlbumSearchQuery.Type.YEAR_RANGE: "byYear",
            AlbumSearchQuery.Type.GENRE: "byGenre",
        }[query.type]

        extra_args: Dict[str, Any] = {}
        if query.type == AlbumSearchQuery.Type.YEAR_RANGE:
            assert (year_range := query.year_range)
            extra_args = {
                "fromYear": year_range[0],
                "toYear": year_range[1],
            }
        elif query.type == AlbumSearchQuery.Type.GENRE:
            assert (genre := query.genre)
            extra_args = {"genre": genre.name}

        albums: List[API.Album] = []
        page_size = 50 if query.type == AlbumSearchQuery.Type.RANDOM else 500
        offset = 0

        def get_page(offset: int) -> Sequence[API.Album]:
            album_list = self._get_json(
                self._make_url("getAlbumList2"),
                type=type_,
                size=page_size,
                offset=offset,
                **extra_args,
            ).albums
            return album_list.album if album_list else []

        # Get all pages.
        while len(next_page := get_page(offset)) > 0:
            albums.extend(next_page)
            if query.type == AlbumSearchQuery.Type.RANDOM:
                break
            offset += page_size

        return albums

    def get_album(self, album_id: str) -> API.Album:
        album = self._get_json(self._make_url("getAlbum"), id=album_id).album
        assert album, f"Error getting album {album_id}"
        return album

    def _get_indexes(self) -> API.Directory:
        indexes = self._get_json(self._make_url("getIndexes")).indexes
        assert indexes, "Error getting indexes"
        with open(self.ignored_articles_cache_file, "wb+") as f:
            pickle.dump(indexes.ignored_articles, f)

        root_dir_items: List[Dict[str, Any]] = []
        for index in indexes.index:
            root_dir_items.extend(map(lambda x: {**x, "isDir": True}, index.artist))
        return Directory(id="root", _children=root_dir_items)

    def get_directory(self, directory_id: str) -> API.Directory:
        if directory_id == "root":
            return self._get_indexes()

        # TODO (#187) make sure to filter out all non-song files
        directory = self._get_json(
            self._make_url("getMusicDirectory"), id=directory_id
        ).directory
        assert directory, f"Error getting directory {directory_id}"
        return directory

    def get_genres(self) -> Sequence[API.Genre]:
        if genres := self._get_json(self._make_url("getGenres")).genres:
            return genres.genre
        return []

    def get_play_queue(self) -> Optional[API.PlayQueue]:
        return self._get_json(self._make_url("getPlayQueue")).play_queue

    def save_play_queue(
        self,
        song_ids: Sequence[int],
        current_song_index: int = None,
        position: timedelta = None,
    ):
        # TODO (sonic-extensions-api/specification#1) make an extension that allows you
        # to save the play queue position by index instead of id.
        self._get(
            self._make_url("savePlayQueue"),
            id=song_ids,
            current=song_ids[current_song_index] if current_song_index else None,
            position=math.floor(position.total_seconds() * 1000) if position else None,
        )

    def search(self, query: str) -> API.SearchResult:
        result = self._get_json(self._make_url("search3"), query=query).search_result
        if not result:
            return API.SearchResult(query)

        search_result = API.SearchResult(query)
        search_result.add_results("albums", result.album)
        search_result.add_results("artists", result.artist)
        search_result.add_results("songs", result.song)
        return search_result
