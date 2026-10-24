from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

from xspacekit.auth.guest_auth import GuestAuth
from xspacekit.auth.x_session import XSession
from xspacekit.periscope.bootstrap import (
    bootstrap_periscope_access_chat_token,
    resolve_live_stream_seed_chat_token,
)
from unittest.mock import patch

from xspacekit.periscope.media_key_extract import extract_media_key


@dataclass
class _DummyResponse:
    payload: dict[str, Any]

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class _DummyHttp:
    def __init__(self) -> None:
        self.last_post: dict[str, Any] | None = None
        self._next_payload: dict[str, Any] | None = None

    def set_next_json(self, payload: dict[str, Any]) -> None:
        self._next_payload = payload

    def post(self, url: str, json: Any = None, headers: dict[str, str] | None = None) -> _DummyResponse:
        self.last_post = {"url": url, "json": json, "headers": headers}
        if self._next_payload is None:
            raise AssertionError("_DummyHttp: next payload not set")
        return _DummyResponse(self._next_payload)


class _DummyXSession:
    def graphql(self, query_id: str, operation: str, *, variables: dict[str, Any], features=None):
        _ = (query_id, operation, variables, features)
        return {"data": {"authenticate_periscope": "pcp_jwt_test"}}


def test_login_twitter_token_extracts_cookie() -> None:
    dummy_x = _DummyXSession()
    dummy_http = _DummyHttp()
    dummy_http.set_next_json({"cookie": "atu_cookie_test"})

    guest_auth = GuestAuth(x_session=dummy_x, session=dummy_http)

    atu_cookie = guest_auth.login_twitter_token(pcp_jwt="pcp_jwt_test")
    assert atu_cookie == "atu_cookie_test"
    assert dummy_http.last_post is not None
    assert "loginTwitterToken" in dummy_http.last_post["url"]


def test_access_chat_extracts_access_token() -> None:
    dummy_x = _DummyXSession()
    dummy_http = _DummyHttp()
    dummy_http.set_next_json({"access_token": "access_token_test"})

    guest_auth = GuestAuth(x_session=dummy_x, session=dummy_http)

    access_token = guest_auth.access_chat(chat_token="seed_chat_token", pscp_cookie="atu_cookie_test")
    assert access_token == "access_token_test"
    assert dummy_http.last_post is not None
    assert "accessChat" in dummy_http.last_post["url"]


def test_extract_media_key_prefers_media_key_over_m3u8_media_key() -> None:
    payload = {
        "m3u8_media_key": "m3u8_key",
        "nested": {
            "media_key": "   media_key_value   ",
        },
    }

    assert extract_media_key(payload) == "media_key_value"


def test_extract_media_key_falls_back_to_m3u8_media_key() -> None:
    payload = {
        "nested": [
            {"not_media": "x"},
            {"m3u8_media_key": "m3u8_key_value"},
        ]
    }

    assert extract_media_key(payload) == "m3u8_key_value"


def test_resolve_live_stream_seed_chat_token_json_payload() -> None:
    class _Resp:
        def __init__(self) -> None:
            self._json = {"chatToken": "seed_chat_token_test"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._json

        @property
        def text(self) -> str:
            return "unused"

    class _Client:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str, params: dict[str, Any], headers: dict[str, str]) -> _Resp:
            _ = (url, params, headers)
            return _Resp()

    class _DummyX(XSession):
        # Minimal graphql_headers surface for resolve_live_stream_seed_chat_token.
        def graphql_headers(self, *, extra=None):  # type: ignore[override]
            return {"authorization": "Bearer X", "x-csrf-token": "CT0", "Cookie": "auth_token=A; ct0=C; guest_id=G"}

    dummy_x = _DummyX.__new__(_DummyX)  # bypass XSession init

    with patch("httpx.Client", _Client):
        seed = resolve_live_stream_seed_chat_token(x_session=dummy_x, media_key="media_key_test")

    assert seed == "seed_chat_token_test"


def test_bootstrap_periscope_access_chat_token_composes_pscp_cookie_seed_and_access_chat() -> None:
    class _QueueHttp:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self._payloads: list[dict[str, Any]] = []

        def set_payloads(self, payloads: list[dict[str, Any]]) -> None:
            self._payloads = list(payloads)

        def post(self, url: str, json: Any = None, headers: dict[str, str] | None = None):
            self.calls.append({"url": url, "json": json, "headers": headers})
            if not self._payloads:
                raise AssertionError("_QueueHttp: no payloads left")
            return _DummyResponse(self._payloads.pop(0))

    class _DummyXSession2:
        def graphql(self, query_id: str, operation: str, *, variables: dict[str, Any], features=None):
            _ = (query_id, operation, variables, features)
            return {"data": {"authenticate_periscope": "pcp_jwt_test"}}

        def graphql_headers(self, *, extra=None):  # type: ignore[override]
            return {"authorization": "Bearer X", "x-csrf-token": "CT0", "Cookie": "auth_token=A; ct0=C; guest_id=G"}

    # 1) loginTwitterToken -> returns atu_cookie
    # 2) accessChat -> returns access_token
    dummy_http = _QueueHttp()
    dummy_http.set_payloads([
        {"cookie": "atu_cookie_test"},
        {"access_token": "access_token_test"},
    ])

    dummy_x = _DummyXSession2()
    guest_auth = GuestAuth(x_session=dummy_x, session=dummy_http)

    # Mock live_video_stream/status -> returns base64(json) with chatToken.
    import base64

    live_status_payload = {"chatToken": "seed_chat_token_test"}
    b64 = base64.b64encode(json.dumps(live_status_payload).encode("utf-8")).decode("utf-8")

    class _Resp2:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            # Force the base64/json fallback path in resolve_live_stream_seed_chat_token.
            raise ValueError("not json")

        @property
        def text(self) -> str:
            return b64

    class _Client2:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "_Client2":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str, params: dict[str, Any], headers: dict[str, str]) -> _Resp2:
            _ = (url, params, headers)
            return _Resp2()

    with patch("httpx.Client", _Client2):
        result = bootstrap_periscope_access_chat_token(
            x_session=dummy_x,
            guest_auth=guest_auth,
            media_key="media_key_test",
        )

    assert result.pscp_cookie == "atu_cookie_test"
    assert result.seed_chat_token == "seed_chat_token_test"
    assert result.access_chat_token == "access_token_test"

    assert len(dummy_http.calls) == 2
    assert "loginTwitterToken" in dummy_http.calls[0]["url"]
    assert "accessChat" in dummy_http.calls[1]["url"]
    assert dummy_http.calls[1]["json"]["chat_token"] == "seed_chat_token_test"
    assert dummy_http.calls[1]["json"]["cookie"] == "atu_cookie_test"
