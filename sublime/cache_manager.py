import os
import glob
import threading
import shutil
import json
import hashlib
from collections import defaultdict
from time import sleep

from concurrent.futures import ThreadPoolExecutor, Future
from enum import EnumMeta, Enum
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Union,
    Callable,
    Set,
    DefaultDict,
    Tuple,
    TypeVar,
)

import requests

from .config import AppConfiguration, ServerConfiguration
from .server import Server
from .server.api_object import APIObject
from .server.api_objects import (
    Playlist,
    PlaylistWithSongs,
    Child,
    Genre,

    # Non-ID3 versions
    Artist,
    ArtistInfo,
    Directory,

    # ID3 versions
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


T = TypeVar('T')


class CacheManager(metaclass=Singleton):
    executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=50)
    should_exit: bool = False

    class Result(Generic[T]):
        """A result from a CacheManager function."""
        data = None
        future = None

        @staticmethod
        def from_data(data: T) -> 'CacheManager.Result[T]':
            result: 'CacheManager.Result[T]' = CacheManager.Result()
            result.data = data
            return result

        @staticmethod
        def from_server(
                download_fn,
                before_download=None,
                after_download=None,
        ) -> 'CacheManager.Result[T]':
            result: 'CacheManager.Result[T]' = CacheManager.Result()

            def future_fn() -> T:
                if before_download:
                    before_download()
                return download_fn()

            result.future = CacheManager.executor.submit(future_fn)

            if after_download:
                result.future.add_done_callback(
                    lambda f: after_download(f.result()))

            return result

        def result(self) -> T:
            if self.data is not None:
                return self.data
            if self.future is not None:
                return self.future.result()

            raise Exception(
                'CacheManager.Result did not have either a data or future '
                'member.')

        def add_done_callback(self, fn, *args):
            if self.is_future:
                self.future.add_done_callback(fn, *args)
            else:
                # Run the function immediately if it's not a future.
                fn(self, *args)

        @property
        def is_future(self) -> bool:
            return self.future is not None

    @staticmethod
    def ready():
        return CacheManager._instance is not None

    @staticmethod
    def shutdown():
        CacheManager.should_exit = True
        print('Shutdown start')
        CacheManager.executor.shutdown()
        print('Shutdown complete')

    @staticmethod
    def calculate_server_hash(server: ServerConfiguration):
        if server is None:
            return None
        server_info = (server.name + server.server_address + server.username)
        return hashlib.md5(server_info.encode('utf-8')).hexdigest()[:8]

    class CacheEncoder(json.JSONEncoder):
        def default(self, obj):
            if type(obj) == datetime:
                return int(obj.timestamp() * 1000)
            elif type(obj) == set:
                return list(obj)
            elif isinstance(obj, APIObject):
                return {k: v for k, v in obj.__dict__.items() if v is not None}
            elif isinstance(obj, EnumMeta):
                return None

            return json.JSONEncoder.default(self, obj)

    class __CacheManagerInternal:
        # Thread lock for preventing threads from overriding the state while
        # it's being saved.
        cache_lock = threading.Lock()

        cache: DefaultDict[str, Any] = defaultdict(dict)
        permanently_cached_paths: Set[str] = set()

        # The server instance.
        server: Server
        browse_by_tags: bool

        # TODO need to split out the song downloads and make them higher
        # priority I think. Maybe even need to just make this a priority queue.
        download_set_lock = threading.Lock()
        current_downloads: Set[Path] = set()

        def __init__(
                self,
                app_config: AppConfiguration,
                server_config: ServerConfiguration,
        ):
            self.app_config = app_config
            self.browse_by_tags = self.app_config.server.browse_by_tags
            self.server_config = server_config
            self.server = Server(
                name=server_config.name,
                hostname=server_config.server_address,
                username=server_config.username,
                password=server_config.password,
                disable_cert_verify=server_config.disable_cert_verify,
            )
            self.download_limiter_semaphore = threading.Semaphore(
                self.app_config.concurrent_download_limit)

            self.load_cache_info()

        def load_cache_info(self):
            cache_meta_file = self.calculate_abs_path('.cache_meta')

            meta_json = {}
            if cache_meta_file.exists():
                with open(cache_meta_file, 'r') as f:
                    try:
                        meta_json = json.load(f)
                    except json.decoder.JSONDecodeError:
                        return

            cache_configs = [
                # Playlists
                ('playlists', Playlist, list),
                ('playlist_details', PlaylistWithSongs, dict),
                ('song_details', Child, dict),
                ('genres', Genre, list),

                # Non-ID3 caches
                ('albums', Child, 'dict-list'),
                ('album_details', Directory, dict),
                ('artists', Artist, list),
                ('artist_details', Directory, dict),
                ('artist_infos', ArtistInfo, dict),

                # ID3 caches
                ('albums_id3', AlbumWithSongsID3, 'dict-list'),
                ('album_details_id3', AlbumWithSongsID3, dict),
                ('artists_id3', ArtistID3, list),
                ('artist_details_id3', ArtistWithAlbumsID3, dict),
                ('artist_infos_id3', ArtistInfo2, dict),
            ]
            for name, type_name, default in cache_configs:
                if default == list:
                    self.cache[name] = [
                        type_name.from_json(x)
                        for x in meta_json.get(name, [])
                    ]
                elif default == dict:
                    self.cache[name] = {
                        id: type_name.from_json(x)
                        for id, x in meta_json.get(name, {}).items()
                    }
                elif default == 'dict-list':
                    self.cache[name] = {
                        n: [type_name.from_json(x) for x in xs]
                        for n, xs in meta_json.get(name, {}).items()
                    }

        def save_cache_info(self):
            os.makedirs(self.app_config.cache_location, exist_ok=True)

            cache_meta_file = self.calculate_abs_path('.cache_meta')
            os.makedirs(os.path.dirname(cache_meta_file), exist_ok=True)
            with open(cache_meta_file, 'w+') as f, self.cache_lock:
                f.write(
                    json.dumps(
                        self.cache, indent=2, cls=CacheManager.CacheEncoder))

        def save_file(self, absolute_path: Path, data: bytes):
            # Make the necessary directories and write to file.
            os.makedirs(absolute_path.parent, exist_ok=True)
            with open(absolute_path, 'wb+') as f:
                f.write(data)

        def calculate_abs_path(self, *relative_paths):
            return Path(self.app_config.cache_location).joinpath(
                CacheManager.calculate_server_hash(self.server_config),
                *relative_paths,
            )

        def calculate_download_path(self, *relative_paths):
            """
            Determine where to temporarily put the file as it is downloading.
            """
            xdg_cache_home = (
                os.environ.get('XDG_CACHE_HOME')
                or os.path.expanduser('~/.cache'))
            return Path(xdg_cache_home).joinpath(
                'sublime-music',
                CacheManager.calculate_server_hash(self.server_config),
                *relative_paths,
            )

        def return_cached_or_download(
                self,
                relative_path: Union[Path, str],
                download_fn: Callable[[], bytes],
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
                allow_download: bool = True,
        ) -> 'CacheManager.Result[Optional[str]]':
            abs_path = self.calculate_abs_path(relative_path)
            abs_path_str = str(abs_path)
            download_path = self.calculate_download_path(relative_path)

            if abs_path.exists() and not force:
                return CacheManager.Result.from_data(abs_path_str)

            if not allow_download:
                return CacheManager.Result.from_data(None)

            def do_download() -> str:
                # TODO
                resource_downloading = False
                with self.download_set_lock:
                    if abs_path_str in self.current_downloads:
                        resource_downloading = True

                    self.current_downloads.add(abs_path_str)

                if resource_downloading:
                    print(abs_path, 'already being downloaded.')
                    # The resource is already being downloaded. Busy loop until
                    # it has completed. Then, just return the path to the
                    # resource.
                    # TODO: figure out a way to determine if the download we
                    # are waiting on failed.
                    while abs_path_str in self.current_downloads:
                        sleep(0.5)
                else:
                    print(abs_path, 'not found. Downloading...')

                    os.makedirs(download_path.parent, exist_ok=True)
                    self.save_file(download_path, download_fn())

                    # Move the file to its cache download location.
                    os.makedirs(abs_path.parent, exist_ok=True)
                    if download_path.exists():
                        shutil.move(download_path, abs_path)

                print(abs_path, 'downloaded. Returning.')
                return abs_path_str

            def after_download(path):
                with self.download_set_lock:
                    self.current_downloads.discard(path)

            return CacheManager.Result.from_server(
                do_download,
                before_download=before_download,
                after_download=after_download,
            )

        @staticmethod
        def create_future(fn, *args):
            """
            Creates a future on the CacheManager's executor.
            """
            return CacheManager.executor.submit(fn, *args)

        def delete_cached_cover_art(self, id: int):
            relative_path = f'cover_art/*{id}_*'

            abs_path = self.calculate_abs_path(relative_path)

            for path in glob.glob(str(abs_path)):
                Path(path).unlink()

        def get_playlists(
                self,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[List[Playlist]]':
            if self.cache.get('playlists') and not force:
                return CacheManager.Result.from_data(self.cache['playlists'])

            def after_download(playlists):
                with self.cache_lock:
                    self.cache['playlists'] = playlists
                self.save_cache_info()

            return CacheManager.Result.from_server(
                lambda: self.server.get_playlists().playlist,
                before_download=before_download,
                after_download=after_download,
            )

        def invalidate_playlists_cache(self):
            if not self.cache.get('playlists'):
                return

            with self.cache_lock:
                self.cache['playlists'] = []
            self.save_cache_info()

        def get_playlist(
                self,
                playlist_id: int,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[PlaylistWithSongs]':
            playlist_details = self.cache.get('playlist_details', {})
            if playlist_id in playlist_details and not force:
                return CacheManager.Result.from_data(
                    playlist_details[playlist_id])

            def after_download(playlist):
                with self.cache_lock:
                    self.cache['playlist_details'][playlist_id] = playlist

                    # Playlists have the song details, so save those too.
                    for song in (playlist.entry or []):
                        self.cache['song_details'][song.id] = song

                self.save_cache_info()

            # Invalidate the cached photo if we are forcing a retrieval
            # from the server.
            if force:
                self.delete_cached_cover_art(playlist_id)

            return CacheManager.Result.from_server(
                lambda: self.server.get_playlist(playlist_id),
                before_download=before_download,
                after_download=after_download,
            )

        def create_playlist(self, name: str) -> Future:
            def do_create_playlist():
                self.server.create_playlist(name=name)

            return CacheManager.create_future(do_create_playlist)

        def update_playlist(self, playlist_id, *args, **kwargs) -> Future:
            def do_update_playlist():
                self.server.update_playlist(playlist_id, *args, **kwargs)
                with self.cache_lock:
                    del self.cache['playlist_details'][playlist_id]

            return CacheManager.create_future(do_update_playlist)

        def get_artists(
                self,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[List[Union[Artist, ArtistID3]]]':
            cache_name = self.id3ify('artists')

            if self.cache.get(cache_name) and not force:
                return CacheManager.Result.from_data(self.cache[cache_name])

            def download_fn():
                raw_artists = (
                    self.server.get_artists
                    if self.browse_by_tags else self.server.get_indexes)()

                artists: List[Union[Artist, ArtistID3]] = []
                for index in raw_artists.index:
                    artists.extend(index.artist)

                return artists

            def after_download(artists):
                with self.cache_lock:
                    self.cache[cache_name] = artists
                self.save_cache_info()

            return CacheManager.Result.from_server(
                download_fn,
                before_download=before_download,
                after_download=after_download,
            )

        def get_artist(
                self,
                artist_id,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[Union[ArtistWithAlbumsID3, Child]]':
            cache_name = self.id3ify('artist_details')

            if artist_id in self.cache.get(cache_name, {}) and not force:
                return CacheManager.Result.from_data(
                    self.cache[cache_name][artist_id])

            server_fn = (
                self.server.get_artist
                if self.browse_by_tags else self.server.get_music_directory)

            def after_download(artist):
                with self.cache_lock:
                    self.cache[cache_name][artist_id] = artist
                self.save_cache_info()

            return CacheManager.Result.from_server(
                lambda: server_fn(artist_id),
                before_download=before_download,
                after_download=after_download,
            )

        def get_artist_info(
                self,
                artist_id,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[Union[ArtistInfo, ArtistInfo2]]':
            cache_name = self.id3ify('artist_infos')

            if artist_id in self.cache.get(cache_name, {}) and not force:
                return CacheManager.Result.from_data(
                    self.cache[cache_name][artist_id])

            server_fn = (
                self.server.get_artist_info2
                if self.browse_by_tags else self.server.get_artist_info)

            def after_download(artist_info):
                if not artist_info:
                    return

                with self.cache_lock:
                    self.cache[cache_name][artist_id] = artist_info
                self.save_cache_info()

            return CacheManager.Result.from_server(
                lambda: server_fn(id=artist_id),
                before_download=before_download,
                after_download=after_download,
            )

        def get_artist_artwork(
                self,
                artist: Union[Artist, ArtistID3],
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> 'CacheManager.Result[Optional[str]]':
            def do_get_artist_artwork(artist_info):
                lastfm_url = ''.join(artist_info.largeImageUrl)

                # If it is the placeholder LastFM image, try and use the cover
                # art filename given by the server.
                if lastfm_url.endswith('2a96cbd8b46e442fc41c2b86b821562f.png'):
                    if isinstance(artist, ArtistWithAlbumsID3):
                        return CacheManager.get_cover_art_filename(
                            artist.coverArt, size=300)
                    elif (isinstance(artist, Directory)
                          and len(artist.child) > 0):
                        # Retrieve the first album's cover art
                        return CacheManager.get_cover_art_filename(
                            artist.child[0].coverArt, size=300)

                url_hash = hashlib.md5(lastfm_url.encode('utf-8')).hexdigest()
                return self.return_cached_or_download(
                    f'cover_art/artist.{url_hash}',
                    lambda: requests.get(lastfm_url).content,
                    before_download=before_download,
                    force=force,
                )

            def download_fn(artist_info):
                # In this case, artist_info is a future, so we have to wait for
                # its result before calculating. Then, immediately unwrap the
                # result() because we are already within a future.
                return do_get_artist_artwork(artist_info.result()).result()

            artist_info = CacheManager.get_artist_info(artist.id)
            if artist_info.is_future:
                return CacheManager.Result.from_server(
                    lambda: download_fn(artist_info),
                    before_download=before_download,
                )
            else:
                return do_get_artist_artwork(artist_info.result())

        def get_album_list(
                self,
                type_: str,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
                # Look at documentation for get_album_list in server.py:
                **params,
        ) -> Future:
            cache_name = self.id3ify('albums')
            server_fn = (
                self.server.get_album_list2
                if self.browse_by_tags else self.server.get_album_list)

            def get_page(offset, page_size=500):
                return server_fn(
                    type_,
                    size=page_size,
                    offset=offset,
                    **params,
                ).album or []

            def do_get_album_list() -> List[Union[Child, AlbumWithSongsID3]]:
                if not self.cache.get(cache_name, {}).get(type_, []) or force:
                    before_download()

                    page_size = 40 if type_ == 'random' else 500
                    offset = 0

                    next_page = get_page(offset, page_size=page_size)
                    albums = next_page

                    # If it returns 500 things, then there's more leftover.
                    while len(next_page) == 500:
                        next_page = get_page(offset)
                        albums.extend(next_page)

                    # Update the cache.
                    with self.cache_lock:
                        if not self.cache[cache_name].get(type_):
                            self.cache[cache_name][type_] = []
                        self.cache[cache_name][type_] = albums
                    self.save_cache_info()

                return self.cache[cache_name][type_]

            return CacheManager.create_future(do_get_album_list)

        def invalidate_album_list(self, type_):
            # TODO make this invalidate instead of delete
            cache_name = self.id3ify('albums')
            if not self.cache.get(cache_name, {}).get(type_):
                return
            with self.cache_lock:
                self.cache[cache_name][type_] = []
            self.save_cache_info()

        def get_album(
                self,
                album_id,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_album() -> Union[AlbumWithSongsID3, Child]:
                cache_name = self.id3ify('album_details')
                server_fn = (
                    self.server.get_album if self.browse_by_tags else
                    self.server.get_music_directory)

                if album_id not in self.cache.get(cache_name, {}) or force:
                    before_download()
                    album = server_fn(album_id)

                    with self.cache_lock:
                        self.cache[cache_name][album_id] = album

                    self.save_cache_info()

                return self.cache[cache_name][album_id]

            return CacheManager.create_future(do_get_album)

        def batch_delete_cached_songs(
                self,
                song_ids: List[int],
                on_song_delete: Callable[[], None],
        ) -> Future:
            def do_delete_cached_songs():
                # Do the actual download.
                for song_id in song_ids:
                    song_details_future = CacheManager.get_song_details(
                        song_id)

                    def filename_future_done(f):
                        relative_path = f.result().path
                        abs_path = self.calculate_abs_path(relative_path)
                        if abs_path.exists():
                            abs_path.unlink()
                        on_song_delete()

                    song_details_future.add_done_callback(filename_future_done)

            return CacheManager.create_future(do_delete_cached_songs)

        def batch_download_songs(
                self,
                song_ids: List[int],
                before_download: Callable[[], None],
                on_song_download_complete: Callable[[int], None],
        ) -> Future:
            def do_download_song(song_id):
                # If a song download is already in the queue and then the ap is
                # exited, this prevents the download.
                if CacheManager.should_exit:
                    return

                # Do the actual download. Call .result() because we are already
                # inside of a future.
                song = CacheManager.get_song_details(song_id).result()
                self.return_cached_or_download(
                    song.path,
                    lambda: self.server.download(song.id),
                    before_download=before_download,
                ).result()

                # Allow the next song in the queue to be downloaded.
                self.download_limiter_semaphore.release()
                on_song_download_complete(song_id)

            def do_batch_download_songs():
                self.current_downloads = self.current_downloads.union(
                    set(song_ids))
                for song_id in song_ids:
                    # Only allow a certain number of songs ot be downloaded
                    # simultaneously.
                    self.download_limiter_semaphore.acquire()

                    # Prevents further songs from being downloaded.
                    if CacheManager.should_exit:
                        break
                    CacheManager.create_future(do_download_song, song_id)

            return CacheManager.create_future(do_batch_download_songs)

        def get_cover_art_filename(
                self,
                id: str,
                before_download: Callable[[], None] = lambda: None,
                size: Union[str, int] = 200,
                force: bool = False,
                allow_download: bool = True,
        ) -> 'CacheManager.Result[Optional[str]]':
            tag = 'tag_' if self.browse_by_tags else ''
            return self.return_cached_or_download(
                f'cover_art/{tag}{id}_{size}',
                lambda: self.server.get_cover_art(id, str(size)),
                before_download=before_download,
                force=force,
                allow_download=allow_download,
            )

        def get_song_details(
                self,
                song_id: int,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_song_details() -> Child:
                if not self.cache['song_details'].get(song_id) or force:
                    before_download()
                    song_details = self.server.get_song(song_id)
                    with self.cache_lock:
                        self.cache['song_details'][song_id] = song_details
                    self.save_cache_info()

                return self.cache['song_details'][song_id]

            return CacheManager.create_future(do_get_song_details)

        def get_play_queue(self) -> Future:
            return CacheManager.create_future(self.server.get_play_queue)

        def save_play_queue(
                self,
                play_queue: List[str],
                current: str,
                position: float,
        ):
            CacheManager.create_future(
                self.server.save_play_queue, play_queue, current, position)

        def scrobble(self, song_id: int) -> Future:
            def do_scrobble():
                self.server.scrobble(song_id)

            return CacheManager.create_future(do_scrobble)

        def get_song_filename_or_stream(
                self,
                song: Child,
                format=None,
                force_stream: bool = False,
        ) -> Tuple[str, bool]:
            abs_path = self.calculate_abs_path(song.path)
            if not abs_path.exists() or force_stream:
                return (
                    self.server.get_stream_url(song.id, format=format),
                    True,
                )

            return (str(abs_path), False)

        def get_genres(
                self,
                before_download: Callable[[], None] = lambda: None,
                force: bool = False,
        ) -> Future:
            def do_get_genres() -> List[Genre]:
                if not self.cache['genres'] or force:
                    before_download()
                    genres = self.server.get_genres().genre
                    with self.cache_lock:
                        self.cache['genres'] = genres
                    self.save_cache_info()

                return self.cache['genres']

            return CacheManager.create_future(do_get_genres)

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

        def id3ify(self, cache_type):
            return cache_type + ('_id3' if self.browse_by_tags else '')

    _instance: Optional[__CacheManagerInternal] = None

    def __init__(self, server_config: ServerConfiguration):
        raise Exception('Do not instantiate the CacheManager.')

    @classmethod
    def reset(cls, app_config, server_config):
        CacheManager._instance = CacheManager.__CacheManagerInternal(
            app_config, server_config)
