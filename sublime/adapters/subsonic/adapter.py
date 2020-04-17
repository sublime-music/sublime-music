from typing import Any, Dict, List, Tuple
from pathlib import Path

from sublime.adapters.api_objects import (Playlist, PlaylistDetails)
from .. import Adapter


class SubsonicAdapter(Adapter):
    """
    Defines an adapter which retrieves its data from a Subsonic server
    """
    # Configuration and Initialization Properties
    # =========================================================================
    @staticmethod
    def get_config_parameters() -> List[Tuple[str, str]]:  # TODO fix
        return []

    @staticmethod
    def verify_configuration(config: Dict[str, Any]) -> Dict[str, str]:
        return {}

    def __init__(self, config: dict, data_directory: Path):
        pass

    # Availability Properties
    # =========================================================================
    @property
    def can_service_requests(self) -> bool:
        # TODO
        return True

    # Data Retrieval Methods
    # =========================================================================
    can_get_playlists = True

    def get_playlists(self) -> List[Playlist]:
        return []

    can_get_playlist_details = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        raise NotImplementedError()
