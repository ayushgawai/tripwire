import asyncio
import math
import time

import pytest

from backend.audio import FRAME_BYTES
from backend.audio.file_replay import FileReplaySource


def collect(src, limit=None):
    async def main():
        frames = []
        async with src:
            async for f in src:
                frames.append(f)
                if limit and len(frames) >= limit:
                    break
        return frames

    return asyncio.run(main())


def test_16k_mono_frames(make_wav):
    p = make_wav(seconds=0.3, rate=16000, channels=1)  # 4800 samples = 15 frames
    src = FileReplaySource(p, realtime=False)
    assert src.source_label == "file_replay"
    frames = collect(src)
    assert len(frames) == 15
    assert all(len(f.data) == FRAME_BYTES for f in frames)
    assert [f.seq for f in frames] == list(range(15))
    assert all(b.timestamp >= a.timestamp for a, b in zip(frames, frames[1:]))


def test_48k_stereo_converted(make_wav):
    p = make_wav(seconds=0.31, rate=48000, channels=2)  # -> 4960 samples -> 15.5 -> 16 frames
    frames = collect(FileReplaySource(p, realtime=False))
    assert len(frames) == math.ceil(4960 / 320)
    assert all(len(f.data) == FRAME_BYTES for f in frames)
    assert frames[-1].data[-100:] == b"\x00" * 100  # zero-padded tail


def test_realtime_pacing(make_wav):
    p = make_wav(seconds=0.3)
    t0 = time.monotonic()
    frames = collect(FileReplaySource(p, realtime=True))
    elapsed = time.monotonic() - t0
    assert len(frames) == 15
    # last frame scheduled at 14*20ms = 0.28 s
    assert 0.22 < elapsed < 0.9


def test_stop_ends_iteration(make_wav):
    p = make_wav(seconds=1.0)
    src = FileReplaySource(p, realtime=True, loop=True)

    async def main():
        n = 0
        async with src:
            async for _ in src:
                n += 1
                if n == 5:
                    asyncio.get_running_loop().call_later(0.05, lambda: asyncio.ensure_future(src.stop()))
        return n

    n = asyncio.run(asyncio.wait_for(main(), timeout=5))
    assert 5 <= n < 20


def test_loop_mode(make_wav):
    p = make_wav(seconds=0.1)  # 5 frames
    frames = collect(FileReplaySource(p, realtime=False, loop=True), limit=12)
    assert len(frames) == 12 and frames[-1].seq == 11


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        FileReplaySource(tmp_path / "nope.wav")


def test_not_a_wav(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_bytes(b"not a wav at all" * 10)
    with pytest.raises(ValueError):
        FileReplaySource(p)


def test_iter_before_start(make_wav):
    src = FileReplaySource(make_wav(), realtime=False)

    async def main():
        async for _ in src:
            pass

    with pytest.raises(RuntimeError):
        asyncio.run(main())
