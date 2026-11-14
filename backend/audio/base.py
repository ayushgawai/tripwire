"""Audio source contract shared by every Tripwire audio input.

Every source yields 20 ms frames of 16 kHz mono signed 16-bit little-endian PCM
(Deepgram ``encoding=linear16&sample_rate=16000&channels=1``).

Consumers use::

    async with source:
        async for frame in source:
            send(frame.data)
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from typing import AsyncIterator

import numpy as np

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes per sample (int16)
ENCODING = "linear16"
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 320
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_WIDTH * CHANNELS  # 640


@dataclass(frozen=True)
class AudioFrame:
    """One 20 ms frame of contract-format PCM."""

    data: bytes  # exactly FRAME_BYTES of int16 LE mono @ 16 kHz
    seq: int  # monotonically increasing per source, starting at 0
    timestamp: float  # time.monotonic() at capture


class AudioSource(abc.ABC):
    """Abstract async audio source producing :class:`AudioFrame` objects."""

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def channels(self) -> int:
        return CHANNELS

    @property
    def encoding(self) -> str:
        return ENCODING

    @property
    def frame_ms(self) -> int:
        return FRAME_MS

    @property
    @abc.abstractmethod
    def source_label(self) -> str:
        """Short label, e.g. "laptop_mic", "file_replay", "wearable"."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin capturing. Must be called before iterating."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop capturing. Idempotent; ends any active iteration."""

    @abc.abstractmethod
    def __aiter__(self) -> AsyncIterator[AudioFrame]:
        """Async iterator of frames that ends once the source is stopped."""

    async def __aenter__(self) -> "AudioSource":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} label={self.source_label}>"


class FrameChunker:
    """Accumulates arbitrary-length int16 PCM bytes and emits exact frames."""

    def __init__(self, frame_bytes: int = FRAME_BYTES) -> None:
        if frame_bytes <= 0 or frame_bytes % SAMPLE_WIDTH:
            raise ValueError("frame_bytes must be a positive multiple of SAMPLE_WIDTH")
        self.frame_bytes = frame_bytes
        self._buf = bytearray()

    def push(self, data: bytes) -> list[bytes]:
        """Add data; return every complete frame now available."""
        if data:
            self._buf.extend(data)
        n = len(self._buf) // self.frame_bytes
        if n == 0:
            return []
        fb = self.frame_bytes
        frames = [bytes(self._buf[i * fb:(i + 1) * fb]) for i in range(n)]
        del self._buf[: n * fb]
        return frames

    def flush(self, pad: bool = True) -> bytes | None:
        """Return the buffered remainder (zero-padded to a full frame if pad)."""
        if not self._buf:
            return None
        rem = bytes(self._buf)
        self._buf.clear()
        if pad:
            rem = rem + b"\x00" * (self.frame_bytes - len(rem))
        return rem

    @property
    def pending(self) -> int:
        return len(self._buf)


def to_pcm16_mono_16k(samples: np.ndarray, src_rate: int, channels: int) -> bytes:
    """Convert audio samples to contract format (16 kHz mono int16 LE bytes).

    ``samples`` may be 1-D interleaved or 2-D (frames, channels); dtype may be
    any int (int8/uint8/int16/int32, scaled by its full range) or float
    (expected in [-1, 1]). Downmix by mean, resample by linear interpolation,
    clip to int16.
    """
    if src_rate <= 0:
        raise ValueError("src_rate must be positive")
    if channels <= 0:
        raise ValueError("channels must be positive")
    arr = np.asarray(samples)
    if arr.size == 0:
        return b""

    # Normalise to float64 in [-1, 1].
    if arr.dtype == np.uint8:
        x = (arr.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(arr.dtype, np.integer):
        x = arr.astype(np.float64) / float(-np.iinfo(arr.dtype).min)
    else:
        x = arr.astype(np.float64)

    # Shape to (frames, channels) and downmix.
    if x.ndim == 1:
        usable = (x.size // channels) * channels
        x = x[:usable].reshape(-1, channels)
    elif x.ndim != 2:
        raise ValueError("samples must be 1-D or 2-D")
    mono = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]

    # Resample (linear interpolation).
    if src_rate != SAMPLE_RATE and mono.size > 0:
        n_out = int(round(mono.size * SAMPLE_RATE / src_rate))
        if n_out <= 0:
            return b""
        t_out = np.arange(n_out, dtype=np.float64) * (src_rate / SAMPLE_RATE)
        t_in = np.arange(mono.size, dtype=np.float64)
        mono = np.interp(t_out, t_in, mono)

    out = np.clip(np.round(mono * 32767.0), -32768, 32767).astype("<i2")
    return out.tobytes()


def rms_dbfs(frame_bytes: bytes) -> float:
    """RMS level of int16 LE PCM in dBFS (full-scale sine ~ -3 dB; silence -inf)."""
    if not frame_bytes:
        return float("-inf")
    a = np.frombuffer(frame_bytes[: len(frame_bytes) // 2 * 2], dtype="<i2").astype(np.float64)
    if a.size == 0:
        return float("-inf")
    rms = math.sqrt(float(np.mean(a * a)))
    if rms <= 0:
        return float("-inf")
    return 20.0 * math.log10(rms / 32768.0)
