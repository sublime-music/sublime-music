from pathlib import Path

import pytest

from sublime.adapters import ConfigurationStore
from sublime.adapters.filesystem import FilesystemAdapter
from sublime.adapters.subsonic import SubsonicAdapter
from sublime.config import AppConfiguration, ProviderConfiguration, ReplayGainType


@pytest.fixture
def config_filename(tmp_path: Path):
    yield tmp_path.joinpath("config.json")


def test_config_default_cache_location():
    config = AppConfiguration()
    assert config.cache_location == Path("~/.local/share/sublime-music").expanduser()


def test_server_property():
    config = AppConfiguration()
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

    expected_state_file_location = Path("~/.local/share").expanduser()
    expected_state_file_location = expected_state_file_location.joinpath(
        "sublime-music", "1", "state.pickle",
    )
    assert config._state_file_location == expected_state_file_location


def test_json_load_unload(config_filename: Path):
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

    original_config.save()

    loaded_config = AppConfiguration.load_from_file(config_filename)

    assert original_config.version == loaded_config.version
    assert original_config.providers == loaded_config.providers
    assert original_config.provider == loaded_config.provider


def test_config_migrate(config_filename: Path):
    config = AppConfiguration(
        providers={
            "1": ProviderConfiguration(
                id="1",
                name="foo",
                ground_truth_adapter_type=SubsonicAdapter,
                ground_truth_adapter_config=ConfigurationStore(),
            )
        },
        current_provider_id="1",
        filename=config_filename,
    )
    config.migrate()

    assert config.version == 5


def test_replay_gain_enum():
    for rg in (ReplayGainType.NO, ReplayGainType.TRACK, ReplayGainType.ALBUM):
        assert rg == ReplayGainType.from_string(rg.as_string())
