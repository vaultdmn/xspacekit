from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RtmpsTransportConfig:
    ingest_url: str
    stream_key: str


class RtmpsTransport:
    def __init__(self, cfg: RtmpsTransportConfig):
        self.cfg = cfg

    def ingest_url(self) -> str:
        return self.cfg.ingest_url
