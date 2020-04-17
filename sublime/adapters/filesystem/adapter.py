from typing import Any, Dict, List, Tuple
from pathlib import Path

from sublime.adapters.api_objects import (Playlist, PlaylistDetails)
from .. import CachingAdapter


class FilesystemAdapter(CachingAdapter):
    """
    Defines an adapter which retrieves its data from the local filesystem.
    """

    # Configuration and Initialization Properties
    # =========================================================================
    @staticmethod
    def get_config_parameters() -> List[Tuple[str, str]]:  # TODO fix
        return []

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, str]:
        return {}

    def __init__(
        self,
        config: dict,
        data_directory: Path,
        is_cache: bool = False,
    ):
        pass

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
        return []

    can_get_playlist_details: bool = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        raise NotImplementedError()

    # Data Ingestion Methods
    # =========================================================================
    def ingest_new_data(self):  # TODO: actually ingest data
        pass
