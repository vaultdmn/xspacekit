from __future__ import annotations

from typing import Any

from xspacekit.signaling.videoroom import (
    VideoroomPublisherParams,
    VideoroomSubscriberParams,
    build_publisher_message_sequence,
    build_subscriber_message_sequence,
)


def test_build_publisher_sequence_matches_har_shapes() -> None:
    params = VideoroomPublisherParams(
        session_uuid="sess-1",
        room_id="room-1",
        stream_name="stream-1",
        vidman_token="vidman-1",
        offer_sdp="v=0\n...",
        trickle_candidates=[
            {"candidate": "cand-a", "sdpMid": "0", "sdpMLineIndex": 0},
            {"candidate": "cand-b", "sdpMid": "0", "sdpMLineIndex": 0},
        ],
        periscope_user_id="per-user-1",
        display="disp-1",
    )

    seq = build_publisher_message_sequence(params=params)
    assert len(seq) == 2 + len(params.trickle_candidates)

    join = seq[0]
    assert join["janus"] == "message"
    assert isinstance(join["body"], dict)
    assert join["body"]["request"] == "join"
    assert join["body"]["ptype"] == "publisher"
    assert join["body"]["room"] == params.room_id
    assert join["body"]["periscope_user_id"] == params.periscope_user_id
    assert join["body"]["display"] == params.display

    configure = seq[1]
    assert configure["janus"] == "message"
    assert isinstance(configure["body"], dict)
    assert configure["body"]["request"] == "configure"
    assert configure["body"]["room"] == params.room_id
    assert configure["body"]["session_uuid"] == params.session_uuid
    assert configure["body"]["stream_name"] == params.stream_name
    assert configure["body"]["vidman_token"] == params.vidman_token
    assert configure["body"]["periscope_user_id"] == params.periscope_user_id

    assert isinstance(configure["jsep"], dict)
    assert configure["jsep"]["type"] == "offer"
    assert configure["jsep"]["sdp"] == params.offer_sdp

    # Trickles preserve candidate object as-is.
    for i, cand in enumerate(params.trickle_candidates):
        trickle = seq[2 + i]
        assert trickle["janus"] == "trickle"
        assert trickle["candidate"] == cand


def test_build_subscriber_sequence_matches_har_shapes() -> None:
    params = VideoroomSubscriberParams(
        session_uuid="sess-2",
        room_id="room-2",
        answer_sdp="v=0\n...",
        trickle_candidates=[
            {"candidate": "cand-x", "sdpMid": "0", "sdpMLineIndex": 0},
        ],
        periscope_user_id="per-user-2",
        streams=[{"mid": "0"}],
    )

    seq = build_subscriber_message_sequence(params=params)
    assert len(seq) == 2 + len(params.trickle_candidates)

    join = seq[0]
    assert join["janus"] == "message"
    assert join["body"]["request"] == "join"
    assert join["body"]["ptype"] == "subscriber"
    assert join["body"]["room"] == params.room_id
    assert join["body"]["periscope_user_id"] == params.periscope_user_id
    assert join["body"]["streams"] == params.streams

    start = seq[1]
    assert start["janus"] == "message"
    assert start["body"]["request"] == "start"
    assert start["body"]["room"] == params.room_id
    assert start["body"]["periscope_user_id"] == params.periscope_user_id

    assert isinstance(start["jsep"], dict)
    assert start["jsep"]["type"] == "answer"
    assert start["jsep"]["sdp"] == params.answer_sdp

    trickle = seq[2]
    assert trickle["janus"] == "trickle"
    assert isinstance(trickle["candidate"], dict)
    assert trickle["candidate"] == params.trickle_candidates[0]
