from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from xspacekit.audio.audio_stream import AudioStream, silent_frames
from xspacekit.signaling.videoroom import (
    VideoroomPublisherParams,
    VideoroomSubscriberParams,
    build_publisher_message_sequence,
    build_subscriber_message_sequence,
)

logger = logging.getLogger("xspacekit.transports.webrtc")

@dataclass(frozen=True)
class WebRtcTransportConfig:
    janus_gateway: Any


VideoRoomRole = Literal["publisher", "session"]


class WebRtcTransport:
    """WebRTC media transport adapter.

    - Supports pure signaling orchestration over HTTP long-poll (via `negotiate()`),
      maintaining full backwards compatibility with existing unit tests.
    - Supports live WebRTC media streaming via `aiortc` (`publish_audio_live()`),
      which dynamically generates an SDP offer, collects ICE candidates, performs
      the Janus HTTP signaling exchange, and streams Opus packets to Janus.
    """

    def __init__(self, cfg: WebRtcTransportConfig):
        self.cfg = cfg

    def negotiate(
        self,
        *,
        message_sequence: list[dict[str, Any]],
        gateway_session_id: str | None = None,
        videoroom_handle_id: str | None = None,
        poll_after_each_payload: bool = True,
        max_polls_per_payload: int = 20,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
        stop_polling_when: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any]:
        """Run a videoroom message exchange over an HTTP long-poll gateway."""
        gateway = self.cfg.janus_gateway

        if gateway_session_id is None:
            gateway_session_id = gateway.create_session(transaction=None)

        if videoroom_handle_id is None:
            videoroom_handle_id = gateway.attach_videoroom(
                session_id=gateway_session_id,
                transaction=None,
            )

        responses: list[dict[str, Any]] = []
        for payload in message_sequence:
            send_resp = gateway.send_message(
                session_id=gateway_session_id,
                handle_id=videoroom_handle_id,
                payload=payload,
            )
            responses.append(send_resp)

            if not poll_after_each_payload:
                continue

            for _ in range(max_polls_per_payload):
                ev = gateway.long_poll_events(session_id=gateway_session_id, max_events=1)
                if isinstance(ev, dict):
                    responses.append(ev)
                    if on_event is not None:
                        on_event(ev)

                    if stop_polling_when is not None and stop_polling_when(ev):
                        break

                    janus_type = ev.get("janus")
                    if stop_polling_when is None and janus_type not in {"keepalive", "timeout"}:
                        break
                else:
                    responses.append({"_raw": ev})

        return {
            "gateway_session_id": gateway_session_id,
            "videoroom_handle_id": videoroom_handle_id,
            "responses": responses,
        }

    def negotiate_videoroom_publisher(
        self,
        *,
        params: VideoroomPublisherParams,
        poll_after_each_payload: bool = True,
        max_polls_per_payload: int = 20,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
        stop_polling_when: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any]:
        """Convenience wrapper for the publisher/speaking path (static SDP/candidates)."""
        sequence = build_publisher_message_sequence(params=params)
        return self.negotiate(
            message_sequence=sequence,
            poll_after_each_payload=poll_after_each_payload,
            max_polls_per_payload=max_polls_per_payload,
            on_event=on_event,
            stop_polling_when=stop_polling_when,
        )

    def negotiate_videoroom_subscriber(
        self,
        *,
        params: VideoroomSubscriberParams,
        poll_after_each_payload: bool = True,
        max_polls_per_payload: int = 20,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
        stop_polling_when: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any]:
        """Convenience wrapper for the subscriber/listening path."""
        sequence = build_subscriber_message_sequence(params=params)
        return self.negotiate(
            message_sequence=sequence,
            poll_after_each_payload=poll_after_each_payload,
            max_polls_per_payload=max_polls_per_payload,
            on_event=on_event,
            stop_polling_when=stop_polling_when,
        )

    async def publish_audio_live_async(
        self,
        *,
        room_id: str,
        stream_name: str,
        vidman_token: str,
        periscope_user_id: str,
        session_uuid: str,
        audio_stream: AudioStream | None = None,
        duration_s: float | None = None,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        """Execute true End-to-End live audio publishing via aiortc and Janus HTTP gateway.

        1. Creates an aiortc RTCPeerConnection.
        2. Wraps `audio_stream` into an aiortc MediaStreamTrack (sending Opus).
        3. Generates a dynamic SDP offer and collects ICE candidates.
        4. Initiates Janus session and attaches to the videoroom plugin.
        5. Sends `join` and `configure` (with the live offer SDP).
        6. Sends gathered ICE candidates via `trickle`.
        7. Parses the remote answer SDP from Janus events and completes DTLS/ICE.
        8. Streams audio frames for `duration_s` (or indefinitely if duration_s is None).
        """
        try:
            from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
            from aiortc.mediastreams import AudioStreamTrack
            from av import AudioFrame
            import fractions
        except ImportError as e:
            raise SystemExit(
                "aiortc is required for live audio streaming. Run: pip install aiortc"
            ) from e

        gateway = self.cfg.janus_gateway
        stream = audio_stream or pcm_s16le_stream()

        # Custom aiortc AudioStreamTrack reading from AudioStream async generator
        class XSpaceAudioTrack(AudioStreamTrack):
            def __init__(self, stream: AudioStream):
                super().__init__()
                self._stream = stream
                self._sample_rate = stream.fmt.sample_rate
                self._channels = stream.fmt.channels
                self._timestamp = 0

            async def recv(self) -> AudioFrame:
                if self.readyState != "live":
                    raise RuntimeError("Track ended")

                # 20ms frame size = sample_rate * 20 / 1000 samples
                samples_per_frame = int(self._sample_rate * 0.02)
                bytes_per_sample = 2 * self._channels
                expected_bytes = samples_per_frame * bytes_per_sample

                # Collect or generate PCM chunk
                try:
                    chunk = await asyncio.wait_for(
                        self._stream._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    chunk = b"\x00" * expected_bytes

                if chunk is None or self._stream._closed:
                    raise RuntimeError("Audio stream closed")

                # Pad or truncate chunk to match exactly 20ms
                if len(chunk) < expected_bytes:
                    chunk = chunk + b"\x00" * (expected_bytes - len(chunk))
                elif len(chunk) > expected_bytes:
                    chunk = chunk[:expected_bytes]

                frame = AudioFrame(format="s16", layout="mono" if self._channels == 1 else "stereo", samples=samples_per_frame)
                frame.planes[0].update(chunk)
                frame.sample_rate = self._sample_rate
                frame.pts = self._timestamp
                self._timestamp += samples_per_frame
                return frame

        pc = RTCPeerConnection()
        trickle_candidates: list[dict[str, Any]] = []

        @pc.on("icecandidate")
        def on_icecandidate(candidate: Any) -> None:
            if candidate and candidate.candidate:
                c_dict = {
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid or "0",
                    "sdpMLineIndex": candidate.sdpMLineIndex if candidate.sdpMLineIndex is not None else 0,
                }
                trickle_candidates.append(c_dict)

        # Add audio track
        audio_track = XSpaceAudioTrack(stream)
        pc.addTrack(audio_track)

        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # Wait briefly for ICE candidates to gather
        await asyncio.sleep(0.5)

        # Start gateway session & attach videoroom
        gateway_session_id = gateway.create_session(transaction=None)
        videoroom_handle_id = gateway.attach_videoroom(
            session_id=gateway_session_id,
            transaction=None,
        )

        # 1) Join publisher
        join_payload = {
            "janus": "message",
            "body": {
                "request": "join",
                "ptype": "publisher",
                "room": room_id,
                "periscope_user_id": periscope_user_id,
                "display": periscope_user_id,
            },
        }
        ack1 = gateway.send_message(
            session_id=gateway_session_id,
            handle_id=videoroom_handle_id,
            payload=join_payload,
        )

        # 2) Configure with live SDP offer
        configure_payload = {
            "janus": "message",
            "body": {
                "request": "configure",
                "room": room_id,
                "session_uuid": session_uuid,
                "stream_name": stream_name,
                "vidman_token": vidman_token,
                "periscope_user_id": periscope_user_id,
            },
            "jsep": {
                "type": offer.type,
                "sdp": offer.sdp,
            },
        }
        ack2 = gateway.send_message(
            session_id=gateway_session_id,
            handle_id=videoroom_handle_id,
            payload=configure_payload,
        )

        # 3) Send trickle candidates
        trickle_acks = []
        for cand in trickle_candidates:
            t_payload = {"janus": "trickle", "candidate": cand}
            t_ack = gateway.send_message(
                session_id=gateway_session_id,
                handle_id=videoroom_handle_id,
                payload=t_payload,
            )
            trickle_acks.append(t_ack)

        # 4) Poll for remote answer (JSEP answer from Janus)
        remote_answer_sdp: str | None = None
        responses = [ack1, ack2, *trickle_acks]

        for _ in range(15):
            ev = gateway.long_poll_events(session_id=gateway_session_id, max_events=1)
            if isinstance(ev, dict):
                responses.append(ev)
                if on_event:
                    on_event(ev)
                # Check for jsep answer
                jsep = ev.get("jsep")
                if isinstance(jsep, dict) and jsep.get("type") == "answer":
                    remote_answer_sdp = jsep.get("sdp")
                    break
            await asyncio.sleep(0.2)

        if remote_answer_sdp:
            await pc.setRemoteDescription(
                RTCSessionDescription(type="answer", sdp=remote_answer_sdp)
            )

        # 5) Stream audio for duration_s (or run task)
        if duration_s is not None:
            # Seed some initial silent frames if buffer is empty
            for frame in silent_frames(duration_s=0.2):
                stream.write(frame)
            await asyncio.sleep(duration_s)

        return {
            "gateway_session_id": gateway_session_id,
            "videoroom_handle_id": videoroom_handle_id,
            "remote_answer_received": bool(remote_answer_sdp),
            "responses": responses,
        }

    def publish_audio_live(
        self,
        *,
        room_id: str,
        stream_name: str,
        vidman_token: str,
        periscope_user_id: str,
        session_uuid: str,
        audio_stream: AudioStream | None = None,
        duration_s: float | None = None,
        on_event: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        """Synchronous wrapper for publish_audio_live_async."""
        return asyncio.run(
            self.publish_audio_live_async(
                room_id=room_id,
                stream_name=stream_name,
                vidman_token=vidman_token,
                periscope_user_id=periscope_user_id,
                session_uuid=session_uuid,
                audio_stream=audio_stream,
                duration_s=duration_s,
                on_event=on_event,
            )
        )
