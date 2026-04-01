"""
In-memory cache: {caller: version_id} for the currently deployed prompt version.
Warmed at startup from DB. Updated on every deploy action.
"""
import threading

_cache: dict[str, str] = {}
_lock = threading.Lock()


def warm_cache(deployed_rows: list[dict]) -> None:
    with _lock:
        _cache.clear()
        for row in deployed_rows:
            _cache[row["caller"]] = row["id"]


def get_version_id(caller: str) -> str | None:
    with _lock:
        return _cache.get(caller)


def set_version_id(caller: str, version_id: str) -> None:
    with _lock:
        _cache[caller] = version_id


def remove_caller(caller: str) -> None:
    with _lock:
        _cache.pop(caller, None)