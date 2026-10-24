from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from xspacekit.auth.guest_auth import GuestAuth
from xspacekit.auth.x_session import XSession, XSessionConfig
from xspacekit.config.cookie_loader import CookieFile, require_cookie_file_fields
from xspacekit.spaces.spaces_api import SpacesApi


@dataclass(frozen=True)
class BuiltFlow:
    x_session: XSession
    guest_auth: GuestAuth
    spaces_api: SpacesApi


def build_flow_from_cookie_file(cfg: CookieFile) -> BuiltFlow:
    require_cookie_file_fields(cfg)

    x_cfg = XSessionConfig(
        auth_token=cfg.auth_token or "",
        ct0=cfg.ct0 or "",
        guest_id=cfg.guest_id or "",
        x_bearer=cfg.x_bearer or "",
    )

    x_session = XSession(x_cfg)
    guest_auth = GuestAuth(x_session)
    spaces_api = SpacesApi(x_session)

    return BuiltFlow(
        x_session=x_session,
        guest_auth=guest_auth,
        spaces_api=spaces_api,
    )
