import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from sublime.adapters.api_objects import (Playlist, PlaylistDetails)
from .. import CachingAdapter, ConfigParamDescriptor, CacheMissError


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
        self.database_filename = data_directory.joinpath('.cache_meta.db')
        database_connection = sqlite3.connect(
            self.database_filename,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )

        # TODO extract this out eventually
        c = database_connection.cursor()
        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='playlists';"
        )
        if not c.fetchone():
            c.execute(
                """
                CREATE TABLE playlists (
                    id TEXT NOT NULL UNIQUE PRIMARY KEY,
                    name TEXT NOT NULL,
                    song_count INTEGER,
                    duration INTEGER,
                    created INTEGER,
                    changed INTEGER,
                    comment TEXT,
                    owner TEXT, -- TODO convert to a a FK
                    public INT,
                    cover_art TEXT -- TODO convert to a FK
                )
                """)

        c.close()

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

    def get_playlists(self) -> List[Playlist]:
        database_connection = sqlite3.connect(
            self.database_filename,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        with database_connection:
            playlists = database_connection.execute(
                """
                SELECT * from playlists
                """).fetchall()
            return [Playlist(*p) for p in playlists]

        raise CacheMissError()

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
        database_connection = sqlite3.connect(
            self.database_filename,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        with database_connection:
            if function_name == 'get_playlists':
                database_connection.executemany(
                    """
                    INSERT OR IGNORE INTO playlists (id, name, song_count, duration, created, comment, owner, public, cover_art)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO
                    UPDATE SET id=?, name=?, song_count=?, duration=?, created=?, comment=?, owner=?, public=?, cover_art=?;
                    """, [
                        (
                            p.id, p.name, p.songCount, p.duration, p.created,
                            p.comment, p.owner, p.public, p.coverArt, p.id,
                            p.name, p.songCount, p.duration, p.created,
                            p.comment, p.owner, p.public, p.coverArt)
                        for p in data
                    ])
