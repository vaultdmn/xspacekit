from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from xspacekit.auth.guest_auth import GuestAuth
from xspacekit.auth.x_session import XSession


@dataclass(frozen=True)
class PeriscopeBootstrapResult:
    """Derived credentials needed for audiospace join/request.

    This is based on the observed browser flow:
    - AuthenticatePeriscope (X GraphQL) -> proxsee loginTwitterToken -> pscp cookie
    - live_video_stream/status -> chatToken seed
    - accessChat (proxsee) -> access_token (join-ready chat_token)

    We do not expose or log raw tokens beyond what callers explicitly return.
    """

    pscp_cookie: str
    seed_chat_token: str
    access_chat_token: str


# X GraphQL: observed query id for AuthenticatePeriscope in captured HARs.
_AUTHENTICATE_PERISCOPE_QUERY_ID = "r7VUmxbfqNkx7uwjgONSNw"


def _decode_b64_json(text: str) -> dict[str, Any]:
    # The response is base64(json)
    raw = base64.b64decode(text)
    return json.loads(raw.decode("utf-8", errors="replace"))


def bootstrap_periscope_pscp_cookie(*, x_session: XSession, guest_auth: GuestAuth) -> str:
    """Obtain the proxsee cookie used for authorizeToken/turnServers and accessChat."""

    auth = x_session.graphql(
        _AUTHENTICATE_PERISCOPE_QUERY_ID,
        "AuthenticatePeriscope",
        variables={},
    )

    try:
        pcp_jwt = auth["data"]["authenticate_periscope"]
    except (KeyError, TypeError) as e:
        raise SystemExit("periscope bootstrap: unexpected AuthenticatePeriscope response shape") from e

    return guest_auth.login_twitter_token(pcp_jwt=pcp_jwt)


def resolve_live_stream_seed_chat_token(*, x_session: XSession, media_key: str) -> str:
    """Resolve the seed chatToken from X's live_video_stream/status endpoint."""

    import httpx

    url = f"https://x.com/i/api/1.1/live_video_stream/status/{media_key}"
    params = {
        "client": "web",
        "use_syndication_guest_id": "false",
        "cookie_set_host": "x.com",
    }

    # Reuse the cookie/CSRF/Bearer headers used for GraphQL.
    headers = x_session.graphql_headers()

    with httpx.Client(timeout=30.0) as c:
        r = c.get(url, params=params, headers=headers)
        r.raise_for_status()

        # HAR shows: response is base64(json), but implementations vary.
        # Try JSON first; if that fails, fall back to treating the body as
        # a base64-encoded string.
        resp_json: Any | None = None
        try:
            resp_json = r.json()
        except Exception:
            resp_json = None

        if isinstance(resp_json, dict):
            if "chatToken" in resp_json and isinstance(resp_json["chatToken"], str):
                return resp_json["chatToken"]

        # If it wasn't JSON, treat the response body as a base64 string.
        # If it was JSON but not a dict, coerce it to string.
        text: str
        if isinstance(resp_json, str):
            text = resp_json
        else:
            text = r.text

        decoded = _decode_b64_json(text)
        chat_token = decoded.get("chatToken")
        if not isinstance(chat_token, str) or not chat_token:
            raise SystemExit("periscope bootstrap: missing chatToken in live_video_stream/status")
        return chat_token


def bootstrap_periscope_access_chat_token(
    *,
    x_session: XSession,
    guest_auth: GuestAuth,
    media_key: str,
) -> PeriscopeBootstrapResult:
    """Derive pscp cookie + seed chatToken + join-ready access_chat_token."""

    pscp_cookie = bootstrap_periscope_pscp_cookie(x_session=x_session, guest_auth=guest_auth)
    seed_chat_token = resolve_live_stream_seed_chat_token(x_session=x_session, media_key=media_key)
    access_chat_token = guest_auth.access_chat(chat_token=seed_chat_token, pscp_cookie=pscp_cookie)

    return PeriscopeBootstrapResult(
        pscp_cookie=pscp_cookie,
        seed_chat_token=seed_chat_token,
        access_chat_token=access_chat_token,
    )


def bootstrap_periscope_access_chat_token_from_media_key(*, x_session: XSession, guest_auth: GuestAuth, media_key: str) -> str:
    """Compatibility wrapper if you only need the join-ready chat_token."""

    return bootstrap_periscope_access_chat_token(
        x_session=x_session,
        guest_auth=guest_auth,
        media_key=media_key,
    ).access_chat_token


def bootstrap_periscope_access_chat_token_from_username(*, x_session: XSession, guest_auth: GuestAuth, username: str) -> PeriscopeBootstrapResult:
    raise SystemExit("periscope bootstrap: username resolution not implemented (use media_key) ")


# (Legacy placeholder kept to avoid breaking imports)
# The recommended entrypoint is bootstrap_periscope_access_chat_token_from_media_key.

