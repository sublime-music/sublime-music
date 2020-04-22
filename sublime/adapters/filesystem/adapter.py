import logging
import threading
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from queue import PriorityQueue
from time import sleep
from typing import Any, Dict, Optional, Sequence, Tuple

from sublime.adapters.api_objects import (Playlist, PlaylistDetails)

from . import models
from .. import CacheMissError, CachingAdapter, ConfigParamDescriptor


class FilesystemAdapter(CachingAdapter):
    """
    Defines an adapter which retrieves its data from the local filesystem.
    """
    # Configuration and Initialization Properties
    # =========================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        return {}

    @staticmethod
    def verify_configuration(
            config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {}

    def __init__(
        self,
        config: dict,
        data_directory: Path,
        is_cache: bool = False,
    ):
        self.data_directory = data_directory
        self.is_cache = is_cache
        database_filename = data_directory.joinpath('cache.db')
        models.database.init(database_filename)
        models.database.connect()

        with models.database.atomic():
            models.database.create_tables(models.ALL_TABLES)

    def shutdown(self):
        logging.info('Shutdown complete')

    # Usage Properties
    # =========================================================================
    can_be_cache: bool = True
    can_be_cached: bool = False

    # Availability Properties
    # =========================================================================
    can_service_requests: bool = True

    # Data Retrieval Methods
    # =========================================================================
    can_get_playlists: bool = True

    def get_playlists(self) -> Sequence[Playlist]:
        playlists = list(models.Playlist.select())
        if self.is_cache and len(playlists) == 0:
            # Determine if the adapter has ingested data for get_playlists
            # before. If not, cache miss.
            function_name = CachingAdapter.FunctionNames.GET_PLAYLISTS
            if not models.CacheInfo.get_or_none(
                    models.CacheInfo.query_name == function_name):
                raise CacheMissError()
        return playlists

    can_get_playlist_details: bool = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        playlist = models.Playlist.get_or_none(
            models.Playlist.id == playlist_id)
        if not playlist:
            if self.is_cache:
                raise CacheMissError()
            else:
                raise Exception(f'Playlist {playlist_id} does not exist.')

        return playlist

    # Data Ingestion Methods
    # =========================================================================
    @models.database.atomic()
    def ingest_new_data(
        self,
        function: 'CachingAdapter.FunctionNames',
        params: Tuple[Any, ...],
        data: Any,
    ):
        if not self.is_cache:
            raise Exception('FilesystemAdapter is not in cache mode')

        models.CacheInfo.insert(
            query_name=function,
            last_ingestion_time=datetime.now(),
        ).on_conflict_replace().execute()

        if function == CachingAdapter.FunctionNames.GET_PLAYLISTS:
            models.Playlist.insert_many(map(
                asdict, data)).on_conflict_replace().execute()
        elif function == CachingAdapter.FunctionNames.GET_PLAYLIST_DETAILS:
            playlist_data = asdict(data)
            playlist, created = models.Playlist.get_or_create(
                id=playlist_data['id'],
                defaults=playlist_data,
            )

            # Handle the songs.
            f = ('id', 'title', 'duration')
            playlist.songs = [
                models.Song.create(
                    **dict(filter(lambda kv: kv[0] in f, s.items())))
                for s in playlist_data['songs']
            ]

            # Update the values if the playlist already existed.
            if not created:
                for k, v in playlist_data.items():
                    setattr(playlist, k, v)

            playlist.save()
