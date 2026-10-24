from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class XSessionConfig:
    """Credentials for X web session calls (GraphQL).

    Provide only via user config/env; never hardcode.
    """

    auth_token: str  # cookie: auth_token
    ct0: str  # cookie + x-csrf-token
    guest_id: str
    x_bearer: str  # authorization: Bearer <X_BEARER>


class XSession:
    def __init__(self, cfg: XSessionConfig, *, session: Any | None = None):
        self.cfg = cfg
        self._http = session or httpx.Client(timeout=30.0)

    @property
    def base_url(self) -> str:
        return "https://x.com"

    def _cookies_header(self) -> str:
        return (
            f"auth_token={self.cfg.auth_token}; ct0={self.cfg.ct0}; guest_id={self.cfg.guest_id}"
        )

    def graphql_headers(self, *, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "authorization": f"Bearer {self.cfg.x_bearer}",
            "x-csrf-token": self.cfg.ct0,
            "Cookie": self._cookies_header(),
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
        }
        if extra is not None:
            headers.update(extra)
        return headers

    def graphql(
        self,
        query_id: str,
        operation: str,
        *,
        variables: Mapping[str, Any],
        features: Mapping[str, Any] | None = None,
        x_client_transaction_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform X GraphQL call to an observed endpoint."""

        if not x_client_transaction_id:
            x_client_transaction_id = uuid.uuid4().hex

        url = f"{self.base_url}/i/api/graphql/{query_id}/{operation}"
        params: dict[str, Any] = {
            "variables": json.dumps(variables, separators=(",", ":"), ensure_ascii=False),
        }
        if features is not None:
            params["features"] = json.dumps(features, separators=(",", ":"), ensure_ascii=False)

        headers = self.graphql_headers(extra={"x-client-transaction-id": x_client_transaction_id})
        r = self._http.get(url, params=params, headers=headers)
        r.raise_for_status()
        return r.json()
