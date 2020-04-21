import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Sequence, Optional, Tuple
from time import sleep

from playhouse.sqliteq import SqliteQueueDatabase

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
        logging.info('Opening connection to the database.')
        database_filename = data_directory.joinpath('cache.db')
        models.database.initialize(
            SqliteQueueDatabase(database_filename, autorollback=True))
        models.database.connect()
        models.database.create_tables(models.ALL_TABLES)
        sleep(1)
        assert len(models.database.get_tables()) > 0

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
        if len(playlists) == 0:  # TODO not necessarily a cache miss
            raise CacheMissError()
        return playlists

    can_get_playlist_details: bool = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        raise NotImplementedError()

    # Data Ingestion Methods
    # =========================================================================
    def ingest_new_data(
        self,
        function_name: str,
        params: Tuple[Any, ...],
        data: Any,
    ):
        if function_name == 'get_playlists':
            (
                models.Playlist.insert_many(
                    map(lambda p: models.Playlist(**asdict(p)),
                        data)).on_conflict_replace())
