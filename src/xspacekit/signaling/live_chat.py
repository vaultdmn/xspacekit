from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LiveChatEvent:
    ts: str | None
    raw: dict[str, Any]


class LiveChatClient:
    """Client for X live-chat NDJSON feed.

    The feed is delivered as `application/x-ndjson`.
    """

    def __init__(self, *, fetch: Any | None = None):
        # `fetch` is dependency injection for tests; it should behave like `httpx.Client`.
        self._client = fetch or httpx.Client(timeout=60.0)

    def iter_events(self, *, url: str, auth_headers: dict[str, str]) -> Iterator[LiveChatEvent]:
        headers = dict(auth_headers)
        headers.setdefault("Accept", "application/x-ndjson, application/json")

        with self._client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # Best-effort: keep raw event.
                    yield LiveChatEvent(ts=None, raw={"_raw": line})
                    continue

                if isinstance(obj, dict):
                    yield LiveChatEvent(ts=obj.get("ts"), raw=obj)
                else:
                    yield LiveChatEvent(ts=None, raw={"_raw": obj})
