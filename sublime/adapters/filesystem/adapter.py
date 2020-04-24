import hashlib
import json
import logging
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
    # =========================================================================
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
        database_filename = data_directory.joinpath("cache.db")
        models.database.init(database_filename)
        models.database.connect()

        with models.database.atomic():
            models.database.create_tables(models.ALL_TABLES)

    def shutdown(self):
        logging.info("Shutdown complete")

    # Usage Properties
    # =========================================================================
    can_be_cache: bool = True
    can_be_cached: bool = False

    # Availability Properties
    # =========================================================================
    can_service_requests: bool = True

    # Data Helper Methods
    # =========================================================================
    def _params_hash(self, *params: Any) -> str:
        return hashlib.sha1(bytes(json.dumps(params), "utf8")).hexdigest()

    # Data Retrieval Methods
    # =========================================================================
    can_get_playlists: bool = True

    def get_playlists(self) -> Sequence[Playlist]:
        playlists = list(models.Playlist.select())
        if self.is_cache and len(playlists) == 0:
            # This does not necessary mean that we have a cache miss. It could
            # just mean that the list of playlists is actually empty. Determine
            # if the adapter has ingested data for get_playlists before, and if
            # not, cache miss.
            function_name = CachingAdapter.FunctionNames.GET_PLAYLISTS
            if not models.CacheInfo.get_or_none(
                models.CacheInfo.query_name == function_name
            ):
                raise CacheMissError()
        return playlists

    can_get_playlist_details: bool = True

    def get_playlist_details(self, playlist_id: str,) -> PlaylistDetails:
        playlist = models.Playlist.get_or_none(models.Playlist.id == playlist_id)
        if not playlist and not self.is_cache:
            raise Exception(f"Playlist {playlist_id} does not exist.")

        # If we haven't ingested data for this playlist before, raise a
        # CacheMissError with the partial playlist data.
        function_name = CachingAdapter.FunctionNames.GET_PLAYLIST_DETAILS
        cache_info = models.CacheInfo.get_or_none(
            models.CacheInfo.query_name == function_name,
            params_hash=self._params_hash(playlist_id),
        )
        if not cache_info:
            raise CacheMissError(partial_data=playlist)

        return playlist

    # Data Ingestion Methods
    # =========================================================================
    @models.database.atomic()
    def ingest_new_data(
        self,
        function: "CachingAdapter.FunctionNames",
        params: Tuple[Any, ...],
        data: Any,
    ):
        assert self.is_cache, "FilesystemAdapter is not in cache mode"

        models.CacheInfo.insert(
            query_name=function,
            params_hash=self._params_hash(*params),
            last_ingestion_time=datetime.now(),
        ).on_conflict_replace().execute()

        if function == CachingAdapter.FunctionNames.GET_PLAYLISTS:
            models.Playlist.insert_many(
                map(asdict, data)
            ).on_conflict_replace().execute()
        elif function == CachingAdapter.FunctionNames.GET_PLAYLIST_DETAILS:
            playlist_data = asdict(data)
            playlist, playlist_created = models.Playlist.get_or_create(
                id=playlist_data["id"], defaults=playlist_data,
            )

            # Handle the songs.
            songs = []
            for index, song_data in enumerate(playlist_data["songs"]):
                # args = dict(filter(lambda kv: kv[0] in f, song_data.items()))
                song_data["index"] = index
                song, song_created = models.Song.get_or_create(
                    id=song_data["id"], defaults=song_data
                )

                keys = ("title", "duration", "path", "index")
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
