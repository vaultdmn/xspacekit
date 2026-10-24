from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from xspacekit.config.cookie_loader import CookieFile, load_cookie_file, resolve_default_cookie_path
from xspacekit.core import build_flow_from_cookie_file
from xspacekit.har.publisher_offer_trickle_extractor import _extract_publisher_offer_and_trickle_from_har
from xspacekit.periscope import (
    bootstrap_periscope_pscp_cookie,
    resolve_live_stream_seed_chat_token,
    extract_media_key,
)
from xspacekit.spaces.m3u8_extract import find_first_m3u8_url


def _load_cookie_or_default(cookie_file: str | None) -> CookieFile:
    if cookie_file:
        return load_cookie_file(cookie_file)

    default_path = resolve_default_cookie_path()
    if default_path is None:
        raise SystemExit(
            "Missing cookie file. Provide --cookie-file <path> or create cookie.txt next to where you run the CLI."
        )

    return load_cookie_file(default_path)


def _decode_janus_jwt_payload(janus_jwt: str) -> dict[str, Any]:
    """Decode the middle JWT payload segment (no signature verification)."""

    parts = janus_jwt.split(".")
    if len(parts) < 2:
        return {}

    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    raw = base64.urlsafe_b64decode(payload_b64)
    return json.loads(raw.decode("utf-8", errors="replace"))


def _read_text_file(path: str | Path) -> str:
    p = Path(path).expanduser().resolve()
    return p.read_text(encoding="utf-8", errors="replace")


def _load_trickle_candidates(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, dict):
        # Allow either {"candidates": [...]} or similar.
        for k in ["candidates", "trickle_candidates", "ice_candidates"]:
            if k in data and isinstance(data[k], list):
                data = data[k]
                break

    if not isinstance(data, list):
        raise SystemExit("speak: trickle candidates file must contain a JSON list")

    out: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(f"speak: trickle candidate at index {i} is not an object")
        out.append(item)
    return out


def _summarize_janus_responses(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for r in responses:
        if not isinstance(r, dict):
            summarized.append({"type": str(type(r))})
            continue

        janus_type = r.get("janus")
        plugindata = r.get("plugindata")
        videoroom = None
        if isinstance(plugindata, dict):
            data = plugindata.get("data")
            if isinstance(data, dict):
                videoroom = data.get("videoroom")

        summarized.append({
            "janus": janus_type,
            "videoroom": videoroom,
        })

    return summarized


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="xspacekit")
    p.add_argument(
        "--cookie-file",
        default=None,
        help="Path to cookie.txt (x.com cookies + proxsee guest cookie + optional chat_token). Defaults to $XSPACEKIT_COOKIE_FILE or ./cookie.txt.",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    listen = sub.add_parser("listen", help="Listen to an X Space (prototype)")
    listen.add_argument("--m3u8", required=False, help="If provided, just prints the URL.")
    listen.add_argument("--broadcast-id", required=False, help="AudioSpace broadcast id (rest_id).")
    listen.add_argument("--query-id", required=False, help="GraphQL query id for AudioSpaceById.")
    listen.add_argument(
        "--chat-token",
        required=False,
        help="(Legacy) Periscope join-ready chat token. If omitted, xspacekit will derive it automatically.",
    )

    listen.add_argument(
        "--poll",
        action="store_true",
        help="Poll audiospace/call/status and print session occupancy.",
    )
    listen.add_argument("--max-polls", type=int, default=10)
    listen.add_argument("--poll-interval-s", type=float, default=2.0)

    speak = sub.add_parser(
        "speak",
        help=(
            "Attempt to speak/publish (publisher signaling scaffold). "
            "Either provide offer+trickle via files, or extract them from a captured HAR."
        ),
    )
    speak.add_argument(
        "--offer-sdp-file",
        required=False,
        help="Path to a text file containing videoroom offer SDP (jsep.sdp).",
    )
    speak.add_argument(
        "--trickle-candidates-file",
        required=False,
        help="Path to a JSON file containing a list of ICE candidate objects (videoroom trickle candidate format).",
    )
    speak.add_argument(
        "--har-file",
        required=False,
        help=(
            "Optional HAR capture to extract videoroom offer SDP + trickle candidates "
            "from a previous successful publisher run."
        ),
    )
    speak.add_argument(
        "--janus-publisher-handle-id",
        required=False,
        help=(
            "Optional: when extracting from --har-file, restrict to this videoroom handle_id "
            "(the path segment after .../v1/gateway/<session_id>/)."
        ),
    )
    speak.add_argument(
        "--stop-when-joined",
        action="store_true",
        help="Stop polling long-poll events early once videoroom=joined is observed for each payload.",
    )
    speak.add_argument(
        "--max-polls",
        type=int,
        default=10,
        help="Max long-poll event fetches after each gateway payload.",
    )
    speak.add_argument(
        "--poll-interval-s",
        type=float,
        default=0.0,
        help="Optional sleep between polling rounds (default: 0).",
    )
    speak.add_argument(
        "--broadcast-id",
        required=False,
        help="AudioSpace broadcast id (rest_id). Defaults to cookie.txt broadcast_id.",
    )
    speak.add_argument(
        "--query-id",
        required=False,
        help="GraphQL query id for AudioSpaceById (not required for publisher signaling; defaults to cookie.txt query_id).",
    )
    speak.add_argument(
        "--chat-token",
        required=False,
        help="(Legacy) Periscope join-ready chat token. If omitted, xspacekit will derive it via accessChat using the live stream seed token.",
    )

    speak.add_argument(
        "--live-audio",
        action="store_true",
        help="Use aiortc to generate a live WebRTC audio offer dynamically and stream audio (requires aiortc).",
    )
    speak.add_argument(
        "--duration-s",
        type=float,
        default=5.0,
        help="Duration in seconds to stream live audio when --live-audio is specified (default: 5.0).",
    )
    speak.add_argument(
        "--poll",
        action="store_true",
        help="Poll audiospace/call/status after request/submit to surface state transitions.",
    )
    speak.add_argument("--max-polls-occupancy", type=int, default=10)

    args = p.parse_args(argv)

    if args.cmd == "listen":
        if args.m3u8:
            print(args.m3u8)
            return 0

        cookie_cfg = _load_cookie_or_default(args.cookie_file)

        broadcast_id = args.broadcast_id or cookie_cfg.broadcast_id
        query_id = args.query_id or cookie_cfg.query_id
        chat_token = args.chat_token or cookie_cfg.chat_token

        if not broadcast_id:
            raise SystemExit("listen: missing --broadcast-id (or set broadcast_id in cookie.txt)")
        if not query_id:
            raise SystemExit("listen: missing --query-id (or set query_id in cookie.txt)")

        flow = build_flow_from_cookie_file(cookie_cfg)

        # 1) Periscope guest cookie ("atu" / pscp cookie)
        pscp_cookie = cookie_cfg.atu_cookie
        if not pscp_cookie:
            pscp_cookie = bootstrap_periscope_pscp_cookie(x_session=flow.x_session, guest_auth=flow.guest_auth)

        # 2) Guest auth for audiospace backend
        guest_jwt = flow.guest_auth.authorize_token(atu_cookie=pscp_cookie)

        # 2) Fetch AudioSpaceById metadata.
        # We use this both for HLS URL discovery and (optionally) for extracting
        # the live_video_stream/status media_key used to derive chat_token.
        raw_meta = flow.spaces_api.audio_space_by_id_raw(
            query_id=query_id,
            broadcast_id=broadcast_id,
            with_replays=True,
            with_listeners=True,
            is_metatags_query=False,
            features=None,
        )

        m3u8_url = find_first_m3u8_url(raw_meta)

        # 2b) Auto-derive join-ready chat_token when not provided.
        # Derivation chain: live_video_stream/status -> accessChat.
        if not chat_token:
            media_key = extract_media_key(raw_meta)
            if not isinstance(media_key, str) or not media_key:
                raise SystemExit(
                    "listen: missing --chat-token (and unable to extract media_key from AudioSpaceById)"
                )

            seed_chat_token = resolve_live_stream_seed_chat_token(
                x_session=flow.x_session,
                media_key=media_key,
            )
            chat_token = flow.guest_auth.access_chat(
                chat_token=seed_chat_token,
                pscp_cookie=pscp_cookie,
            )

        # 3) Join as listener + occupancy poll
        join_resp = flow.spaces_api.audiospace_join(
            guest_jwt=guest_jwt,
            broadcast_id=broadcast_id,
            chat_token=chat_token,
            join_as_admin=False,
            should_auto_join=False,
        )

        # Print a compact bootstrap response.
        bootstrap: dict[str, Any] = {
            "broadcast_id": broadcast_id,
            "can_auto_join": join_resp.get("can_auto_join"),
            "m3u8_url": m3u8_url,
        }

        print(json.dumps(bootstrap, indent=2, ensure_ascii=False))

        if not args.poll:
            return 0

        # Poll occupancy
        import time

        for _ in range(args.max_polls):
            call_status = flow.spaces_api.audiospace_call_status(
                guest_jwt=guest_jwt,
                broadcast_id=broadcast_id,
                include_non_active_sessions=False,
            )

            guest_sessions = call_status.get("guest_sessions") if isinstance(call_status, dict) else None
            if isinstance(guest_sessions, list):
                simplified = [
                    {
                        "session_uuid": gs.get("session_uuid"),
                        "session_state": gs.get("session_state"),
                        "muted_guest": gs.get("is_muted_by_guest"),
                    }
                    for gs in guest_sessions
                    if isinstance(gs, dict)
                ]
            else:
                simplified = []

            print(json.dumps({"guest_sessions": simplified}, ensure_ascii=False))
            time.sleep(args.poll_interval_s)

        return 0

    if args.cmd == "speak":
        from xspacekit.signaling import JanusGateway, JanusGatewayConfig
        from xspacekit.transports import WebRtcTransport, WebRtcTransportConfig
        from xspacekit.signaling import VideoroomPublisherParams

        cookie_cfg = _load_cookie_or_default(args.cookie_file)

        broadcast_id = args.broadcast_id or cookie_cfg.broadcast_id
        chat_token = args.chat_token or cookie_cfg.chat_token

        if not broadcast_id:
            raise SystemExit("speak: missing --broadcast-id (or set broadcast_id in cookie.txt)")

        query_id = args.query_id or cookie_cfg.query_id

        flow = build_flow_from_cookie_file(cookie_cfg)

        # 1) Periscope guest cookie ("atu" / pscp cookie)
        pscp_cookie = cookie_cfg.atu_cookie
        if not pscp_cookie:
            pscp_cookie = bootstrap_periscope_pscp_cookie(x_session=flow.x_session, guest_auth=flow.guest_auth)

        # 2) Guest JWT for audiospace backend
        guest_jwt = flow.guest_auth.authorize_token(atu_cookie=pscp_cookie)

        # 3) Join-ready chat token
        if not chat_token:
            if not query_id:
                raise SystemExit("speak: missing --query-id (or set query_id in cookie.txt) to derive chat_token")

            raw_meta = flow.spaces_api.audio_space_by_id_raw(
                query_id=query_id,
                broadcast_id=broadcast_id,
                with_replays=True,
                with_listeners=True,
                is_metatags_query=False,
                features=None,
            )
            media_key = extract_media_key(raw_meta)
            if not isinstance(media_key, str) or not media_key:
                raise SystemExit("speak: unable to extract media_key from AudioSpaceById response")

            seed_chat_token = resolve_live_stream_seed_chat_token(
                x_session=flow.x_session,
                media_key=media_key,
            )
            chat_token = flow.guest_auth.access_chat(chat_token=seed_chat_token, pscp_cookie=pscp_cookie)

        # 2) Best-effort join (speaker approval flow often follows this)
        flow.spaces_api.audiospace_join(
            guest_jwt=guest_jwt,
            broadcast_id=broadcast_id,
            chat_token=chat_token,
            join_as_admin=False,
            should_auto_join=False,
        )

        # 3) Request/submit as speaker
        req_submit = flow.spaces_api.audiospace_request_submit(
            guest_jwt=guest_jwt,
            broadcast_id=broadcast_id,
            chat_token=chat_token,
        )

        if not req_submit.success:
            raise SystemExit("speak: audiospace/request/submit returned success=false")

        # 4) Stream negotiate (gives JANUS JWT + gateway base URL)
        stream_negotiate = flow.spaces_api.audiospace_stream_negotiate(
            guest_jwt=guest_jwt,
            session_uuid=req_submit.session_uuid,
        )
        janus_jwt = stream_negotiate.get("janus_jwt")
        webrtc_gw_url = stream_negotiate.get("webrtc_gw_url")

        if not isinstance(janus_jwt, str) or not janus_jwt:
            raise SystemExit("speak: stream/negotiate missing janus_jwt")
        if not isinstance(webrtc_gw_url, str) or not webrtc_gw_url:
            raise SystemExit("speak: stream/negotiate missing webrtc_gw_url")

        janus_payload = _decode_janus_jwt_payload(janus_jwt)
        periscope_user_id = janus_payload.get("GrantedTo")
        if not isinstance(periscope_user_id, str) or not periscope_user_id:
            raise SystemExit("speak: unable to extract periscope_user_id from janus_jwt")

        # 5) Optional: occupancy/state polling
        occupancy_snapshots: list[dict[str, Any]] = []
        if args.poll:
            import time

            for _ in range(args.max_polls_occupancy):
                call_status = flow.spaces_api.audiospace_call_status(
                    guest_jwt=guest_jwt,
                    broadcast_id=broadcast_id,
                    include_non_active_sessions=False,
                )

                guest_sessions = call_status.get("guest_sessions") if isinstance(call_status, dict) else None
                if isinstance(guest_sessions, list):
                    simplified = [
                        {
                            "session_uuid": gs.get("session_uuid"),
                            "session_state": gs.get("session_state"),
                            "muted_guest": gs.get("is_muted_by_guest"),
                        }
                        for gs in guest_sessions
                        if isinstance(gs, dict)
                    ]
                else:
                    simplified = []

                occupancy_snapshots.append({"guest_sessions": simplified})
                if args.poll_interval_s:
                    time.sleep(args.poll_interval_s)

        offer_sdp: str | None = None
        trickle_candidates: list[dict[str, Any]] | None = None

        if args.offer_sdp_file and args.trickle_candidates_file:
            offer_sdp = _read_text_file(args.offer_sdp_file).strip()
            trickle_candidates = _load_trickle_candidates(args.trickle_candidates_file)

        if (offer_sdp is None or trickle_candidates is None) and args.har_file:
            offer_sdp, trickle_candidates = _extract_publisher_offer_and_trickle_from_har(
                har_file=args.har_file,
                janus_publisher_handle_id=args.janus_publisher_handle_id,
            )

        if offer_sdp is None or trickle_candidates is None:
            raise SystemExit(
                "speak: provide either (--offer-sdp-file AND --trickle-candidates-file) or --har-file"
            )

        # Observed in full_order_xspaces.har:
        # - videoroom "room" == audiospace broadcast_id (rest_id)
        # - videoroom configure "stream_name" == same room id
        room_id = broadcast_id
        stream_name = broadcast_id
        vidman_token = janus_jwt

        janus_gateway = JanusGateway(
            JanusGatewayConfig(gateway_base_url=webrtc_gw_url, janus_jwt=janus_jwt)
        )
        transport = WebRtcTransport(WebRtcTransportConfig(janus_gateway=janus_gateway))

        if args.live_audio:
            # Live WebRTC streaming via aiortc
            live_result = transport.publish_audio_live(
                room_id=room_id,
                stream_name=stream_name,
                vidman_token=vidman_token,
                periscope_user_id=periscope_user_id,
                session_uuid=req_submit.session_uuid,
                duration_s=args.duration_s,
            )
            bootstrap: dict[str, Any] = {
                "broadcast_id": broadcast_id,
                "mode": "live_audio_aiortc",
                "speaker_request": {
                    "success": req_submit.success,
                    "session_uuid": req_submit.session_uuid,
                },
                "stream_negotiate": {
                    "webrtc_gw_url": webrtc_gw_url,
                    "janus_jwt_len": len(janus_jwt),
                },
                "live_streaming": live_result,
            }
            if occupancy_snapshots:
                bootstrap["occupancy_snapshots"] = occupancy_snapshots

            print(json.dumps(bootstrap, indent=2, ensure_ascii=False))
            return 0

        offer_sdp: str | None = None
        trickle_candidates: list[dict[str, Any]] | None = None

        if args.offer_sdp_file and args.trickle_candidates_file:
            offer_sdp = _read_text_file(args.offer_sdp_file).strip()
            trickle_candidates = _load_trickle_candidates(args.trickle_candidates_file)

        if (offer_sdp is None or trickle_candidates is None) and args.har_file:
            offer_sdp, trickle_candidates = _extract_publisher_offer_and_trickle_from_har(
                har_file=args.har_file,
                janus_publisher_handle_id=args.janus_publisher_handle_id,
            )

        if offer_sdp is None or trickle_candidates is None:
            raise SystemExit(
                "speak: provide either (--offer-sdp-file AND --trickle-candidates-file), --har-file, or --live-audio"
            )

        params = VideoroomPublisherParams(
            session_uuid=req_submit.session_uuid,
            room_id=room_id,
            stream_name=stream_name,
            vidman_token=vidman_token,
            offer_sdp=offer_sdp,
            trickle_candidates=trickle_candidates,
            periscope_user_id=periscope_user_id,
            display=periscope_user_id,
        )

        # 6) Janus publisher signaling over HTTP gateway (long-poll)

        def _stop_polling_when_joined(ev: dict[str, Any]) -> bool:
            if not isinstance(ev, dict):
                return False
            if ev.get("janus") != "event":
                return False
            plugindata = ev.get("plugindata")
            if not isinstance(plugindata, dict):
                return False
            data = plugindata.get("data")
            if not isinstance(data, dict):
                return False
            return data.get("videoroom") == "joined"

        negotiation = transport.negotiate_videoroom_publisher(
            params=params,
            poll_after_each_payload=True,
            max_polls_per_payload=args.max_polls,
            stop_polling_when=_stop_polling_when_joined if args.stop_when_joined else None,
        )

        bootstrap: dict[str, Any] = {
            "broadcast_id": broadcast_id,
            "speaker_request": {
                "success": req_submit.success,
                "session_uuid": req_submit.session_uuid,
            },
            "stream_negotiate": {
                "webrtc_gw_url": webrtc_gw_url,
                "janus_jwt_len": len(janus_jwt),
            },
            "videoroom": {
                "room_id": room_id,
                "stream_name": stream_name,
                "periscope_user_id": periscope_user_id,
                "offer_sdp_len": len(offer_sdp),
                "trickle_candidates": len(trickle_candidates),
            },
            "negotiation": {
                "gateway_session_id": negotiation.get("gateway_session_id"),
                "videoroom_handle_id": negotiation.get("videoroom_handle_id"),
                "responses_count": len(negotiation.get("responses") or []),
                "response_summaries": _summarize_janus_responses(negotiation.get("responses") or []),
            },
        }

        if occupancy_snapshots:
            bootstrap["occupancy_snapshots"] = occupancy_snapshots

        print(json.dumps(bootstrap, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
