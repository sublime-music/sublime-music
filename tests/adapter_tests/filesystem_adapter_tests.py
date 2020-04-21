import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

import pytest

from sublime.adapters.filesystem import (
    models,
    FilesystemAdapter,
)

MOCK_DATA_FILES = Path(__file__).parent.joinpath('mock_data')


@pytest.fixture
def adapter(tmp_path: Path):
    adapter = FilesystemAdapter({}, tmp_path)
    yield adapter
    adapter.shutdown()


@pytest.fixture
def cache_adapter(tmp_path: Path):
    adapter = FilesystemAdapter({}, tmp_path, is_cache=True)
    yield adapter
    adapter.shutdown()


def mock_data_files(
        request_name: str,
        mode: str = 'r',
) -> Generator[Tuple[Path, Any], None, None]:
    """
    Yields all of the files in the mock_data directory that start with
    ``request_name``.
    """
    for file in MOCK_DATA_FILES.iterdir():
        if file.name.split('-')[0] in request_name:
            with open(file, mode) as f:
                yield file, f.read()


def test_get_playlists(adapter: FilesystemAdapter, tmp_path: Path):
    assert adapter.get_playlists() == []
