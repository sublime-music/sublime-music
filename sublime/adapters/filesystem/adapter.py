import logging
import shutil
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast, Dict, Optional, Sequence, Set, Tuple, Union

from sublime import util
from sublime.adapters import api_objects as API

from . import models
from .. import CacheMissError, CachingAdapter, ConfigParamDescriptor, SongCacheStatus


class FilesystemAdapter(CachingAdapter):
    """
    Defines an adapter which retrieves its data from the local filesystem.
    """

    # Configuration and Initialization Properties
    # ==================================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        return {
            # TODO: download on play?
        }

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {}

    def __init__(
        self, config: dict, data_directory: Path, is_cache: bool = False,
    ):
        self.data_directory = data_directory
        self.cover_art_dir = self.data_directory.joinpath("cover_art")
        self.music_dir = self.data_directory.joinpath("music")

        self.cover_art_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

        self.is_cache = is_cache

        self.db_write_lock: threading.Lock = threading.Lock()
        database_filename = data_directory.joinpath("cache.db")
        models.database.init(database_filename)
        models.database.connect()

        with self.db_write_lock, models.database.atomic():
            models.database.create_tables(models.ALL_TABLES)
            self._migrate_db()

    def shutdown(self):
        logging.info("Shutdown complete")

    # Database Migration
    # ==================================================================================
    def _migrate_db(self):
        pass

    # Usage and Availability Properties
    # ==================================================================================
    can_be_cached = False  # Can't be cached (there's no need).
    is_networked = False  # Can't be cached (there's no need).
    can_service_requests = True  # Can always be used to service requests.

    # TODO make these dependent on cache state.
    can_get_playlists = True
    can_get_playlist_details = True
    can_get_cover_art_uri = True
    can_get_song_uri = True
    can_get_song_details = True
    can_get_artists = True
    can_get_artist = True
    can_get_albums = True
    can_get_album = True
    can_get_ignored_articles = True
    can_get_genres = True
    can_search = True

    supported_schemes = ("file",)

    # Data Helper Methods
    # ==================================================================================
    def _get_list(
        self,
        model: Any,
        cache_key: CachingAdapter.CachedDataKey,
        ignore_cache_miss: bool = False,
    ) -> Sequence:
        result = list(model.select())
        if self.is_cache and not ignore_cache_miss:
            # Determine if the adapter has ingested data for this key before, and if
            # not, cache miss.
            if not models.CacheInfo.get_or_none(
                models.CacheInfo.cache_key == cache_key
            ):
                raise CacheMissError(partial_data=result)
        return result

    def _get_object_details(
        self, model: Any, id: str, cache_key: CachingAdapter.CachedDataKey
    ) -> Any:
        obj = model.get_or_none(model.id == id)

        # Handle the case that this is the ground truth adapter.
        if not self.is_cache:
            if not obj:
                raise Exception(f"{model} with id={id} does not exist")
            return obj

        # If we haven't ingested data for this item before, or it's been invalidated,
        # raise a CacheMissError with the partial data.
        cache_info = models.CacheInfo.get_or_none(
            models.CacheInfo.cache_key == cache_key,
            models.CacheInfo.params_hash == util.params_hash(id),
        )
        if not cache_info:
            raise CacheMissError(partial_data=obj)

        return obj

    def _get_download_filename(
        self,
        filename: Path,
        params: Tuple[Any],
        cache_key: CachingAdapter.CachedDataKey,
    ) -> str:
        if not filename.exists():
            # Handle the case that this is the ground truth adapter.
            if self.is_cache:
                raise CacheMissError()
            else:
                raise Exception(f"File for {cache_key} {params} does not exist.")

        if not self.is_cache:
            return str(filename)

        # If we haven't ingested data for this file before, or it's been invalidated,
        # raise a CacheMissError with the filename.
        cache_info = models.CacheInfo.get_or_none(
            models.CacheInfo.cache_key == cache_key,
            models.CacheInfo.params_hash == util.params_hash(*params),
        )
        if not cache_info:
            raise CacheMissError(partial_data=str(filename))

        return str(filename)

    # Data Retrieval Methods
    # ==================================================================================
    def get_cached_status(self, song: API.Song) -> SongCacheStatus:
        song = models.Song.get_or_none(models.Song.id == song.id)
        if not song:
            return SongCacheStatus.NOT_CACHED
        cache_path = self.music_dir.joinpath(song.path)
        if cache_path.exists():
            # TODO check if path is permanently cached
            return SongCacheStatus.CACHED

        return SongCacheStatus.NOT_CACHED

    def get_playlists(self, ignore_cache_miss: bool = False) -> Sequence[API.Playlist]:
        return self._get_list(
            models.Playlist,
            CachingAdapter.CachedDataKey.PLAYLISTS,
            ignore_cache_miss=ignore_cache_miss,
        )

    def get_playlist_details(self, playlist_id: str) -> API.PlaylistDetails:
        return self._get_object_details(
            models.Playlist, playlist_id, CachingAdapter.CachedDataKey.PLAYLIST_DETAILS
        )

    def get_cover_art_uri(self, cover_art_id: str, scheme: str) -> str:
        # TODO cache by the content of the file (need to see if cover art ID is
        # duplicated a lot)?
        params_hash = util.params_hash(cover_art_id)
        return self._get_download_filename(
            self.cover_art_dir.joinpath(params_hash),
            (cover_art_id,),
            CachingAdapter.CachedDataKey.COVER_ART_FILE,
        )

    def get_song_uri(self, song_id: str, scheme: str, stream: bool = False) -> str:
        song = models.Song.get_or_none(models.Song.id == song_id)
        if not song:
            if self.is_cache:
                raise CacheMissError()
            else:
                raise Exception(f"Song {song_id} does not exist.")

        return self._get_download_filename(
            self.music_dir.joinpath(song.path),
            (song_id,),
            CachingAdapter.CachedDataKey.SONG_FILE,
        )

    def get_song_details(self, song_id: str) -> API.Song:
        return self._get_object_details(
            models.Song, song_id, CachingAdapter.CachedDataKey.SONG_DETAILS
        )

    def get_artists(self, ignore_cache_miss: bool = False) -> Sequence[API.Artist]:
        return self._get_list(
            models.Artist,
            CachingAdapter.CachedDataKey.ARTISTS,
            ignore_cache_miss=ignore_cache_miss,
        )

    def get_artist(self, artist_id: str) -> API.Artist:
        return self._get_object_details(
            models.Artist, artist_id, CachingAdapter.CachedDataKey.ARTIST
        )

    def get_albums(self, ignore_cache_miss: bool = False) -> Sequence[API.Album]:
        # TODO all of the parameters
        return self._get_list(
            models.Album,
            CachingAdapter.CachedDataKey.ALBUMS,
            ignore_cache_miss=ignore_cache_miss,
        )

    def get_album(self, album_id: str) -> API.Album:
        return self._get_object_details(
            models.Album, album_id, CachingAdapter.CachedDataKey.ALBUM
        )

    def get_ignored_articles(self) -> Set[str]:
        return set(
            map(
                lambda i: i.name,
                self._get_list(
                    models.IgnoredArticle, CachingAdapter.CachedDataKey.IGNORED_ARTICLES
                ),
            )
        )

    def get_genres(self) -> Sequence[API.Genre]:
        return self._get_list(models.Genre, CachingAdapter.CachedDataKey.GENRES)

    def search(self, query: str) -> API.SearchResult:
        search_result = API.SearchResult()
        search_result.add_results("albums", self.get_albums(ignore_cache_miss=True))
        search_result.add_results("artists", self.get_artists(ignore_cache_miss=True))
        search_result.add_results(
            "songs",
            self._get_list(
                models.Song,
                CachingAdapter.CachedDataKey.SONG_DETAILS,
                ignore_cache_miss=True,
            ),
        )
        search_result.add_results(
            "playlists", self.get_playlists(ignore_cache_miss=True)
        )
        return search_result

    # Data Ingestion Methods
    # ==================================================================================
    def ingest_new_data(
        self,
        data_key: CachingAdapter.CachedDataKey,
        params: Tuple[Any, ...],
        data: Any,
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_ingest_new_data(data_key, params, data)

    def invalidate_data(
        self, function: CachingAdapter.CachedDataKey, params: Tuple[Any, ...]
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_invalidate_data(function, params)

    def delete_data(
        self, function: CachingAdapter.CachedDataKey, params: Tuple[Any, ...]
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_delete_data(function, params)

    def _do_ingest_new_data(
        self,
        data_key: CachingAdapter.CachedDataKey,
        params: Tuple[Any, ...],
        data: Any,
    ):
        # TODO: this entire function is not exactly efficient due to the nested
        # dependencies and everything. I'm not sure how to improve it, and I'm not sure
        # if it needs improving at this point.

        # TODO refactor to to be a recursive function like invalidate_data?

        # TODO may need to remove reliance on asdict in order to support more backends.
        params_hash = util.params_hash(*params)
        models.CacheInfo.insert(
            cache_key=data_key,
            params_hash=params_hash,
            last_ingestion_time=datetime.now(),
        ).on_conflict_replace().execute()

        def setattrs(obj: Any, data: Dict[str, Any]):
            for k, v in data.items():
                if v:
                    setattr(obj, k, v)

        def ingest_directory_data(api_directory: API.Directory) -> models.Directory:
            directory_data = asdict(api_directory)
            directory, created = models.Directory.get_or_create(
                id=api_directory.id, defaults=directory_data
            )

            if not created:
                setattrs(directory, directory_data)
                directory.save()

            return directory

        def ingest_genre_data(api_genre: API.Genre) -> models.Genre:
            genre_data = asdict(api_genre)
            genre, created = models.Genre.get_or_create(
                name=api_genre.name, defaults=genre_data
            )

            if not created:
                setattrs(genre, genre_data)
                genre.save()

            return genre

        def ingest_album_data(
            api_album: API.Album, exclude_artist: bool = False
        ) -> models.Album:
            album_data = {
                **asdict(api_album),
                "genre": ingest_genre_data(g) if (g := api_album.genre) else None,
                "artist": ingest_artist_data(ar) if (ar := api_album.artist) else None,
                "songs": [
                    ingest_song_data(s, fill_album=False) for s in api_album.songs or []
                ],
            }

            if exclude_artist:
                del album_data["artist"]

            album, created = models.Album.get_or_create(
                id=api_album.id, defaults=album_data
            )

            if not created:
                setattrs(album, album_data)
                album.save()

            return album

        def ingest_artist_data(api_artist: API.Artist) -> models.Artist:
            # Ingest similar artists.
            models.SimilarArtist.insert_many(
                [
                    {"artist": api_artist.id, "similar_artist": a.id, "order": i}
                    for i, a in enumerate(api_artist.similar_artists or [])
                ]
            ).on_conflict_replace().execute()
            models.SimilarArtist.delete().where(
                models.SimilarArtist.similar_artist.not_in(
                    [sa.id for sa in api_artist.similar_artists or []]
                ),
                models.Artist == api_artist.id,
            ).execute()

            artist_data = {
                **asdict(api_artist),
                "albums": [
                    ingest_album_data(a, exclude_artist=True)
                    for a in api_artist.albums or []
                ],
            }
            del artist_data["similar_artists"]

            artist, created = models.Artist.get_or_create(
                id=api_artist.id, defaults=artist_data
            )

            if not created:
                setattrs(artist, artist_data)
                artist.save()

            return artist

        def ingest_song_data(
            api_song: API.Song, fill_album: bool = True
        ) -> models.Song:
            song_data = {
                **asdict(api_song),
                "parent": ingest_directory_data(d) if (d := api_song.parent) else None,
                "genre": ingest_genre_data(g) if (g := api_song.genre) else None,
                "artist": ingest_artist_data(ar) if (ar := api_song.artist) else None,
            }

            if fill_album:
                # Don't incurr the overhead of creating an album if we are going to turn
                # around and do it in the ingest_album_data function.
                song_data["album"] = (
                    ingest_album_data(al) if (al := api_song.album) else None
                )

            song, created = models.Song.get_or_create(
                id=song_data["id"], defaults=song_data
            )

            if not created:
                setattrs(song, song_data)
                song.save()

            return song

        def ingest_playlist(
            api_playlist: Union[API.Playlist, API.PlaylistDetails]
        ) -> models.Playlist:
            playlist_data = {
                **asdict(api_playlist),
                "songs": [
                    ingest_song_data(s)
                    for s in (
                        api_playlist.songs
                        if isinstance(api_playlist, API.PlaylistDetails)
                        else ()
                    )
                ],
            }
            playlist, playlist_created = models.Playlist.get_or_create(
                id=playlist_data["id"], defaults=playlist_data
            )

            # Update the values if the playlist already existed.
            if not playlist_created:
                setattrs(playlist, playlist_data)
                playlist.save()

            return playlist

        if data_key == CachingAdapter.CachedDataKey.ALBUM:
            ingest_album_data(data)

        elif data_key == CachingAdapter.CachedDataKey.ALBUMS:
            for a in data:
                ingest_album_data(a)
            # TODO need some other way of deleting stale albums

        elif data_key == CachingAdapter.CachedDataKey.ARTIST:
            ingest_artist_data(data)

        elif data_key == CachingAdapter.CachedDataKey.ARTISTS:
            for a in data:
                ingest_artist_data(a)
            models.Artist.delete().where(
                models.Artist.id.not_in([a.id for a in data])
            ).execute()

        elif data_key == CachingAdapter.CachedDataKey.COVER_ART_FILE:
            # ``data`` is the filename of the tempfile in this case
            shutil.copy(str(data), str(self.cover_art_dir.joinpath(params_hash)))

        elif data_key == CachingAdapter.CachedDataKey.GENRES:
            for g in data:
                ingest_genre_data(g)

        elif data_key == CachingAdapter.CachedDataKey.IGNORED_ARTICLES:
            models.IgnoredArticle.insert_many(
                map(lambda s: {"name": s}, data)
            ).on_conflict_replace().execute()
            models.IgnoredArticle.delete().where(
                models.IgnoredArticle.name.not_in(data)
            ).execute()

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            ingest_playlist(data)

        elif data_key == CachingAdapter.CachedDataKey.PLAYLISTS:
            for p in data:
                ingest_playlist(p)
            models.Playlist.delete().where(
                models.Playlist.id.not_in([p.id for p in data])
            ).execute()

        elif data_key == CachingAdapter.CachedDataKey.SEARCH_RESULTS:
            data = cast(API.SearchResult, data)
            for a in data._artists.values():
                ingest_artist_data(a)

            for a in data._albums.values():
                ingest_album_data(a)

            for s in data._songs.values():
                ingest_song_data(s)

            for p in data._playlists.values():
                ingest_song_data(p)

        elif data_key == CachingAdapter.CachedDataKey.SONG_DETAILS:
            ingest_song_data(data)

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            relative_path = models.Song.get_by_id(params[0]).path
            absolute_path = self.music_dir.joinpath(relative_path)
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(data), str(absolute_path))

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE_PERMANENT:
            raise NotImplementedError()

    def _do_invalidate_data(
        self, data_key: CachingAdapter.CachedDataKey, params: Tuple[Any, ...],
    ):
        models.CacheInfo.delete().where(
            models.CacheInfo.cache_key == data_key,
            models.CacheInfo.params_hash == util.params_hash(*params),
        ).execute()

        cover_art_cache_key = CachingAdapter.CachedDataKey.COVER_ART_FILE

        if data_key == CachingAdapter.CachedDataKey.ALBUM:
            album = models.Album.get_or_none(models.Album.id == params[0])
            if album:
                self._do_invalidate_data(cover_art_cache_key, (album.cover_art,))

        elif data_key == CachingAdapter.CachedDataKey.ARTIST:
            # Invalidate the corresponding cover art.
            if artist := models.Artist.get_or_none(models.Artist.id == params[0]):
                self._do_invalidate_data(
                    cover_art_cache_key, (artist.artist_image_url,)
                )
                for album in artist.albums or []:
                    self._do_invalidate_data(
                        CachingAdapter.CachedDataKey.ALBUM, (album.id,)
                    )

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            # Invalidate the corresponding cover art.
            if playlist := models.Playlist.get_or_none(models.Playlist.id == params[0]):
                self._do_invalidate_data(cover_art_cache_key, (playlist.cover_art,))

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            # Invalidate the corresponding cover art.
            if song := models.Song.get_or_none(models.Song.id == params[0]):
                self._do_invalidate_data(cover_art_cache_key, (song.cover_art,))

    def _do_delete_data(
        self, data_key: CachingAdapter.CachedDataKey, params: Tuple[Any, ...],
    ):
        # Invalidate it.
        self._do_invalidate_data(data_key, params)
        cover_art_cache_key = CachingAdapter.CachedDataKey.COVER_ART_FILE

        if data_key == CachingAdapter.CachedDataKey.COVER_ART_FILE:
            cover_art_file = self.cover_art_dir.joinpath(util.params_hash(*params))
            cover_art_file.unlink(missing_ok=True)

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            # Delete the playlist and corresponding cover art.
            if playlist := models.Playlist.get_or_none(models.Playlist.id == params[0]):
                if cover_art := playlist.cover_art:
                    self._do_delete_data(cover_art_cache_key, (cover_art,))

                playlist.delete_instance()

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            if song := models.Song.get_or_none(models.Song.id == params[0]):
                # Delete the song
                music_filename = self.music_dir.joinpath(song.path)
                music_filename.unlink(missing_ok=True)

                # Delete the corresponding cover art.
                if cover_art := song.cover_art:
                    self._do_delete_data(cover_art_cache_key, (cover_art,))
