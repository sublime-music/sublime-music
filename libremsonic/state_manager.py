from typing import List, Any

from .config import get_config, save_config, AppConfiguration

from .server.api_objects import Child


class ApplicationState:
    config: AppConfiguration = AppConfiguration.get_default_configuration()
    current_song: Child  # TODO fix
    config_file: str
    playing: bool = False
    song_progress: float = 0.0
    up_next: List[Any]  # TODO should be song
    volume: int = 100

    def load_config(self):
        self.config = get_config(self.config_file)

    def save_config(self):
        save_config(self.config, self.config_file)
