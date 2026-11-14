import asyncio
import time

import numpy as np
import pytest

from backend.audio import (
    CHANNELS,
    ENCODING,
    FRAME_BYTES,
    FRAME_MS,
    FRAME_SAMPLES,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    AudioFrame,
    AudioSource,
    FrameChunker,
    rms_dbfs,
    to_pcm16_mono_16k,
)


def test_constants():
    assert (SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH, ENCODING) == (16000, 1, 2, "linear16")
    assert (FRAME_MS, FRAME_SAMPLES, FRAME_BYTES) == (20, 320, 640)


class FakeSource(AudioSource):
    def __init__(self, n=5):
        self.n = n
        self.started = False
        self.stop_calls = 0
        self._stop = None

    @property
    def source_label(self):
        return "fake"

    async def start(self):
        self.started = True
        self._stop = asyncio.Event()

    async def stop(self):
        self.stop_calls += 1
        if self._stop:
            self._stop.set()

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i in range(self.n):
            if self._stop.is_set():
                return
            yield AudioFrame(b"\x00" * FRAME_BYTES, i, time.monotonic())
            await asyncio.sleep(0)


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        AudioSource()  # type: ignore[abstract]


def test_fake_source_contract():
    src = FakeSource(5)

    async def main():
        frames = []
        async with src as s:
            assert s is src and src.started
            async for f in s:
                frames.append(f)
        await src.stop()  # idempotent
        return frames

    frames = asyncio.run(main())
    assert [f.seq for f in frames] == list(range(5))
    assert all(len(f.data) == FRAME_BYTES for f in frames)
    assert src.stop_calls == 2
    assert (src.sample_rate, src.channels, src.encoding, src.frame_ms) == (16000, 1, "linear16", 20)
    with pytest.raises(Exception):
        frames[0].seq = 9  # frozen


def test_stop_ends_iteration():
    src = FakeSource(1000)

    async def main():
        got = 0
        async with src:
            async for _ in src:
                got += 1
                if got == 3:
                    await src.stop()
        return got

    assert asyncio.run(main()) == 3


def test_frame_chunker_exact():
    ch = FrameChunker()
    data = bytes(range(256)) * 10  # 2560 bytes = 4 frames exactly
    out = []
    for i in range(0, len(data), 77):  # odd-sized pushes (77 is odd -> crosses sample boundary)
        out.extend(ch.push(data[i:i + 77]))
    assert len(out) == 4 and all(len(f) == FRAME_BYTES for f in out)
    assert b"".join(out) == data
    assert ch.pending == 0 and ch.flush() is None


def test_frame_chunker_remainder_and_pad():
    ch = FrameChunker()
    assert ch.push(b"\x01" * 1000) == [b"\x01" * 640]
    assert ch.pending == 360
    tail = ch.flush(pad=True)
    assert len(tail) == 640 and tail[:360] == b"\x01" * 360 and tail[360:] == b"\x00" * 280


def test_resample_44k_stereo_to_16k_mono():
    n = 44100
    t = np.arange(n) / 44100
    left = 0.5 * np.sin(2 * np.pi * 440 * t)
    stereo = np.stack([left, left], axis=1)
    out = to_pcm16_mono_16k((stereo * 32767).astype(np.int16), 44100, 2)
    samples = np.frombuffer(out, dtype="<i2")
    assert abs(samples.size - 16000) <= 1
    # amplitude preserved approx (0.5 FS sine ~ -9 dBFS)
    assert -10.5 < rms_dbfs(out) < -8.0


def test_interleaved_1d_and_downmix_mean():
    inter = np.array([1000, -1000, 2000, 0], dtype=np.int16)  # 2 frames, 2 ch
    out = np.frombuffer(to_pcm16_mono_16k(inter, 16000, 2), dtype="<i2")
    assert out.tolist() == [0, 1000]


def test_float_clipping():
    x = np.array([2.0, -2.0, 0.0, 0.5], dtype=np.float32)
    out = np.frombuffer(to_pcm16_mono_16k(x, 16000, 1), dtype="<i2")
    assert out[0] == 32767 and out[1] == -32768 and out[2] == 0
    assert abs(int(out[3]) - 16384) <= 1


def test_rms_dbfs():
    assert rms_dbfs(b"\x00" * 640) == float("-inf")
    full = (np.ones(320) * 32767).astype("<i2").tobytes()
    assert abs(rms_dbfs(full)) < 0.01
