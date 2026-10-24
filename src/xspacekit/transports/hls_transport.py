from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HlsTransportConfig:
    m3u8_url: str


class HlsTransport:
    """Listen-only playback helper.

    This is transport scaffolding; actual decoding happens in an external player.
    """

    def __init__(self, cfg: HlsTransportConfig):
        self.cfg = cfg

    def get_playback_url(self) -> str:
        return self.cfg.m3u8_url
