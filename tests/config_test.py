import shutil
from pathlib import Path

import pytest

from sublime_music.adapters import ConfigurationStore
from sublime_music.adapters.filesystem import FilesystemAdapter
from sublime_music.adapters.subsonic import SubsonicAdapter
from sublime_music.config import AppConfiguration, ProviderConfiguration


@pytest.fixture
def config_filename(tmp_path: Path):
    yield tmp_path.joinpath("config.json")


@pytest.fixture
def cwd():
    yield Path(__file__).parent


def test_config_default_cache_location():
    config = AppConfiguration()
    assert config.cache_location == Path("~/.local/share/sublime-music").expanduser()


def test_server_property(tmp_path: Path):
    config = AppConfiguration()
    config.cache_location = tmp_path
    provider = ProviderConfiguration(
        id="1",
        name="foo",
        ground_truth_adapter_type=SubsonicAdapter,
        ground_truth_adapter_config=ConfigurationStore(),
    )
    config.providers["1"] = provider
    assert config.provider is None
    config.current_provider_id = "1"
    assert config.provider == provider

    assert config._state_file_location == tmp_path.joinpath("1", "state.pickle")


def test_json_load_unload(config_filename: Path, tmp_path: Path):
    ConfigurationStore.MOCK = True
    subsonic_config_store = ConfigurationStore(username="test")
    subsonic_config_store.set_secret("password", "testpass")
    original_config = AppConfiguration(
        providers={
            "1": ProviderConfiguration(
                id="1",
                name="foo",
                ground_truth_adapter_type=SubsonicAdapter,
                ground_truth_adapter_config=subsonic_config_store,
                caching_adapter_type=FilesystemAdapter,
                caching_adapter_config=ConfigurationStore(),
            )
        },
        current_provider_id="1",
        filename=config_filename,
    )
    original_config.cache_location = tmp_path

    original_config.save()

    loaded_config = AppConfiguration.load_from_file(config_filename)

    assert original_config.version == loaded_config.version
    assert original_config.providers == loaded_config.providers
    assert original_config.provider == loaded_config.provider


def test_config_migrate_v5_to_v6(config_filename: Path, cwd: Path):
    shutil.copyfile(str(cwd.joinpath("mock_data/config-v5.json")), str(config_filename))
    app_config = AppConfiguration.load_from_file(config_filename)
    app_config.migrate()

    assert app_config.version == 6
    assert app_config.player_config == {
        "Local Playback": {"Replay Gain": "track"},
        "Chromecast": {
            "Serve Local Files to Chromecasts on the LAN": True,
            "LAN Server Port Number": 6969,
        },
    }
    app_config.save()
    app_config2 = AppConfiguration.load_from_file(config_filename)
    assert app_config == app_config2
