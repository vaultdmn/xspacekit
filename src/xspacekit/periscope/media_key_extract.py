from __future__ import annotations

from typing import Any


def extract_media_key(obj: Any) -> str | None:
    """Best-effort extraction of X Spaces media_key from an AudioSpaceById payload.

    Heuristic:
    - Prefer `media_key` over `m3u8_media_key`.
    - Both keys may appear at different nesting depths; we search the entire
      object and then pick the highest-priority key we found.
    """

    if obj is None:
        return None

    # Common keys observed across captures.
    preferred_keys = ["media_key", "m3u8_media_key"]

    found: dict[str, str] = {}

    stack: list[Any] = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k in preferred_keys:
                if k in found:
                    continue
                v = cur.get(k)
                if isinstance(v, str) and v.strip():
                    found[k] = v.strip()

            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)

    for k in preferred_keys:
        if k in found:
            return found[k]

    return None
