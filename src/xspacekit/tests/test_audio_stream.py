from __future__ import annotations

import asyncio
import pytest

from xspacekit.audio.audio_stream import AudioStream, pcm_s16le_stream, silent_frames


def test_audio_stream_buffered_mode() -> None:
    stream = pcm_s16le_stream()
    assert stream.fmt.name == "pcm_s16le"
    assert stream.fmt.sample_rate == 48000
    assert stream.fmt.channels == 1

    stream.write(b"hello")
    stream.write(b"world")

    chunks = stream.written_chunks()
    assert chunks == [b"hello", b"world"]


def test_silent_frames_generation() -> None:
    frames = silent_frames(duration_s=0.1, sample_rate=48000, channels=1, frame_duration_ms=20)
    # 0.1s / 0.02s = 5 frames
    assert len(frames) == 5
    for f in frames:
        assert isinstance(f, bytes)
        assert len(f) > 0


@pytest.mark.anyio
async def test_audio_stream_async_generator() -> None:
    stream = pcm_s16le_stream()

    async def producer() -> None:
        await asyncio.sleep(0.01)
        stream.write(b"chunk1")
        stream.write(b"chunk2")
        stream.close()

    async def consumer() -> list[bytes]:
        res = []
        async for chunk in stream.iter_chunks_async():
            res.append(chunk)
        return res

    _, received = await asyncio.gather(producer(), consumer())
    assert received == [b"chunk1", b"chunk2"]
