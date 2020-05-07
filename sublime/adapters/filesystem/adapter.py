import hashlib
import json
import logging
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from sublime.adapters.api_objects import Playlist, PlaylistDetails

from . import models
from .. import CacheMissError, CachingAdapter, ConfigParamDescriptor


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
        self.is_cache = is_cache
        self.db_write_lock: threading.Lock = threading.Lock()
        database_filename = data_directory.joinpath("cache.db")
        models.database.init(database_filename)
        models.database.connect()

        with self.db_write_lock, models.database.atomic():
            models.database.create_tables(models.ALL_TABLES)

    def shutdown(self):
        logging.info("Shutdown complete")

    # Usage and Availability Properties
    # ==================================================================================
    can_be_cached: bool = False  # Can't be cached (there's no need).
    can_service_requests: bool = True  # Can always be used to service requests.

    # Data Helper Methods
    # ==================================================================================
    def _params_hash(self, *params: Any) -> str:
        return hashlib.sha1(bytes(json.dumps(params), "utf8")).hexdigest()

    # Data Retrieval Methods
    # ==================================================================================
    can_get_playlists: bool = True

    def get_playlists(self) -> Sequence[Playlist]:
        playlists = list(models.Playlist.select())
        if self.is_cache:
            # Determine if the adapter has ingested data for get_playlists before, and
            # if not, cache miss.
            cache_key = CachingAdapter.CachedDataKey.PLAYLISTS
            if not models.CacheInfo.get_or_none(
                models.CacheInfo.cache_key == cache_key
            ):
                raise CacheMissError(partial_data=playlists)
        return playlists

    can_get_playlist_details: bool = True

    def get_playlist_details(self, playlist_id: str) -> PlaylistDetails:
        playlist = models.Playlist.get_or_none(models.Playlist.id == playlist_id)

        # Handle the case that this is the ground truth adapter.
        if not self.is_cache:
            if not playlist:
                raise Exception(f"Playlist {playlist_id} does not exist.")
            return playlist

        # If we haven't ingested data for this playlist before, raise a CacheMissError
        # with the partial playlist data.
        cache_key = CachingAdapter.CachedDataKey.PLAYLIST_DETAILS
        cache_info = models.CacheInfo.get_or_none(
            models.CacheInfo.cache_key == cache_key,
            params_hash=self._params_hash(playlist_id),
        )
        if not cache_info:
            raise CacheMissError(partial_data=playlist)

        return playlist

    # Data Ingestion Methods
    # ==================================================================================
    def ingest_new_data(
        self,
        data_key: "CachingAdapter.CachedDataKey",
        params: Tuple[Any, ...],
        data: Any,
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_ingest_new_data(data_key, params, data)

    def invalidate_data(
        self, function: "CachingAdapter.CachedDataKey", params: Tuple[Any, ...]
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_invalidate_data(function, params)

    def delete_data(
        self, function: "CachingAdapter.CachedDataKey", params: Tuple[Any, ...]
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode!"

        # Wrap the actual ingestion function in a database lock, and an atomic
        # transaction.
        with self.db_write_lock, models.database.atomic():
            self._do_delete_data(function, params)

    def _do_ingest_new_data(
        self,
        data_key: "CachingAdapter.CachedDataKey",
        params: Tuple[Any, ...],
        data: Any,
    ):
        models.CacheInfo.insert(
            cache_key=data_key,
            params_hash=self._params_hash(*params),
            last_ingestion_time=datetime.now(),
        ).on_conflict_replace().execute()

        if data_key == CachingAdapter.CachedDataKey.PLAYLISTS:
            models.Playlist.insert_many(
                map(asdict, data)
            ).on_conflict_replace().execute()
            models.Playlist.delete().where(
                models.Playlist.id.not_in([p.id for p in data])
            ).execute()
        elif data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            playlist_data = asdict(data)
            playlist, playlist_created = models.Playlist.get_or_create(
                id=playlist_data["id"], defaults=playlist_data
            )

            # Handle the songs.
            songs = []
            for song_data in playlist_data["songs"]:
                song, song_created = models.Song.get_or_create(
                    id=song_data["id"], defaults=song_data
                )

                keys = ("title", "duration", "path")
                if not song_created:
                    for key in keys:
                        setattr(song, key, song_data[key])
                    song.save()

                songs.append(song)

            playlist.songs = songs
            del playlist_data["songs"]

            # Update the values if the playlist already existed.
            if not playlist_created:
                for k, v in playlist_data.items():
                    setattr(playlist, k, v)

            playlist.save()

    def _do_invalidate_data(
        self, data_key: "CachingAdapter.CachedDataKey", params: Tuple[Any, ...],
    ):
        if data_key == CachingAdapter.CachedDataKey.PLAYLISTS:
            models.CacheInfo.delete().where(
                models.CacheInfo.cache_key == data_key
            ).execute()

    def _do_delete_data(
        self, data_key: "CachingAdapter.CachedDataKey", params: Tuple[Any, ...],
    ):
        if data_key == CachingAdapter.CachedDataKey.PLAYLIST_DETAILS:
            models.Playlist.delete().where(models.Playlist.id == params[0]).execute()
            models.CacheInfo.delete().where(
                models.CacheInfo.cache_key == data_key,
                models.CacheInfo.params_hash == self._params_hash(params),
            ).execute()
