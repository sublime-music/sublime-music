import hashlib
import json
from typing import Any

from sublime.adapters import AlbumSearchQuery


def params_hash(*params: Any) -> str:
    # Special handling for AlbumSearchQuery objects.
    # TODO figure out if I can optimize this
    if len(params) > 0 and isinstance(params[0], AlbumSearchQuery):
        params = (hash(params[0]), *params[1:])
    return hashlib.sha1(bytes(json.dumps(params), "utf8")).hexdigest()
