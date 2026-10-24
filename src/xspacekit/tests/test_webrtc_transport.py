from __future__ import annotations

from collections.abc import Callable
from typing import Any

from xspacekit.transports.webrtc_transport import WebRtcTransport, WebRtcTransportConfig


class _DummyGateway:
    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, Any]] = []
        self.attach_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.long_poll_calls: list[dict[str, Any]] = []
        self._poll_count = 0

    def create_session(self, *, transaction: str | None = None) -> str:
        self.create_session_calls.append({"transaction": transaction})
        return "gw-session-1"

    def attach_videoroom(
        self,
        *,
        session_id: str,
        transaction: str | None = None,
        plugin: str = "janus.plugin.videoroom",
    ) -> str:
        self.attach_calls.append(
            {"session_id": session_id, "transaction": transaction, "plugin": plugin}
        )
        return "videoroom-handle-1"

    def send_message(
        self,
        *,
        session_id: str,
        handle_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.send_calls.append(
            {"session_id": session_id, "handle_id": handle_id, "payload": payload}
        )
        return {"janus": "ack", "payload": payload}

    def long_poll_events(self, *, session_id: str, max_events: int = 1) -> dict[str, Any]:
        self.long_poll_calls.append({"session_id": session_id, "max_events": max_events})
        self._poll_count += 1
        return {"janus": "event", "seq": self._poll_count}


def test_negotiate_sends_sequence_and_polls_events() -> None:
    gateway = _DummyGateway()
    transport = WebRtcTransport(cfg=WebRtcTransportConfig(janus_gateway=gateway))

    on_event_calls: list[dict[str, Any]] = []

    def on_event(ev: dict[str, Any]) -> Any:
        on_event_calls.append(ev)
        return None

    payloads = [
        {"janus": "message", "request": "configure", "jsep": {"type": "offer"}},
        {"janus": "trickle", "candidate": {"candidate": "cand"}},
    ]

    result = transport.negotiate(
        message_sequence=payloads,
        poll_after_each_payload=True,
        max_polls_per_payload=2,
        on_event=on_event,
    )

    assert result["gateway_session_id"] == "gw-session-1"
    assert result["videoroom_handle_id"] == "videoroom-handle-1"

    # 2 payloads x (ack + first event)
    assert len(result["responses"]) == 4
    assert len(on_event_calls) == 2

    assert len(gateway.send_calls) == 2
    assert gateway.send_calls[0]["handle_id"] == "videoroom-handle-1"
    assert gateway.send_calls[1]["payload"]["janus"] == "trickle"

    # Since our dummy events have janus=event, we break after the first poll per payload.
    assert len(gateway.long_poll_calls) == 2
