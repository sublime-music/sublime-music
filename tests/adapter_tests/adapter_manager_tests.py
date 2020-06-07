from pathlib import Path
from time import sleep

import pytest

from sublime.adapters import AdapterManager, ConfigurationStore, Result, SearchResult
from sublime.adapters.filesystem import FilesystemAdapter
from sublime.adapters.subsonic import api_objects as SubsonicAPI, SubsonicAdapter
from sublime.config import AppConfiguration, ProviderConfiguration


@pytest.fixture
def adapter_manager(tmp_path: Path):
    subsonic_config_store = ConfigurationStore(
        server_address="https://subsonic.example.com",
        username="test",
        verify_cert=True,
    )
    subsonic_config_store.set_secret("password", "testpass")

    config = AppConfiguration(
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
        cache_location=tmp_path,
    )
    AdapterManager.reset(config, lambda *a: None)
    yield
    AdapterManager.shutdown()


def test_result_immediate():
    result = Result(42)
    assert result.data_is_available
    assert result.result() == 42


def test_result_immediate_callback():
    callback_called = True

    def check_done_callback(f: Result):
        nonlocal callback_called
        assert f.result() == 42
        callback_called = True

    result = Result(42)
    result.add_done_callback(check_done_callback)
    assert callback_called


def test_result_future():
    def resolve_later() -> int:
        sleep(0.1)
        return 42

    result = Result(resolve_later)
    assert not result.data_is_available
    assert result.result() == 42
    assert result.data_is_available


def test_result_future_callback():
    def resolve_later() -> int:
        sleep(0.1)
        return 42

    check_done = False

    def check_done_callback(f: Result):
        nonlocal check_done
        assert result.data_is_available
        assert f.result() == 42
        check_done = True

    result = Result(resolve_later)
    result.add_done_callback(check_done_callback)

    # Should take much less than 1 seconds to complete. If the assertion fails, then the
    # check_done_callback failed.
    t = 0
    while not check_done:
        assert t < 1
        t += 0.1
        sleep(0.1)


def test_default_value():
    def resolve_fail() -> int:
        sleep(0.1)
        raise Exception()

    result = Result(resolve_fail, default_value=42)
    assert not result.data_is_available
    assert result.result() == 42
    assert result.data_is_available


def test_cancel():
    def resolve_later() -> int:
        sleep(0.1)
        return 42

    cancel_called = False

    def on_cancel():
        nonlocal cancel_called
        cancel_called = True

    result = Result(resolve_later, on_cancel=on_cancel)
    result.cancel()
    assert cancel_called
    assert not result.data_is_available
    with pytest.raises(Exception):
        result.result()


def test_get_song_details(adapter_manager: AdapterManager):
    # song = AdapterManager.get_song_details("1")
    # print(song)
    # assert 0
    # TODO
    pass


def test_search_result_sort():
    search_results1 = SearchResult(query="foo")
    search_results1.add_results(
        "artists",
        [
            # boo != foo so low match rate
            SubsonicAPI.ArtistAndArtistInfo(id=str(i), name=f"boo{i}")
            for i in range(30)
        ],
    )

    search_results2 = SearchResult(query="foo")
    search_results1.add_results(
        "artists",
        [
            # foo == foo, so high match rate
            SubsonicAPI.ArtistAndArtistInfo(id=str(i), name=f"foo{i}")
            for i in range(30)
        ],
    )

    # After unioning, the high match rate ones should be first, and only the top 20
    # should be included.
    search_results1.update(search_results2)
    assert [a.name for a in search_results1.artists] == [f"foo{i}" for i in range(20)]


def test_search_result_update():
    search_results1 = SearchResult(query="foo")
    search_results1.add_results(
        "artists",
        [
            SubsonicAPI.ArtistAndArtistInfo(id="1", name="foo"),
            SubsonicAPI.ArtistAndArtistInfo(id="2", name="another foo"),
        ],
    )

    search_results2 = SearchResult(query="foo")
    search_results2.add_results(
        "artists", [SubsonicAPI.ArtistAndArtistInfo(id="3", name="foo2")],
    )

    search_results1.update(search_results2)
    assert [a.name for a in search_results1.artists] == ["foo", "another foo", "foo2"]


def test_search(adapter_manager: AdapterManager):
    # TODO
    return
    results = []

    # TODO ingest data

    def search_callback(result: SearchResult):
        results.append((result.artists, result.albums, result.songs, result.playlists))

    AdapterManager.search("ohea", search_callback=search_callback).result()

    # TODO test getting results from the server and updating using that
    while len(results) < 1:
        sleep(0.1)

    assert len(results) == 1
