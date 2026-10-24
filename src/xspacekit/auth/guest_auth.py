from __future__ import annotations

from typing import Any

import httpx

from .x_session import XSession

from dataclasses import dataclass


@dataclass(frozen=True)
class GuestAuthResult:
    authorization_token: str
    cookie: str | None
    user_id: str | None
    username: str | None
    display_name: str | None
    twitter_id: str | None


class GuestAuth:
    """Periscope auth for audiospace backend."""

    def __init__(self, x_session: XSession, *, session: Any | None = None):
        self.x_session = x_session
        self._http = session or httpx.Client(timeout=30.0)

    def authorize_token(self, atu_cookie: str) -> str:
        """Call proxsee-cf.pscp.tv/api/v2/authorizeToken.

        Returns authorization_token (JWT-like bearer).
        """
        url = "https://proxsee-cf.pscp.tv/api/v2/authorizeToken"
        payload = {"service": "guest", "cookie": atu_cookie}
        r = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        return r.json()["authorization_token"]

    def turn_servers(self, atu_cookie: str) -> dict[str, Any]:
        """Call proxsee-cf.pscp.tv/api/v2/turnServers.

        Returns {ttl, username, password, uris}.
        """
        url = "https://proxsee-cf.pscp.tv/api/v2/turnServers"
        payload = {"cookie": atu_cookie}
        r = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        return r.json()

    def login_twitter_token(
        self,
        *,
        pcp_jwt: str,
        vendor_id: str = "m5-proxsee-login-a2011357b73e",
        create_user: bool = False,
        direct: bool = True,
    ) -> str:
        """Call proxsee-cf.pscp.tv/api/v2/loginTwitterToken.

        Returns the proxsee cookie (atu_cookie) used for authorizeToken/turnServers.
        """

        url = "https://proxsee-cf.pscp.tv/api/v2/loginTwitterToken"
        payload = {
            "jwt": pcp_jwt,
            "vendor_id": vendor_id,
            "create_user": create_user,
            "direct": direct,
        }
        r = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        cookie = data.get("cookie")
        if not isinstance(cookie, str) or not cookie:
            raise SystemExit("periscope loginTwitterToken: missing cookie in response")
        return cookie

    def access_chat(
        self,
        *,
        chat_token: str,
        pscp_cookie: str,
    ) -> str:
        """Call proxsee-cf.pscp.tv/api/v2/accessChat.

        The request uses the seed chat_token.
        The response returns access_token, which is the join-ready chat_token.
        """

        url = "https://proxsee-cf.pscp.tv/api/v2/accessChat"
        payload = {"chat_token": chat_token, "cookie": pscp_cookie}
        r = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise SystemExit("periscope accessChat: missing access_token in response")
        return access_token
