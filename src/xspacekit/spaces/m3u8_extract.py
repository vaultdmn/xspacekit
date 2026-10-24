from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _iter_values(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        return obj.values()
    if isinstance(obj, list):
        return obj
    return []


def find_first_m3u8_url(obj: Any) -> str | None:
    """Best-effort scan for a .m3u8 URL within a JSON-like object.

    This is heuristic: it recursively searches dict/list values and returns
    the first string that looks like an m3u8 URL.
    """

    if isinstance(obj, str):
        s = obj.strip()
        if not s:
            return None
        if ".m3u8" in s or "/hls/" in s:
            return s
        return None

    if isinstance(obj, dict):
        for v in obj.values():
            hit = find_first_m3u8_url(v)
            if hit is not None:
                return hit

    if isinstance(obj, list):
        for item in obj:
            hit = find_first_m3u8_url(item)
            if hit is not None:
                return hit

    return None
