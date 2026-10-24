from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class JanusGatewayConfig:
    # e.g. https://gw-prod-hydra-ap-south-1.pscp.tv/s=prod:11/v1/gateway
    gateway_base_url: str
    janus_jwt: str


class JanusGateway:
    """Janus signaling over an HTTP long-poll gateway.

    Observed pattern:
    - POST <gateway_base_url> (create)
    - POST <gateway_base_url>/<session_id> (attach)
    - POST <gateway_base_url>/<session_id>/<handle_id> (videoroom message/trickle)
    - GET  <gateway_base_url>/<session_id>?maxev=1 (keepalive/events)
    """

    def __init__(self, cfg: JanusGatewayConfig, *, fetch: Any | None = None):
        self.cfg = cfg
        self._client = fetch or httpx.Client(timeout=60.0)

    def _headers(self) -> dict[str, str]:
        # Gateways commonly accept `Authorization: <JANUS_JWT>`.
        return {
            "Authorization": self.cfg.janus_jwt,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _transaction() -> str:
        # Janus transaction identifiers are opaque strings.
        # We keep this scaffold deterministic enough for unit testing by letting
        # higher-level code supply a transaction, but provide this helper too.
        import uuid

        return uuid.uuid4().hex

    def create_session(self, *, transaction: str | None = None) -> str:
        txn = transaction or self._transaction()
        url = self.cfg.gateway_base_url
        payload = {"janus": "create", "transaction": txn}

        r = self._client.post(url, json=payload, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        return data["data"]["id"]

    def attach_videoroom(
        self,
        *,
        session_id: str,
        transaction: str | None = None,
        plugin: str = "janus.plugin.videoroom",
    ) -> str:
        txn = transaction or self._transaction()
        url = f"{self.cfg.gateway_base_url}/{session_id}"
        payload = {"janus": "attach", "plugin": plugin, "transaction": txn}

        r = self._client.post(url, json=payload, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        return data["data"]["id"]

    def send_message(
        self,
        *,
        session_id: str,
        handle_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.cfg.gateway_base_url}/{session_id}/{handle_id}"

        # Janus payloads commonly include a `transaction` identifier.
        # If the caller didn’t supply one, add a best-effort unique value.
        if "transaction" not in payload:
            import uuid

            payload = {"transaction": uuid.uuid4().hex, **payload}

        r = self._client.post(url, json=payload, headers=self._headers())
        r.raise_for_status()
        return r.json()

    def long_poll_events(self, *, session_id: str, max_events: int = 1) -> dict[str, Any]:
        url = f"{self.cfg.gateway_base_url}/{session_id}?maxev={max_events}"

        headers = {
            "Authorization": self.cfg.janus_jwt,
            "Accept": "application/json",
        }
        r = self._client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()
