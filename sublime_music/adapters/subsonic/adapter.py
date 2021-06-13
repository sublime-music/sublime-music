import hashlib
import json
import logging
import math
import multiprocessing
import os
import pickle
import random
import string
import tempfile
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
import semver
from gi.repository import Gtk

from sublime_music.util import resolve_path

from .api_objects import Directory, Response
from .. import (
    Adapter,
    AlbumSearchQuery,
    api_objects as API,
    ConfigParamDescriptor,
    ConfigurationStore,
    ConfigureServerForm,
    UIInfo,
)

try:
    import gi

    gi.require_version("NM", "1.0")
    from gi.repository import NM

    networkmanager_imported = True
except Exception:
    # I really don't care what kind of exception it is, all that matters is the
    # import failed for some reason.
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


class ServerError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class SubsonicAdapter(Adapter):
    """
    Defines an adapter which retrieves its data from a Subsonic server
    """

    # Configuration and Initialization Properties
    # ==================================================================================
    @staticmethod
    def get_ui_info() -> UIInfo:
        return UIInfo(
            name="Subsonic",
            description="Connect to a Subsonic-compatible server",
            icon_basename="subsonic",
            icon_dir=resolve_path("adapters/subsonic/icons"),
        )

    @staticmethod
    def get_configuration_form(config_store: ConfigurationStore) -> Gtk.Box:
        configs = {
            "server_address": ConfigParamDescriptor(str, "Server Address"),
            "username": ConfigParamDescriptor(str, "Username"),
            "password": ConfigParamDescriptor("password", "Password"),
            "verify_cert": ConfigParamDescriptor(
                bool,
                "Verify Certificate",
                default=True,
                advanced=True,
                helptext="Whether or not to verify the SSL certificate of the server.",
            ),
            "sync_enabled": ConfigParamDescriptor(
                bool,
                "Sync Play Queue",
                default=True,
                advanced=True,
                helptext="If toggled, Sublime Music will periodically save the play "
                "queue state so that you can resume on other devices.",
            ),
            "salt_auth": ConfigParamDescriptor(
                bool,
                "Use Salt Authentication",
                default=True,
                advanced=True,
                helptext="If toggled, Sublime Music will use salted hash tokens "
                "instead of the plain password in the request urls (only supported on "
                "Subsonic API 1.13.0+)",
            ),
        }

        if networkmanager_imported:
            configs.update(
                {
                    "local_network_ssid": ConfigParamDescriptor(
                        str,
                        "Local Network SSID",
                        advanced=True,
                        required=False,
                        helptext="If Sublime Music is connected to the given SSID, the "
                        "Local Network Address will be used instead of the Server "
                        "address when making network requests.",
                    ),
                    "local_network_address": ConfigParamDescriptor(
                        str,
                        "Local Network Address",
                        advanced=True,
                        required=False,
                        helptext="If Sublime Music is connected to the given Local "
                        "Network SSID, this URL will be used instead of the Server "
                        "address when making network requests.",
                    ),
                }
            )

        def verify_configuration() -> Dict[str, Optional[str]]:
            errors: Dict[str, Optional[str]] = {}

            with tempfile.TemporaryDirectory() as tmp_dir_name:
                try:
                    tmp_adapter = SubsonicAdapter(config_store, Path(tmp_dir_name))
                    tmp_adapter._get_json(
                        tmp_adapter._make_url("ping"),
                        timeout=2,
                        is_exponential_backoff_ping=True,
                    )
                except requests.exceptions.SSLError:
                    errors["__ping__"] = (
                        "<b>Error connecting to the server.</b>\n"
                        "An SSL error occurred while connecting to the server.\n"
                        "You may need to explicitly specify http://."
                    )
                except requests.ConnectionError:
                    errors["__ping__"] = (
                        "<b>Unable to connect to the server.</b>\n"
                        "Double check the server address."
                    )
                except ServerError as e:
                    if e.status_code in (10, 41) and config_store["salt_auth"]:
                        # status code 10: if salt auth is not enabled, server will
                        #   return error server error with status_code 10 since it'll
                        #   interpret it as a missing (password) parameter
                        # status code 41: as per subsonic api docs, description of
                        #   status_code 41 is "Token authentication not supported for
                        #   LDAP users." so fall back to password auth
                        try:
                            config_store["salt_auth"] = False
                            tmp_adapter = SubsonicAdapter(
                                config_store, Path(tmp_dir_name)
                            )
                            tmp_adapter._get_json(
                                tmp_adapter._make_url("ping"),
                                timeout=2,
                                is_exponential_backoff_ping=True,
                            )
                            logging.warn(
                                "Salted auth not supported, falling back to regular "
                                "password auth"
                            )
                        except ServerError as retry_e:
                            config_store["salt_auth"] = True
                            errors["__ping__"] = (
                                "<b>Error connecting to the server.</b>\n"
                                f"Error {retry_e.status_code}: {str(retry_e)}"
                            )
                    else:
                        errors["__ping__"] = (
                            "<b>Error connecting to the server.</b>\n"
                            f"Error {e.status_code}: {str(e)}"
                        )
                except Exception as e:
                    errors["__ping__"] = str(e)

            return errors

        return ConfigureServerForm(config_store, configs, verify_configuration)

    @staticmethod
    def migrate_configuration(config_store: ConfigurationStore):
        if "salt_auth" not in config_store:
            config_store["salt_auth"] = True

    def __init__(self, config: ConfigurationStore, data_directory: Path):
        self.data_directory = data_directory
        self.ignored_articles_cache_file = self.data_directory.joinpath(
            "ignored_articles.pickle"
        )

        self.hostname = config["server_address"]
        if (
            (ssid := config.get("local_network_ssid"))
            and (lan_address := config.get("local_network_address"))
            and networkmanager_imported
        ):
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
                    self.hostname = lan_address
                    break

        parsed_hostname = urlparse(self.hostname)
        if not parsed_hostname.scheme:
            self.hostname = "https://" + self.hostname

        self.username = config["username"]
        self.password = cast(str, config.get_secret("password"))
        self.verify_cert = config["verify_cert"]
        self.use_salt_auth = config["salt_auth"]

        self.is_shutting_down = False
        self._ping_process: Optional[multiprocessing.Process] = None
        self._version = multiprocessing.Array("c", 20)
        self._offline_mode = False

        # TODO (#112): support XML?

    def initial_sync(self):
        # Try to ping the server five times using exponential backoff (2^5 = 32s).
        self._exponential_backoff(5)

    def shutdown(self):
        if self._ping_process:
            self._ping_process.terminate()

    # Availability Properties
    # ==================================================================================
    _server_available = multiprocessing.Value("b", False)
    _last_ping_timestamp = multiprocessing.Value("d", 0.0)

    def _exponential_backoff(self, n: int):
        logging.info(f"Starting Exponential Backoff: n={n}")
        if self._ping_process:
            self._ping_process.terminate()

        self._ping_process = multiprocessing.Process(
            target=self._check_ping_thread, args=(n,)
        )
        self._ping_process.start()

    def _check_ping_thread(self, n: int):
        i = 0
        while i < n and not self._offline_mode and not self._server_available.value:
            try:
                self._set_ping_status(timeout=2 * (i + 1))
            except Exception:
                pass
            sleep(2 ** i)
            i += 1

    def _set_ping_status(self, timeout: int = 2):
        logging.info(f"SET PING STATUS timeout={timeout}")
        now = datetime.now().timestamp()
        if now - self._last_ping_timestamp.value < 15:
            return

        # Try to ping the server.
        self._get_json(
            self._make_url("ping"),
            timeout=timeout,
            is_exponential_backoff_ping=True,
        )

    def on_offline_mode_change(self, offline_mode: bool):
        self._offline_mode = offline_mode

    @property
    def ping_status(self) -> bool:
        return self._server_available.value

    can_create_playlist = True
    can_delete_playlist = True
    can_get_album = True
    can_get_albums = True
    can_get_artist = True
    can_get_artists = True
    can_get_cover_art_uri = True
    can_get_directory = True
    can_get_ignored_articles = True
    can_get_playlist_details = True
    can_get_playlists = True
    can_get_song_details = True
    can_get_song_file_uri = True
    can_get_song_stream_uri = True
    can_scrobble_song = True
    can_search = True
    can_stream = True
    can_update_playlist = True

    def version_at_least(self, version: str) -> bool:
        if not self._version.value:
            return False
        return semver.VersionInfo.parse(self._version.value.decode()) >= version

    @property
    def can_get_genres(self) -> bool:
        return self.version_at_least("1.9.0")

    @property
    def can_get_play_queue(self) -> bool:
        return self.version_at_least("1.12.0")

    @property
    def can_save_play_queue(self) -> bool:
        return self.version_at_least("1.12.0")

    _schemes = None

    @property
    def supported_schemes(self) -> Iterable[str]:
        if not self._schemes:
            self._schemes = (urlparse(self.hostname)[0],)
        return self._schemes

    @property
    def supported_artist_query_types(self) -> Set[AlbumSearchQuery.Type]:
        supported = {
            AlbumSearchQuery.Type.RANDOM,
            AlbumSearchQuery.Type.NEWEST,
            AlbumSearchQuery.Type.FREQUENT,
            AlbumSearchQuery.Type.RECENT,
            AlbumSearchQuery.Type.STARRED,
            AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME,
            AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST,
        }
        if self.version_at_least("1.10.1"):
            supported.add(AlbumSearchQuery.Type.YEAR_RANGE)
            supported.add(AlbumSearchQuery.Type.GENRE)

        return supported

    # Helper mothods for making requests
    # ==================================================================================
    def _get_params(self) -> Dict[str, str]:
        """
        Gets the parameters that are needed for all requests to the Subsonic API. See
        Subsonic API Introduction for details.
        """
        params = {
            "u": self.username,
            "c": "Sublime Music",
            "f": "json",
            "v": self._version.value.decode() or "1.8.0",
        }

        if self.use_salt_auth:
            salt, token = self._generate_auth_token()
            params["s"] = salt
            params["t"] = token
        else:
            params["p"] = self.password

        return params

    def _generate_auth_token(self) -> Tuple[str, str]:
        """
        Generates the necessary authentication data to call the Subsonic API See the
        Authentication section of www.subsonic.org/pages/api.jsp for more information
        """
        salt = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
        return (salt, token)

    def _make_url(self, endpoint: str) -> str:
        return f"{self.hostname}/rest/{endpoint}.view"

    # TODO (#196) figure out some way of rate limiting requests. They often come in too
    # fast.
    def _get(
        self,
        url: str,
        timeout: Union[float, Tuple[float, float], None] = None,
        is_exponential_backoff_ping: bool = False,
        **params,
    ) -> Any:
        params = {**self._get_params(), **params}
        logging.info(f"[START] get: {url}")

        try:
            if REQUEST_DELAY is not None:
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
                raise ServerError(69, "NETWORK_ALWAYS_ERROR enabled")

            # Deal with datetime parameters (convert to milliseconds since 1970)
            for k, v in params.items():
                if isinstance(v, datetime):
                    params[k] = int(v.timestamp() * 1000)

            if self._is_mock:
                logging.info("Using mock data")
                result = self._get_mock_data()
            else:
                if url.startswith("http://") or url.startswith("https://"):
                    result = requests.get(
                        url,
                        params=params,
                        verify=self.verify_cert,
                        timeout=timeout,
                    )
                else:
                    # if user creates a serverconf address w/o protocol, we'll
                    # attempt to fix it and store it in hostname
                    # TODO (#305) #hostname currently preprends https:// if
                    # protocol isn't defined this might be able to be taken out
                    try:
                        logging.info("Hostname: %r has no protocol", self.hostname)
                        result = requests.get(
                            "https://" + url,
                            params=params,
                            verify=self.verify_cert,
                            timeout=timeout,
                        )
                        self.hostname = "https://" + url.split("/")[0]
                    except Exception:
                        result = requests.get(
                            "http://" + url,
                            params=params,
                            verify=self.verify_cert,
                            timeout=timeout,
                        )

                        self.hostname = "http://" + url.split("/")[0]

            if result.status_code != 200:
                raise ServerError(
                    result.status_code, f"{url} returned status={result.status_code}."
                )
            # Any time that a server request succeeds, then we win.
            self._server_available.value = True
            self._last_ping_timestamp.value = datetime.now().timestamp()

        except Exception:
            logging.exception(f"[FAIL] get: {url} failed")
            self._server_available.value = False
            self._last_ping_timestamp.value = datetime.now().timestamp()
            if not is_exponential_backoff_ping:
                self._exponential_backoff(5)
            raise

        logging.info(f"[FINISH] get: {url}")
        return result

    def _get_json(
        self,
        url: str,
        timeout: Union[float, Tuple[float, float], None] = None,
        is_exponential_backoff_ping: bool = False,
        **params: Union[None, str, datetime, int, Sequence[int], Sequence[str]],
    ) -> Response:
        """
        Make a get request to a *Sonic REST API. Handle all types of errors including
        *Sonic ``<error>`` responses.

        :returns: a dictionary of the subsonic response.
        :raises Exception: needs some work
        """
        result = self._get(
            url,
            timeout=timeout,
            is_exponential_backoff_ping=is_exponential_backoff_ping,
            **params,
        )
        subsonic_response = result.json().get("subsonic-response")

        if not subsonic_response:
            raise ServerError(500, f"{url} returned invalid JSON.")

        if subsonic_response["status"] != "ok":
            raise ServerError(
                subsonic_response["error"].get("code"),
                subsonic_response["error"].get("message"),
            )

        self._version.value = subsonic_response["version"].encode()

        logging.debug(f"Response from {url}: {subsonic_response}")
        return Response.from_dict(subsonic_response)

    # Helper Methods for Testing
    _get_mock_data: Any = None
    _is_mock: bool = False

    def _set_mock_data(self, data: Any):
        class MockResult:
            status_code = 200

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
                    logging.info("MOCK DATA: %s", d)
                    return MockResult(d)

            logging.info("MOCK DATA: %s", data)
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
        assert result, f"Error getting playlist {playlist_id}"
        return result

    def create_playlist(
        self, name: str, songs: Sequence[API.Song] = None
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

    def get_cover_art_uri(self, cover_art: str, scheme: str, size: int) -> str:
        # Some servers return a full URL instead of an ID
        if cover_art.startswith("http://") or cover_art.startswith("https://"):
            return cover_art

        params = {"id": cover_art, "size": size, **self._get_params()}
        return self._make_url("getCoverArt") + "?" + urlencode(params)

    def get_song_file_uri(self, song_id: str, schemes: Iterable[str]) -> str:
        assert any(s in schemes for s in self.supported_schemes)
        params = {"id": song_id, **self._get_params()}
        return self._make_url("download") + "?" + urlencode(params)

    def get_song_stream_uri(self, song_id: str) -> str:
        params = {"id": song_id, **self._get_params()}
        return self._make_url("stream") + "?" + urlencode(params)

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
        if self.version_at_least("1.11.0"):
            try:
                artist_info = self._get_json(
                    self._make_url("getArtistInfo2"), id=artist_id
                )
                artist.augment_with_artist_info(artist_info.artist_info)
            except Exception:
                pass
        return artist

    def get_ignored_articles(self) -> Set[str]:
        ignored_articles = "The El La Los Las Le Les"
        try:
            # If we already got the ignored articles from the get_artists, do that here.
            with open(self.ignored_articles_cache_file, "rb+") as f:
                if ia := pickle.load(f):
                    ignored_articles = ia
        except Exception:
            try:
                # Whatever the exception, fall back on getting from the server.
                if artists := self._get_json(self._make_url("getArtists")).artists:
                    if ia := artists.ignored_articles:
                        ignored_articles = ia
            except Exception:
                # Use the default ignored articles.
                pass

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
        song_ids: Sequence[str],
        current_song_index: int = None,
        position: timedelta = None,
    ):
        # TODO (sonic-extensions-api/specification#1) make an extension that allows you
        # to save the play queue position by index instead of id.
        self._get(
            self._make_url("savePlayQueue"),
            id=song_ids,
            timeout=2,
            current=song_ids[current_song_index]
            if current_song_index is not None
            else None,
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
