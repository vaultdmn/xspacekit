from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudioStreamFormat:
    # e.g. "pcm_s16le", "opus"
    name: str
    sample_rate: int = 48000
    channels: int = 1


class AudioStream:
    """Audio abstraction for SDK consumers.

    Supports two modes:
    - Buffered (sink=None): chunks accumulated in-memory for tests / offline use.
    - Streaming (sink=callback): each chunk forwarded to a sink immediately.

    For live WebRTC publishing the transport layer calls `iter_chunks_async()`
    which yields PCM frames from a thread-safe queue; the aiortc AudioStreamTrack
    pulls from this same queue via `recv()`.
    """

    def __init__(
        self,
        *,
        fmt: AudioStreamFormat,
        sink: Callable[[bytes], Any] | None = None,
        queue_maxsize: int = 200,
    ):
        self.fmt = fmt
        self._sink = sink
        self._buffer: list[bytes] = []
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=queue_maxsize)
        self._closed = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write-side API (called from recording thread / mic capture)
    # ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Push a chunk of raw PCM audio."""
        if self._closed:
            return
        if self._sink is not None:
            self._sink(data)
        else:
            with self._lock:
                self._buffer.append(data)
        # Non-blocking put; drop silently if the consumer falls behind.
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

    def close(self) -> None:
        """Signal EOF to all async consumers."""
        self._closed = True
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    # ------------------------------------------------------------------
    # Read-side API
    # ------------------------------------------------------------------

    def written_chunks(self) -> list[bytes]:
        """Return accumulated chunks (buffered mode only)."""
        with self._lock:
            return list(self._buffer)

    async def iter_chunks_async(self) -> AsyncIterator[bytes]:
        """Yield PCM chunks as they arrive; stops at close()."""
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                break
            yield chunk


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------

def pcm_s16le_stream(*, sample_rate: int = 48000, channels: int = 1) -> AudioStream:
    """Create a mono/stereo 16-bit PCM stream at `sample_rate` Hz."""
    return AudioStream(fmt=AudioStreamFormat(name="pcm_s16le", sample_rate=sample_rate, channels=channels))


def silent_frames(
    *,
    duration_s: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 1,
    frame_duration_ms: int = 20,
) -> list[bytes]:
    """Generate silence frames in 16-bit PCM for testing / warmup.

    Each frame is `frame_duration_ms` milliseconds of silence.
    Total frames = ceil(duration_s / (frame_duration_ms / 1000)).
    """
    frame_samples = sample_rate * frame_duration_ms // 1000
    frame_bytes = frame_samples * channels * 2  # 16-bit = 2 bytes/sample
    n_frames = max(1, int(duration_s * 1000 / frame_duration_ms))
    return [b"\x00" * frame_bytes for _ in range(n_frames)]
