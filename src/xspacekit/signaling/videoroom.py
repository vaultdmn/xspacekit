from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

VideoRoomRole = Literal["publisher", "subscriber"]


@dataclass(frozen=True)
class VideoroomPublisherParams:
    # Audiospace/speaker-side identifiers
    session_uuid: str
    room_id: str

    # Videoroom configure fields (observed in HAR)
    stream_name: str
    vidman_token: str

    # SDP/ICE (caller-supplied; we don't generate WebRTC SDP yet)
    offer_sdp: str
    trickle_candidates: list[dict[str, Any]]

    # Periscope identity fields (observed in HAR)
    periscope_user_id: str

    # Only present in the HAR "join ptype=publisher" message body.
    display: str | None = None

    # Optional patch dicts for fields that change between gateway revisions.
    join_payload_extra: dict[str, Any] = field(default_factory=dict)
    configure_payload_extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoroomSubscriberParams:
    session_uuid: str
    room_id: str

    answer_sdp: str
    trickle_candidates: list[dict[str, Any]]

    periscope_user_id: str

    # Optional: in the HAR, join ptype=subscriber included a streams list.
    streams: list[dict[str, Any]] = field(default_factory=list)

    join_payload_extra: dict[str, Any] = field(default_factory=dict)
    start_payload_extra: dict[str, Any] = field(default_factory=dict)


def _build_trickle_payloads(
    *,
    trickle_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trickle_payloads: list[dict[str, Any]] = []
    for cand in trickle_candidates:
        trickle_payloads.append({"janus": "trickle", "candidate": cand})
    return trickle_payloads


def build_publisher_message_sequence(*, params: VideoroomPublisherParams) -> list[dict[str, Any]]:
    """Build videoroom signaling sequence for a publisher.

    This uses the message shapes observed in `full_order_xspaces.har`:
    - gateway-level: JanusGateway.create_session() + attach_videoroom()
    - plugin-level message exchange:
      - message{body: {request: join, ptype: publisher, ...}}
      - message{body: {request: configure, ...}, jsep: {type: offer, sdp: ...}}
      - trickle{candidate: ...} repeated
    """

    join_body: dict[str, Any] = {
        "request": "join",
        "ptype": "publisher",
        "room": params.room_id,
        "periscope_user_id": params.periscope_user_id,
    }
    if params.display is not None:
        join_body["display"] = params.display

    join_body.update(params.join_payload_extra)

    join_payload: dict[str, Any] = {
        "janus": "message",
        "body": join_body,
    }

    configure_body: dict[str, Any] = {
        "request": "configure",
        "room": params.room_id,
        "session_uuid": params.session_uuid,
        "stream_name": params.stream_name,
        "vidman_token": params.vidman_token,
        "periscope_user_id": params.periscope_user_id,
    }
    configure_body.update(params.configure_payload_extra)

    configure_payload: dict[str, Any] = {
        "janus": "message",
        "body": configure_body,
        "jsep": {"type": "offer", "sdp": params.offer_sdp},
    }

    return [
        join_payload,
        configure_payload,
        *_build_trickle_payloads(trickle_candidates=params.trickle_candidates),
    ]


def build_subscriber_message_sequence(
    *,
    params: VideoroomSubscriberParams,
) -> list[dict[str, Any]]:
    """Build videoroom signaling sequence for a subscriber/listener."""

    join_body: dict[str, Any] = {
        "request": "join",
        "ptype": "subscriber",
        "room": params.room_id,
        "periscope_user_id": params.periscope_user_id,
    }
    if params.streams:
        join_body["streams"] = params.streams

    join_body.update(params.join_payload_extra)

    join_payload: dict[str, Any] = {
        "janus": "message",
        "body": join_body,
    }

    start_body: dict[str, Any] = {
        "request": "start",
        "room": params.room_id,
        "periscope_user_id": params.periscope_user_id,
    }
    start_body.update(params.start_payload_extra)

    start_payload: dict[str, Any] = {
        "janus": "message",
        "body": start_body,
        "jsep": {"type": "answer", "sdp": params.answer_sdp},
    }

    return [
        join_payload,
        start_payload,
        *_build_trickle_payloads(trickle_candidates=params.trickle_candidates),
    ]
