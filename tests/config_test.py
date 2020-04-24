import os
from dataclasses import asdict
from pathlib import Path

import yaml

from sublime.config import AppConfiguration, ReplayGainType, ServerConfiguration


def test_config_default_cache_location():
    config = AppConfiguration()
    assert config.cache_location == os.path.expanduser("~/.local/share/sublime-music")


def test_server_property():
    config = AppConfiguration()
    server = ServerConfiguration(name="foo", server_address="bar", username="baz")
    config.servers.append(server)
    assert config.server is None
    config.current_server_index = 0
    assert asdict(config.server) == asdict(server)

    expected_state_file_location = Path("~/.local/share").expanduser()
    expected_state_file_location = expected_state_file_location.joinpath(
        "sublime-music", "6df23dc03f9b54cc38a0fc1483df6e21", "state.pickle",
    )
    assert config.state_file_location == expected_state_file_location


def test_yaml_load_unload():
    config = AppConfiguration()
    server = ServerConfiguration(name="foo", server_address="bar", username="baz")
    config.servers.append(server)
    config.current_server_index = 0

    yamlified = yaml.dump(asdict(config))
    unyamlified = yaml.load(yamlified, Loader=yaml.CLoader)
    deserialized = AppConfiguration(**unyamlified)

    # Make sure that the config and each of the servers gets loaded in properly
    # into the dataclass objects.
    assert asdict(config) == asdict(deserialized)
    assert type(deserialized.replay_gain) == ReplayGainType
    for i, server in enumerate(deserialized.servers):
        assert asdict(config.servers[i]) == asdict(server)


def test_config_migrate():
    config = AppConfiguration()
    server = ServerConfiguration(
        name="Test", server_address="https://test.host", username="test"
    )
    config.servers.append(server)
    config.migrate()

    assert config.version == 3
    for server in config.servers:
        server.version == 0


def test_replay_gain_enum():
    for rg in (ReplayGainType.NO, ReplayGainType.TRACK, ReplayGainType.ALBUM):
        assert rg == ReplayGainType.from_string(rg.as_string())
