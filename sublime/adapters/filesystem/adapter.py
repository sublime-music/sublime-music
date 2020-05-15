import hashlib
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast, Dict, Optional, Sequence, Set, Tuple, Union

from peewee import fn

from sublime import util
from sublime.adapters import api_objects as API

from . import models
from .. import (
    AlbumSearchQuery,
    CacheMissError,
    CachingAdapter,
    ConfigParamDescriptor,
    SongCacheStatus,
)


class FilesystemAdapter(CachingAdapter):
    """
    Defines an adapter which retrieves its data from the local filesystem.
    """

    # Configuration and Initialization Properties
    # ==================================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        return {
            # TODO (#188): directory path, whether or not to scan tags
        }

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {
            # TODO (#188): verify that the path exists
        }

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

    # TODO make these dependent on cache state. Need to do this kinda efficiently
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
    can_get_directory = True
    can_get_genres = True
    can_search = True

    supported_schemes = ("file",)
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

    # Data Helper Methods
    # ==================================================================================
    def _get_list(
        self,
        model: Any,
        cache_key: CachingAdapter.CachedDataKey,
        ignore_cache_miss: bool = False,
        where_clause: Optional[Tuple[Any, ...]] = None,
    ) -> Sequence:
        query = model.select()
        if where_clause:
            query = query.where(*where_clause)
        result = list(query)
        if self.is_cache and not ignore_cache_miss:
            # Determine if the adapter has ingested data for this key before, and if
            # not, cache miss.
            if not models.CacheInfo.get_or_none(
                models.CacheInfo.valid == True,  # noqa: 712
                models.CacheInfo.cache_key == cache_key,
            ):
                raise CacheMissError(partial_data=result)
        return result

    def _get_object_details(
        self,
        model: Any,
        id: str,
        cache_key: CachingAdapter.CachedDataKey,
        where_clause: Tuple[Any, ...] = (),
        cache_where_clause: Tuple[Any, ...] = (),
    ) -> Any:
        obj = model.get_or_none(model.id == id, *where_clause)

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
            models.CacheInfo.valid == True,  # noqa: 712
            *cache_where_clause,
        )
        if not cache_info:
            raise CacheMissError(partial_data=obj)

        return obj

    def _compute_song_filename(self, cache_info: models.CacheInfo) -> Path:
        if path_str := cache_info.path:
            # Make sure that the path is somewhere in the cache directory and a
            # malicious server (or MITM attacker) isn't trying to override files in
            # other parts of the system.
            path = self.music_dir.joinpath(path_str)
            if self.music_dir in path.parents:
                return path

        # Fall back to using the song file hash as the filename. This shouldn't happen
        # with good servers, but just to be safe.
        return self.music_dir.joinpath(cache_info.file_hash)

    # Data Retrieval Methods
    # ==================================================================================
    def get_cached_status(self, song: API.Song) -> SongCacheStatus:
        try:
            song_model = self.get_song_details(song.id)
            file = song_model.file
            if self._compute_song_filename(file).exists():
                if file.valid:
                    if file.cache_permanently:
                        return SongCacheStatus.PERMANENTLY_CACHED
                    return SongCacheStatus.CACHED

                # The file is on disk, but marked as stale.
                return SongCacheStatus.CACHED_STALE
        except Exception:
            pass

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
        cover_art = models.CacheInfo.get_or_none(
            models.CacheInfo.cache_key == CachingAdapter.CachedDataKey.COVER_ART_FILE,
            models.CacheInfo.params_hash == util.params_hash(cover_art_id),
        )
        if cover_art:
            filename = self.cover_art_dir.joinpath(str(cover_art.file_hash))
            if cover_art.valid and filename.exists():
                return str(filename)
            raise CacheMissError(partial_data=str(filename))

        raise CacheMissError()

    def get_song_uri(self, song_id: str, scheme: str, stream: bool = False) -> str:
        song = models.Song.get_or_none(models.Song.id == song_id)
        if not song:
            if self.is_cache:
                raise CacheMissError()
            else:
                raise Exception(f"Song {song_id} does not exist.")

        try:
            if (song_file := song.file) and (
                filename := self._compute_song_filename(song_file)
            ):
                if song_file.valid and filename.exists():
                    return str(filename)
                raise CacheMissError(partial_data=str(filename))
        except models.CacheInfo.DoesNotExist:
            pass

        raise CacheMissError()

    def get_song_details(self, song_id: str) -> models.Song:
        return self._get_object_details(
            models.Song, song_id, CachingAdapter.CachedDataKey.SONG,
        )

    def get_artists(self, ignore_cache_miss: bool = False) -> Sequence[API.Artist]:
        # TODO order_by
        return self._get_list(
            models.Artist,
            CachingAdapter.CachedDataKey.ARTISTS,
            ignore_cache_miss=ignore_cache_miss,
        )

    def get_artist(self, artist_id: str) -> API.Artist:
        return self._get_object_details(
            models.Artist, artist_id, CachingAdapter.CachedDataKey.ARTIST
        )

    def get_albums(self, query: AlbumSearchQuery) -> Sequence[API.Album]:
        # TODO: deal with ordering
        # TODO: deal with paging
        # TODO: deal with cache invalidation
        sql_query = models.Album.select()
        # TODO use the new ``where_clause`` from get_list

        Type = AlbumSearchQuery.Type
        if query.type == Type.GENRE:
            assert query.genre
        genre_name = genre.name if (genre := query.genre) else None

        sql_query = {
            Type.RANDOM: sql_query.order_by(fn.Random()),
            Type.NEWEST: sql_query.order_by(models.Album.created.desc()),
            Type.FREQUENT: sql_query.order_by(models.Album.play_count.desc()),
            Type.RECENT: sql_query,  # TODO IMPLEMENT
            Type.STARRED: sql_query.where(models.Album.starred.is_null(False)),
            Type.ALPHABETICAL_BY_NAME: sql_query.order_by(models.Album.name),
            Type.ALPHABETICAL_BY_ARTIST: sql_query.order_by(models.Album.artist.name),
            Type.YEAR_RANGE: sql_query.where(
                models.Album.year.between(*query.year_range)
            ).order_by(models.Album.year),
            Type.GENRE: sql_query.where(models.Album.genre == genre_name),
        }[query.type]

        if self.is_cache:
            # Determine if the adapter has ingested data for this key before, and if
            # not, cache miss.
            if not models.CacheInfo.get_or_none(
                models.CacheInfo.cache_key == CachingAdapter.CachedDataKey.ALBUMS,
                models.CacheInfo.params_hash == util.params_hash(query),
                models.CacheInfo.valid == True,  # noqa: 712
            ):
                raise CacheMissError(partial_data=sql_query)

        return sql_query

    def get_all_albums(self) -> Sequence[API.Album]:
        return self._get_list(
            models.Album, CachingAdapter.CachedDataKey.ALBUMS, ignore_cache_miss=True
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

    def get_directory(self, directory_id: str) -> models.Directory:
        return self._get_object_details(
            models.Directory, directory_id, CachingAdapter.CachedDataKey.DIRECTORY
        )

    def get_genres(self) -> Sequence[API.Genre]:
        return self._get_list(models.Genre, CachingAdapter.CachedDataKey.GENRES)

    def search(self, query: str) -> API.SearchResult:
        search_result = API.SearchResult()
        search_result.add_results("albums", self.get_all_albums())
        search_result.add_results("artists", self.get_artists(ignore_cache_miss=True))
        search_result.add_results(
            "songs",
            self._get_list(
                models.Song, CachingAdapter.CachedDataKey.SONG, ignore_cache_miss=True
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
        partial: bool = False,
    ) -> Any:
        # TODO: this entire function is not exactly efficient due to the nested
        # dependencies and everything. I'm not sure how to improve it, and I'm not sure
        # if it needs improving at this point.

        # TODO refactor to to be a recursive function like invalidate_data?

        params_hash = util.params_hash(*params)
        cache_info_extra: Dict[str, Any] = {}

        logging.debug(
            f"_do_ingest_new_data params={params} params_hash={params_hash} data_key={data_key} data={data}"  # noqa: 502
        )

        KEYS = CachingAdapter.CachedDataKey

        def setattrs(obj: Any, data: Dict[str, Any]):
            for k, v in data.items():
                if v:
                    setattr(obj, k, v)

        def ingest_directory_data(api_directory: API.Directory) -> models.Directory:
            directory_data: Dict[str, Any] = {
                "id": api_directory.id,
                "name": api_directory.name,
                "parent_id": api_directory.parent_id,
            }

            if not partial:
                directory_data["directory_children"] = []
                directory_data["song_children"] = []
                for c in api_directory.children:
                    if hasattr(c, "children"):  # directory
                        directory_data["directory_children"].append(
                            self._do_ingest_new_data(
                                KEYS.DIRECTORY, (c.id,), c, partial=True
                            )
                        )
                    else:
                        directory_data["song_children"].append(
                            self._do_ingest_new_data(KEYS.SONG, (c.id,), c)
                        )

            directory, created = models.Directory.get_or_create(
                id=api_directory.id, defaults=directory_data
            )

            if not created:
                setattrs(directory, directory_data)
                directory.save()

            return directory

        def ingest_genre_data(api_genre: API.Genre) -> models.Genre:
            genre_data = {
                "name": api_genre.name,
                "song_count": getattr(api_genre, "song_count", None),
                "album_count": getattr(api_genre, "album_count", None),
            }
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
                "id": api_album.id,
                "name": api_album.name,
                "created": getattr(api_album, "created", None),
                "duration": getattr(api_album, "duration", None),
                "play_count": getattr(api_album, "play_count", None),
                "song_count": getattr(api_album, "song_count", None),
                "starred": getattr(api_album, "starred", None),
                "year": getattr(api_album, "year", None),
                "genre": ingest_genre_data(g) if (g := api_album.genre) else None,
                "artist": ingest_artist_data(ar) if (ar := api_album.artist) else None,
                "songs": [
                    ingest_song_data(s, fill_album=False) for s in api_album.songs or []
                ],
                "_cover_art": self._do_ingest_new_data(
                    KEYS.COVER_ART_FILE, params=(api_album.cover_art,), data=None,
                )
                if api_album.cover_art
                else None,
            }

            album, created = models.Album.get_or_create(
                id=api_album.id, defaults=album_data
            )

            if not created:
                setattrs(album, album_data)
                album.save()

            return album

        def ingest_artist_data(api_artist: API.Artist) -> models.Artist:
            # Ingest similar artists.
            # TODO figure out which order to do this in to be most efficient.
            if api_artist.similar_artists:
                models.SimilarArtist.delete().where(
                    models.SimilarArtist.similar_artist.not_in(
                        [sa.id for sa in api_artist.similar_artists or []]
                    ),
                    models.Artist == api_artist.id,
                ).execute()
                models.SimilarArtist.insert_many(
                    [
                        {"artist": api_artist.id, "similar_artist": a.id, "order": i}
                        for i, a in enumerate(api_artist.similar_artists or [])
                    ]
                ).on_conflict_replace().execute()

            artist_data = {
                "id": api_artist.id,
                "name": api_artist.name,
                "album_count": getattr(api_artist, "album_count", None),
                "starred": getattr(api_artist, "starred", None),
                "biography": getattr(api_artist, "biography", None),
                "music_brainz_id": getattr(api_artist, "music_brainz_id", None),
                "last_fm_url": getattr(api_artist, "last_fm_url", None),
                "albums": [
                    ingest_album_data(a, exclude_artist=True)
                    for a in api_artist.albums or []
                ],
                "_artist_image_url": self._do_ingest_new_data(
                    KEYS.COVER_ART_FILE,
                    params=(api_artist.artist_image_url,),
                    data=None,
                )
                if api_artist.artist_image_url
                else None,
            }
            # del artist_data["artist_image_url"]
            # del artist_data["similar_artists"]

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
                "id": api_song.id,
                "title": api_song.title,
                "track": getattr(api_song, "track", None),
                "year": getattr(api_song, "year", None),
                "duration": getattr(api_song, "duration", None),
                "parent_id": api_song.parent_id,
                # Ingest the FKs.
                "genre": ingest_genre_data(g) if (g := api_song.genre) else None,
                "artist": ingest_artist_data(ar) if (ar := api_song.artist) else None,
                "album": ingest_album_data(al) if (al := api_song.album) else None,
                "_cover_art": self._do_ingest_new_data(
                    KEYS.COVER_ART_FILE, params=(api_song.cover_art,), data=None,
                )
                if api_song.cover_art
                else None,
                "file": self._do_ingest_new_data(
                    KEYS.SONG_FILE, params=(api_song.id,), data=(api_song.path, None)
                )
                if api_song.path
                else None,
            }

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
                "id": api_playlist.id,
                "name": api_playlist.name,
                "song_count": api_playlist.song_count,
                "duration": api_playlist.duration,
                "created": getattr(api_playlist, "created", None),
                "changed": getattr(api_playlist, "changed", None),
                "comment": getattr(api_playlist, "comment", None),
                "owner": getattr(api_playlist, "owner", None),
                "public": getattr(api_playlist, "public", None),
                "songs": [
                    self._do_ingest_new_data(KEYS.SONG, (s.id,), s)
                    for s in (
                        cast(API.PlaylistDetails, api_playlist).songs
                        if hasattr(api_playlist, "songs")
                        else ()
                    )
                ],
                "_cover_art": self._do_ingest_new_data(
                    KEYS.COVER_ART_FILE, (api_playlist.cover_art,), None
                )
                if api_playlist.cover_art
                else None,
            }

            playlist, playlist_created = models.Playlist.get_or_create(
                id=playlist_data["id"], defaults=playlist_data
            )

            # Update the values if the playlist already existed.
            if not playlist_created:
                setattrs(playlist, playlist_data)
                playlist.save()

            return playlist

        def compute_file_hash(filename: str) -> str:
            file_hash = hashlib.sha1()
            with open(filename, "rb") as f:
                while chunk := f.read(8192):
                    file_hash.update(chunk)

            return file_hash.hexdigest()

        return_val = None

        if data_key == KEYS.ALBUM:
            return_val = ingest_album_data(data)

        elif data_key == KEYS.ALBUMS:
            for a in data:
                ingest_album_data(a)
            # TODO deal with sorting here
            # TODO need some other way of deleting stale albums

        elif data_key == KEYS.ARTIST:
            return_val = ingest_artist_data(data)

        elif data_key == KEYS.ARTISTS:
            for a in data:
                ingest_artist_data(a)
            models.Artist.delete().where(
                models.Artist.id.not_in([a.id for a in data])
            ).execute()

        elif data_key == KEYS.COVER_ART_FILE:
            cache_info_extra["file_id"] = params[0]

            if data is not None:
                file_hash = compute_file_hash(data)
                cache_info_extra["file_hash"] = file_hash

                # Copy the actual cover art file
                shutil.copy(str(data), str(self.cover_art_dir.joinpath(file_hash)))

        elif data_key == KEYS.DIRECTORY:
            return_val = ingest_directory_data(data)

        elif data_key == KEYS.GENRES:
            for g in data:
                ingest_genre_data(g)

        elif data_key == KEYS.IGNORED_ARTICLES:
            models.IgnoredArticle.insert_many(
                map(lambda s: {"name": s}, data)
            ).on_conflict_replace().execute()
            models.IgnoredArticle.delete().where(
                models.IgnoredArticle.name.not_in(data)
            ).execute()

        elif data_key == KEYS.PLAYLIST_DETAILS:
            return_val = ingest_playlist(data)

        elif data_key == KEYS.PLAYLISTS:
            for p in data:
                ingest_playlist(p)
            models.Playlist.delete().where(
                models.Playlist.id.not_in([p.id for p in data])
            ).execute()

        elif data_key == KEYS.SEARCH_RESULTS:
            data = cast(API.SearchResult, data)
            for a in data._artists.values():
                ingest_artist_data(a)

            for a in data._albums.values():
                ingest_album_data(a)

            for s in data._songs.values():
                ingest_song_data(s)

            for p in data._playlists.values():
                ingest_playlist(p)

        elif data_key == KEYS.SONG:
            return_val = ingest_song_data(data)

        elif data_key == KEYS.SONG_FILE:
            cache_info_extra["file_id"] = params[0]

        elif data_key == KEYS.SONG_FILE_PERMANENT:
            data_key = KEYS.SONG_FILE
            cache_info_extra["cache_permanently"] = True

        # Set the cache info.
        now = datetime.now()
        cache_info, cache_info_created = models.CacheInfo.get_or_create(
            cache_key=data_key,
            params_hash=params_hash,
            defaults={
                "cache_key": data_key,
                "params_hash": params_hash,
                "last_ingestion_time": now,
                # If it's partial data, then set it to be invalid so it will only be
                # used in the event that the ground truth adapter can't service the
                # request.
                "valid": not partial,
                **cache_info_extra,
            },
        )
        if not cache_info_created:
            cache_info.last_ingestion_time = now
            cache_info.valid = not partial
            for k, v in cache_info_extra.items():
                setattr(cache_info, k, v)
            cache_info.save()

        # Special handling for Song
        if data_key == KEYS.SONG_FILE and data:
            path, buffer_filename = data

            if path:
                cache_info.path = path

            if buffer_filename:
                cache_info.file_hash = compute_file_hash(buffer_filename)

                # Copy the actual song file from the download buffer dir to the cache
                # dir.
                filename = self._compute_song_filename(cache_info)
                filename.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(str(buffer_filename), str(filename))

            cache_info.save()

            # song = models.Song.get_by_id(params[0])
            # song.file = cache_info
            # song.save()

        return return_val if return_val is not None else cache_info

    def _do_invalidate_data(
        self, data_key: CachingAdapter.CachedDataKey, params: Tuple[Any, ...],
    ):
        params_hash = util.params_hash(*params)
        logging.debug(
            f"_do_invalidate_data params={params} params_hash={params_hash} data_key={data_key}"  # noqa: 502
        )
        models.CacheInfo.update({"valid": False}).where(
            models.CacheInfo.cache_key == data_key,
            models.CacheInfo.params_hash == params_hash,
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
                self._do_invalidate_data(
                    CachingAdapter.CachedDataKey.COVER_ART_FILE, (song.cover_art,)
                )

    def _do_delete_data(
        self, data_key: CachingAdapter.CachedDataKey, params: Tuple[Any, ...],
    ):
        params_hash = util.params_hash(*params)
        logging.debug(
            f"_do_delete_data params={params} params_hash={params_hash} data_key={data_key}"  # noqa: 502
        )
        cache_info = models.CacheInfo.get_or_none(
            models.CacheInfo.cache_key == data_key,
            models.CacheInfo.params_hash == params_hash,
        )

        if data_key == CachingAdapter.CachedDataKey.COVER_ART_FILE:
            if cache_info:
                self.cover_art_dir.joinpath(str(cache_info.file_hash)).unlink(
                    missing_ok=True
                )

        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            # Delete the playlist and corresponding cover art.
            if playlist := models.Playlist.get_or_none(models.Playlist.id == params[0]):
                if cover_art := playlist.cover_art:
                    self._do_delete_data(
                        CachingAdapter.CachedDataKey.COVER_ART_FILE, (cover_art,),
                    )

                playlist.delete_instance()

        elif data_key == CachingAdapter.CachedDataKey.SONG_FILE:
            if cache_info:
                self._compute_song_filename(cache_info).unlink(missing_ok=True)

        cache_info.delete_instance()
