import hashlib
import json
from typing import Any


def params_hash(*params: Any) -> str:
    return hashlib.sha1(bytes(json.dumps(params), "utf8")).hexdigest()
