from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
import time

import httpx

from ..auth.x_session import XSession

NTP_FOR_XSPACES = 2208988800021999900


@dataclass(frozen=True)
class AudioSpaceMetadata:
    broadcast_id: str
    state: str
    title: str
    participants: dict[str, Any]


@dataclass(frozen=True)
class SpeakerRequestResult:
    success: bool
    session_uuid: str


@dataclass(frozen=True)
class GuestSessionState:
    session_uuid: str
    session_state: int
    guest_is_audio_only: bool | None
    is_muted_by_admin: bool | None
    is_muted_by_guest: bool | None
    ended_at: str | None

    raw: dict[str, Any]

class SpacesApi:
    def __init__(self, x_session: XSession, *, session: object | None = None):
        self.x_session = x_session
        self._http = session or httpx.Client(timeout=30.0)

    def audio_space_by_id_raw(
        self,
        *,
        query_id: str,
        broadcast_id: str,
        with_replays: bool,
        with_listeners: bool,
        is_metatags_query: bool = False,
        features: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch raw AudioSpaceById response JSON from X GraphQL."""

        variables = {
            "id": broadcast_id,
            "isMetatagsQuery": is_metatags_query,
            "withReplays": with_replays,
            "withListeners": with_listeners,
        }

        return self.x_session.graphql(
            query_id,
            "AudioSpaceById",
            variables=variables,
            features=features,
        )

    def audio_space_by_id(
        self,
        *,
        query_id: str,
        broadcast_id: str,
        with_replays: bool,
        with_listeners: bool,
        is_metatags_query: bool = False,
        features: Mapping[str, Any] | None = None,
    ) -> AudioSpaceMetadata:
        """Fetch AudioSpaceById via X GraphQL."""

        variables = {
            "id": broadcast_id,
            "isMetatagsQuery": is_metatags_query,
            "withReplays": with_replays,
            "withListeners": with_listeners,
        }

        resp = self.x_session.graphql(
            query_id,
            "AudioSpaceById",
            variables=variables,
            features=features,
        )

        try:
            meta = resp["data"]["audioSpace"]["metadata"]
            broadcast_id = meta["rest_id"]
            state = meta["state"]
            title = meta["title"]
            participants = meta.get("participants") or {}
        except (KeyError, TypeError) as e:
            raise ValueError("Unexpected AudioSpaceById response shape") from e

        return AudioSpaceMetadata(
            broadcast_id=broadcast_id,
            state=state,
            title=title,
            participants=participants,
        )

    def audiospace_call_status_last_guest_session(
        self,
        *,
        guest_jwt: str,
        broadcast_id: str,
    ) -> GuestSessionState | None:
        """Best-effort parse of the last guest session in call status response."""

        resp = self.audiospace_call_status(
            guest_jwt=guest_jwt,
            broadcast_id=broadcast_id,
        )

        if not isinstance(resp, dict):
            return None

        guest_sessions = resp.get("guest_sessions")
        if not isinstance(guest_sessions, list) or not guest_sessions:
            return None

        last = guest_sessions[-1]
        if not isinstance(last, dict):
            return None

        def _get_bool(key: str) -> bool | None:
            v = last.get(key)
            if isinstance(v, bool):
                return v
            return None

        def _get_int(key: str) -> int | None:
            v = last.get(key)
            if isinstance(v, int):
                return v
            return None

        return GuestSessionState(
            session_uuid=str(last.get("session_uuid")),
            session_state=int(_get_int("session_state") or 0),
            guest_is_audio_only=_get_bool("guest_is_audio_only"),
            is_muted_by_admin=_get_bool("is_muted_by_admin"),
            is_muted_by_guest=_get_bool("is_muted_by_guest"),
            ended_at=last.get("ended_at") if isinstance(last.get("ended_at"), str) else None,
            raw=last,
        )

    def audio_space_lifecycle_listener(
        self,
        *,
        guest_jwt: str,
        broadcast_id: str,
        chat_token: str,
        poll_interval_s: float = 2.0,
        max_polls: int = 60,
    ) -> dict[str, Any]:
        """Best-effort listener lifecycle: join + poll call status.

        This is a convenience helper for exploration, not a fully modeled
        state machine yet.
        """

        join_resp = self.audiospace_join(
            guest_jwt=guest_jwt,
            broadcast_id=broadcast_id,
            chat_token=chat_token,
        )

        # Some captures return a can_auto_join boolean, others include more.
        # For now, require session_uuid from stream/negotiate phase later.
        # We still poll call status to expose occupancy.
        call_status_last: dict[str, Any] | None = None

        for _ in range(max_polls):
            call_status_last = self.audiospace_call_status(
                guest_jwt=guest_jwt,
                broadcast_id=broadcast_id,
            )
            # Break early if the backend indicates ended/non-active.
            # Caller can inspect the structure.
            if isinstance(call_status_last, dict) and call_status_last.get("ended") is True:
                break

            time.sleep(poll_interval_s)

        return {
            "join": join_resp,
            "call_status": call_status_last or {},
        }

    def audiospace_join(
        self,
        *,
        guest_jwt: str,
        broadcast_id: str,
        chat_token: str,
        join_as_admin: bool = False,
        should_auto_join: bool = False,
        ntp_for_broadcaster_frame: int = NTP_FOR_XSPACES,
        ntp_for_live_frame: int = NTP_FOR_XSPACES,
    ) -> dict[str, Any]:
        """POST /api/v1/audiospace/join"""

        url = "https://guest-cf.pscp.tv/api/v1/audiospace/join"
        payload = {
            "ntpForBroadcasterFrame": ntp_for_broadcaster_frame,
            "ntpForLiveFrame": ntp_for_live_frame,
            "broadcast_id": broadcast_id,
            "join_as_admin": join_as_admin,
            "should_auto_join": should_auto_join,
            "chat_token": chat_token,
        }
        headers = {"authorization": guest_jwt, "Content-Type": "application/json"}
        r = self._http.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

    def audiospace_request_submit(
        self,
        *,
        guest_jwt: str,
        broadcast_id: str,
        chat_token: str,
        ntp_for_broadcaster_frame: int = NTP_FOR_XSPACES,
        ntp_for_live_frame: int = NTP_FOR_XSPACES,
    ) -> SpeakerRequestResult:
        """POST /api/v1/audiospace/request/submit"""

        url = "https://guest-cf.pscp.tv/api/v1/audiospace/request/submit"
        payload = {
            "ntpForBroadcasterFrame": ntp_for_broadcaster_frame,
            "ntpForLiveFrame": ntp_for_live_frame,
            "broadcast_id": broadcast_id,
            "chat_token": chat_token,
        }
        headers = {"authorization": guest_jwt, "Content-Type": "application/json"}
        r = self._http.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return SpeakerRequestResult(success=bool(data["success"]), session_uuid=data["session_uuid"])

    def audiospace_call_status(
        self,
        *,
        guest_jwt: str,
        broadcast_id: str,
        include_non_active_sessions: bool = False,
    ) -> dict[str, Any]:
        """POST /api/v1/audiospace/call/status"""

        url = "https://guest-cf.pscp.tv/api/v1/audiospace/call/status"
        payload = {
            "broadcast_id": broadcast_id,
            "include_non_active_sessions": include_non_active_sessions,
        }
        headers = {"authorization": guest_jwt, "Content-Type": "application/json"}
        r = self._http.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

    def audiospace_stream_negotiate(self, *, guest_jwt: str, session_uuid: str) -> dict[str, Any]:
        """POST /api/v1/audiospace/stream/negotiate"""

        url = "https://guest-cf.pscp.tv/api/v1/audiospace/stream/negotiate"
        payload = {"session_uuid": session_uuid}
        headers = {"authorization": guest_jwt, "Content-Type": "application/json"}
        r = self._http.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()
