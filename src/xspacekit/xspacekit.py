from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .auth.guest_auth import GuestAuth
from .auth.x_session import XSession, XSessionConfig
from .spaces.spaces_api import SpacesApi


@dataclass(frozen=True)
class XSpaceKitConfig:
    x_session: XSessionConfig


class XSpaceKit:
    """Top-level client for xspacekit."""

    def __init__(self, cfg: XSpaceKitConfig, *, session: Any | None = None):
        # `session` is a placeholder for dependency injection (requests/httpx session).
        self.session = XSession(cfg.x_session, session=session)
        self.guest_auth = GuestAuth(self.session, session=session)
        self.spaces = SpacesApi(self.session, session=session)
