import pytest

from sublime.adapters import Adapter, AdapterManager


def test_adapter_manager_singleton():
    AdapterManager.reset()
    AdapterManager.get_playlists()


def test_functions_not_implemented():
    with pytest.raises(NotImplementedError):
        Adapter(None)

    class MyAdapter(Adapter):
        def __init__(self, s: dict, c: bool = False):
            pass

        can_be_cache: bool = True

    with pytest.raises(NotImplementedError):
        adapter = MyAdapter({})
        adapter.can_service_requests

    with pytest.raises(NotImplementedError):
        adapter = MyAdapter({})
        adapter.ingest_new_data()


def test_override_bool():
    class MyAdapter(Adapter):
        def __init__(self, s: dict, c: bool = False):
            pass

        can_be_cache = True
        can_service_requests = True

    adapter = MyAdapter({})
    assert adapter.can_be_cache is True
    assert adapter.can_service_requests is True


def test_override_bool_with_property():
    class MyAdapter(Adapter):
        def __init__(self, s: dict, c: bool = False):
            pass

        @property
        def can_be_cache(self) -> bool:
            return True

        @property
        def can_service_requests(self) -> bool:
            return True

    adapter = MyAdapter({})
    assert adapter.can_be_cache is True
    assert adapter.can_service_requests is True
