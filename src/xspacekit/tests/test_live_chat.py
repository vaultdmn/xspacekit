from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from xspacekit.signaling.live_chat import LiveChatClient


@dataclass
class _DummyResponse:
    lines: list[str | bytes]

    def raise_for_status(self) -> None:  # noqa: D401
        return None

    def iter_lines(self) -> Iterator[str | bytes]:
        yield from self.lines


class _StreamCtx:
    def __init__(self, resp: _DummyResponse):
        self._resp = resp

    def __enter__(self) -> _DummyResponse:
        return self._resp

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _DummyClient:
    def __init__(self, *, lines: list[str | bytes]):
        self._lines = lines

    def stream(self, method: str, url: str, headers: dict[str, str]):
        _ = (method, url, headers)
        return _StreamCtx(_DummyResponse(lines=self._lines))


def test_iter_events_parses_ndjson_and_handles_invalid_json() -> None:
    lines: list[str | bytes] = [
        '{"ts":"t1","msg":"hello"}',
        b'{"ts":"t2","msg":"world"}',
        "not-json",
    ]

    client = LiveChatClient(fetch=_DummyClient(lines=lines))

    events = list(
        client.iter_events(
            url="https://api.x.com/live-chat?broadcastId=b&sessionId=s",
            auth_headers={"authorization": "Bearer X", "x-csrf-token": "CT0"},
        )
    )

    assert [e.ts for e in events] == ["t1", "t2", None]
    assert events[0].raw["msg"] == "hello"
    assert events[1].raw["msg"] == "world"
    assert events[2].raw["_raw"] == "not-json"
