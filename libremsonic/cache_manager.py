import os
import glob
import threading
import shutil
import json
import hashlib

from concurrent.futures import ThreadPoolExecutor, Future
from enum import EnumMeta, Enum
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable, Set

import requests

from libremsonic.config import AppConfiguration, ServerConfiguration
from libremsonic.server import Server
from libremsonic.server.api_object import APIObject
from libremsonic.server.api_objects import (
    Playlist,
    PlaylistWithSongs,
    Child,
    ArtistID3,
    ArtistInfo2,
    ArtistWithAlbumsID3,
    AlbumWithSongsID3,
)


class Singleton(type):
    def __getattr__(cls, name):
        if not CacheManager._instance:
            return None
        # If the cache has a function to do the thing we want, use it. If
        # not, then go directly to the server (this is useful for things
        # that just send data  to the server.)
        if hasattr(CacheManager._instance, name):
            return getattr(CacheManager._instance, name)
        else:
            return getattr(CacheManager._instance.server, name)

        return None


class SongCacheStatus(Enum):
    NOT_CACHED = 0
    CACHED = 1
    PERMANENTLY_CACHED = 2
    DOWNLOADING = 3


class CacheManager(metaclass=Singleton):
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)

    class CacheEncoder(json.JSONEncoder):
        def default(self, obj):
            if type(obj) == datetime:
                return int(obj.timestamp() * 1000)
            elif isinstance(obj, APIObject):
                return {k: v for k, v in obj.__dict__.items() if v is not None}
            elif isinstance(obj, EnumMeta):
                return None

            return json.JSONEncoder.default(self, obj)

    class __CacheManagerInternal:
        # NOTE: you need to add custom load/store logic for everything you add
        # here!
        playlists: Optional[List[Playlist]] = None
        artists: Optional[List[ArtistID3]] = None
        albums: Optional[List[Child]] = None

        playlist_details: Dict[int, PlaylistWithSongs] = {}
        artist_details: Dict[int, ArtistWithAlbumsID3] = {}
        album_details: Dict[int, AlbumWithSongsID3] = {}
        song_details: Dict[int, Child] = {}

        artist_infos: Dict[int, ArtistInfo2] = {}

        permanently_cached_paths: Set[str] = set()

        # The server instance.
        server: Server

        # Thread lock for preventing threads from overriding the state while
        # it's being saved.
        cache_lock = threading.Lock()

        download_set_lock = threading.Lock()
        current_downloads: Set[Path] = set()

        # TODO make this configurable.
        download_limiter_semaphore = threading.Semaphore(5)

        def __init__(
                self,
                app_config: AppConfiguration,
                server_config: ServerConfiguration,
        ):
            self.app_config = app_config
            self.server = Server(
                name=server_config.name,
                hostname=server_config.server_address,
                username=server_config.username,
                password=server_config.password,
            )

            self.load_cache_info()

        def load_cache_info(self):
            cache_meta_file = self.calculate_abs_path('.cache_meta')

            if not cache_meta_file.exists():
                return

            with open(cache_meta_file, 'r') as f:
                try:
                    meta_json = json.load(f)
                except json.decoder.JSONDecodeError:
                    return

            self.playlists = [
                Playlist.from_json(p)
                for p in meta_json.get('playlists') or []
            ]
            self.artists = [
                ArtistID3.from_json(a) for a in meta_json.get('artists') or []
            ]
            self.albums = [
                Child.from_json(a) for a in meta_json.get('albums') or []
            ]
            self.playlist_details = {
                id: PlaylistWithSongs.from_json(v)
                for id, v in (meta_json.get('playlist_details') or {}).items()
            }
            self.artist_details = {
                id: ArtistWithAlbumsID3.from_json(v)
                for id, v in (meta_json.get('artist_details') or {}).items()
            }
            self.album_details = {
                id: AlbumWithSongsID3.from_json(a)
                for id, a in (meta_json.get('album_details') or {}).items()
            }
            self.song_details = {
                id: Child.from_json(v)
                for id, v in (meta_json.get('song_details') or {}).items()
            }
            self.artist_infos = {
                id: ArtistInfo2.from_json(a)
                for id, a in (meta_json.get('artist_infos') or {}).items()
            }
            self.permanently_cached_paths = set(
                meta_json.get('permanently_cached_paths') or [])

        def save_cache_info(self):
            os.makedirs(self.app_config.cache_location, exist_ok=True)

            cache_meta_file = self.calculate_abs_path('.cache_meta')
            with open(cache_meta_file, 'w+') as f, self.cache_lock:
                cache_info = dict(
                    playlists=self.playlists,
                    artists=self.artists,
                    albums=self.albums,
                    playlist_details=self.playlist_details,
                    artist_details=self.artist_details,
                    album_details=self.album_details,
                    song_details=self.song_details,
                    artist_infos=self.artist_infos,
                    permanently_cached_paths=list(
                        self.permanently_cached_paths),
                )
                f.write(
                    json.dumps(cache_info,
                               indent=2,
                               cls=CacheManager.CacheEncoder))

        def save_file(self, absolute_path: Path, data: bytes):
            # Make the necessary directories and write to file.
            os.makedirs(absolute_path.parent, exist_ok=True)
            with open(absolute_path, 'wb+') as f:
                f.write(data)

        def calculate_abs_path(self, *relative_paths):
            return Path(
                self.app_config.cache_location).joinpath(*relative_paths)

        def calculate_download_path(self, *relative_paths):
            xdg_cache_home = (os.environ.get('XDG_CACHE_HOME')
                              or os.path.expanduser('~/.cache'))
            return Path(xdg_cache_home).joinpath('libremsonic',
                                                 *relative_paths)

        def return_cache_or_download(
                self,
                relative_path: Union[Path, str],
                download_fn: Callable[[], bytes],
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ):
            abs_path = self.calculate_abs_path(relative_path)
            download_path = self.calculate_download_path(relative_path)
            if not abs_path.exists() or force:
                print(abs_path, 'not found. Downloading...')

                with self.download_set_lock:
                    self.current_downloads.add(abs_path)

                os.makedirs(download_path.parent, exist_ok=True)
                before_download()
                self.save_file(download_path, download_fn())

                # Move the file to its cache download location.
                os.makedirs(abs_path.parent, exist_ok=True)
                shutil.move(download_path, abs_path)

                with self.download_set_lock:
                    self.current_downloads.discard(abs_path)

            return str(abs_path)

        def delete_cache(self, relative_path: Union[Path, str]):
            """
            :param relative_path: The path to the cached element to delete.
                Note that this can be a globed path.
            """
            abs_path = self.calculate_abs_path(relative_path)
            for path in glob.glob(str(abs_path)):
                Path(path).unlink()

        def get_playlists(
                self,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_playlists() -> List[Playlist]:
                if not self.playlists or force:
                    before_download()
                    playlists = self.server.get_playlists().playlist
                    with self.cache_lock:
                        self.playlists = playlists
                    self.save_cache_info()
                return self.playlists

            return CacheManager.executor.submit(do_get_playlists)

        def get_playlist(
                self,
                playlist_id: int,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_playlist() -> PlaylistWithSongs:
                if not self.playlist_details.get(playlist_id) or force:
                    before_download()
                    playlist = self.server.get_playlist(playlist_id)
                    with self.cache_lock:
                        self.playlist_details[playlist_id] = playlist

                        # Playlists also have the song details, so save those
                        # as well.
                        for song in (playlist.entry or []):
                            self.song_details[song.id] = song

                    self.save_cache_info()

                playlist_details = self.playlist_details[playlist_id]

                # Invalidate the cached photo if we are forcing a retrieval
                # from the server.
                if force:
                    cover_art_filename = f'cover_art/{playlist_details.coverArt}_*'
                    self.delete_cache(cover_art_filename)

                return playlist_details

            return CacheManager.executor.submit(do_get_playlist)

        def get_artists(
                self,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_artists() -> List[ArtistID3]:
                if not self.artists or force:
                    before_download()
                    raw_artists = self.server.get_artists()

                    artists = []
                    for index in raw_artists.index:
                        artists.extend(index.artist)

                    with self.cache_lock:
                        self.artists = artists

                    self.save_cache_info()

                return self.artists

            return CacheManager.executor.submit(do_get_artists)

        def get_artist(
                self,
                artist_id,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_artist() -> ArtistWithAlbumsID3:
                if artist_id not in self.artist_details or force:
                    before_download()
                    artist = self.server.get_artist(artist_id)

                    with self.cache_lock:
                        self.artist_details[artist_id] = artist

                    self.save_cache_info()

                return self.artist_details[artist_id]

            return CacheManager.executor.submit(do_get_artist)

        def get_artist_info2(
                self,
                artist_id,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_artist_info() -> ArtistInfo2:
                if artist_id not in self.artist_infos or force:
                    before_download()
                    artist_info = self.server.get_artist_info2(id=artist_id)

                    with self.cache_lock:
                        self.artist_infos[artist_id] = artist_info

                    self.save_cache_info()

                return self.artist_infos[artist_id]

            return CacheManager.executor.submit(do_get_artist_info)

        def get_artist_artwork(
                self,
                artist: ArtistID3,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_artist_artwork_filename() -> str:
                artist_info = CacheManager.get_artist_info2(artist.id).result()
                lastfm_url = ''.join(artist_info.largeImageUrl)
                if lastfm_url == 'https://lastfm-img2.akamaized.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png':
                    return CacheManager.get_cover_art_filename(
                        artist.coverArt, size=300).result()

                url_hash = hashlib.md5(lastfm_url.encode('utf-8')).hexdigest()
                return self.return_cache_or_download(
                    f'cover_art/artist.{url_hash}',
                    lambda: requests.get(lastfm_url).content,
                    before_download=before_download,
                    force=force,
                )

            return CacheManager.executor.submit(do_get_artist_artwork_filename)

        def get_albums(
                self,
                type_: str,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_albums() -> List[Child]:
                if not self.albums or force:
                    before_download()
                    albums = self.server.get_album_list(type_)

                    with self.cache_lock:
                        self.albums = albums.album

                    self.save_cache_info()

                return self.albums

            return CacheManager.executor.submit(do_get_albums)

        def batch_download_songs(
                self,
                song_ids: List[int],
                before_download: Callable[[], None],
                on_song_download_complete: Callable[[int], None],
        ) -> Future:
            def do_download_song(song_id):
                # Do the actual download.
                song_details_future = CacheManager.get_song_details(song_id)
                song_filename_future = CacheManager.get_song_filename(
                    song_details_future.result(),
                    before_download=before_download,
                )

                def filename_future_done(f):
                    on_song_download_complete(song_id)
                    self.download_limiter_semaphore.release()

                song_filename_future.add_done_callback(filename_future_done)

            def do_batch_download_songs():
                for song_id in song_ids:
                    self.download_limiter_semaphore.acquire()
                    CacheManager.executor.submit(do_download_song, song_id)

            return CacheManager.executor.submit(do_batch_download_songs)

        def get_cover_art_filename(
                self,
                id: str,
                before_download: Callable[[], None] = lambda: None,
                size: Union[str, int] = 200,
                force: bool = False,
        ) -> Future:
            def do_get_cover_art_filename() -> str:
                return self.return_cache_or_download(
                    f'cover_art/{id}_{size}',
                    lambda: self.server.get_cover_art(id, str(size)),
                    before_download=before_download,
                    force=force,
                )

            return CacheManager.executor.submit(do_get_cover_art_filename)

        def get_song_details(
                self,
                song_id: int,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_song_details() -> Child:
                if not self.song_details.get(song_id) or force:
                    before_download()
                    song_details = self.server.get_song(song_id)
                    with self.cache_lock:
                        self.song_details[song_id] = song_details
                    self.save_cache_info()

                return self.song_details[song_id]

            return CacheManager.executor.submit(do_get_song_details)

        def get_song_filename(
                self,
                song: Child,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_song_filename() -> str:
                song_filename = self.return_cache_or_download(
                    song.path,
                    lambda: self.server.do_download(song.id),
                    before_download=before_download,
                    force=force,
                )
                return song_filename

            return CacheManager.executor.submit(do_get_song_filename)

        def get_cached_status(self, song: Child) -> SongCacheStatus:
            cache_path = self.calculate_abs_path(song.path)
            if cache_path.exists():
                if cache_path in self.permanently_cached_paths:
                    return SongCacheStatus.PERMANENTLY_CACHED
                else:
                    return SongCacheStatus.CACHED
            elif cache_path in self.current_downloads:
                return SongCacheStatus.DOWNLOADING
            else:
                return SongCacheStatus.NOT_CACHED

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, app_config, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            app_config, server_config)
