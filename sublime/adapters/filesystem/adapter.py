import logging
import shutil
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Set, Tuple

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

    supported_schemes = ("file",)

    # Data Helper Methods
    # ==================================================================================
    def _get_list(
        self, model: Any, cache_key: CachingAdapter.CachedDataKey
    ) -> Sequence:
        result = list(model.select())
        if self.is_cache:
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

    def get_playlists(self) -> Sequence[API.Playlist]:
        return self._get_list(models.Playlist, CachingAdapter.CachedDataKey.PLAYLISTS)

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

    def get_artists(self) -> Sequence[API.Artist]:
        return self._get_list(models.Artist, CachingAdapter.CachedDataKey.ARTISTS)

    def get_artist(self, artist_id: str) -> API.Artist:
        return self._get_object_details(
            models.Artist, artist_id, CachingAdapter.CachedDataKey.ARTIST
        )

    def get_albums(self) -> Sequence[API.Album]:
        return self._get_list(models.Album, CachingAdapter.CachedDataKey.ALBUMS)

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
        # TODO may need to remove reliance on asdict in order to support more backends.
        params_hash = util.params_hash(*params)
        models.CacheInfo.insert(
            cache_key=data_key,
            params_hash=params_hash,
            last_ingestion_time=datetime.now(),
        ).on_conflict_replace().execute()

        def ingest_list(model: Any, data: Any, id_property: Any):
            model.insert_many(map(asdict, data)).on_conflict_replace().execute()
            model.delete().where(
                id_property.not_in([getattr(p, id_property.name) for p in data])
            ).execute()

        def set_attrs(obj: Any, data: Dict[str, Any]):
            for k, v in data.items():
                if v:
                    setattr(obj, k, v)

        def ingest_directory_data(api_directory: API.Directory) -> models.Directory:
            directory_data = asdict(api_directory)
            directory, created = models.Directory.get_or_create(
                id=api_directory.id, defaults=directory_data
            )

            if not created:
                set_attrs(directory, directory_data)
                directory.save()

            return directory

        def ingest_genre_data(api_genre: API.Genre) -> models.Genre:
            genre_data = asdict(api_genre)
            genre, created = models.Genre.get_or_create(
                name=api_genre.name, defaults=asdict(api_genre)
            )

            if not created:
                set_attrs(genre, genre_data)
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
                set_attrs(album, album_data)
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
                set_attrs(artist, artist_data)
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
                set_attrs(song, song_data)
                song.save()

            return song

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
            ingest_list(models.Genre, data, models.Genre.name)

        elif data_key == CachingAdapter.CachedDataKey.IGNORED_ARTICLES:
            models.IgnoredArticle.insert_many(
                map(lambda s: {"name": s}, data)
            ).on_conflict_replace().execute()
            models.IgnoredArticle.delete().where(
                models.IgnoredArticle.name.not_in(data)
            ).execute()

        elif data_key == CachingAdapter.CachedDataKey.PLAYLISTS:
            ingest_list(models.Playlist, data, models.Playlist.id)

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            song_objects = [ingest_song_data(s) for s in data.songs]
            playlist_data = {**asdict(data), "songs": song_objects}
            playlist, playlist_created = models.Playlist.get_or_create(
                id=playlist_data["id"], defaults=playlist_data
            )

            # Update the values if the playlist already existed.
            if not playlist_created:
                for k, v in playlist_data.items():
                    setattr(playlist, k, v)

                playlist.save()

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
            artist = models.Artist.get_or_none(models.Artist.id == params[0])
            if not artist:
                return

            self._do_invalidate_data(cover_art_cache_key, (artist.artist_image_url,))
            for album in artist.albums or []:
                self._do_invalidate_data(
                    CachingAdapter.CachedDataKey.ALBUM, (album.id,)
                )

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            # Invalidate the corresponding cover art.
            playlist = models.Playlist.get_or_none(models.Playlist.id == params[0])
            if playlist:
                self._do_invalidate_data(cover_art_cache_key, (playlist.cover_art,))

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            # Invalidate the corresponding cover art.
            song = models.Song.get_or_none(models.Song.id == params[0])
            if song:
                self._do_invalidate_data(cover_art_cache_key, (song.cover_art,))

    def _do_delete_data(
        self, data_key: CachingAdapter.CachedDataKey, params: Tuple[Any, ...],
    ):
        # Delete it from the cache info.
        models.CacheInfo.delete().where(
            models.CacheInfo.cache_key == data_key,
            models.CacheInfo.params_hash == util.params_hash(*params),
        ).execute()

        def delete_cover_art(cover_art_id: str):
            cover_art_params_hash = util.params_hash(cover_art_id)
            if cover_art_file := self.cover_art_dir.joinpath(cover_art_params_hash):
                cover_art_file.unlink(missing_ok=True)
            self._do_invalidate_data(
                CachingAdapter.CachedDataKey.COVER_ART_FILE, (cover_art_id,)
            )

        if data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            # Delete the playlist and corresponding cover art.
            playlist = models.Playlist.get_or_none(models.Playlist.id == params[0])
            if not playlist:
                return

            if playlist.cover_art:
                delete_cover_art(playlist.cover_art)

            playlist.delete_instance()

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            song = models.Song.get_or_none(models.Song.id == params[0])
            if not song:
                return

            # Delete the song
            music_filename = self.music_dir.joinpath(song.path)
            music_filename.unlink(missing_ok=True)

            # Delete the corresponding cover art.
            if song.cover_art:
                delete_cover_art(song.cover_art)
