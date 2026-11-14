"""Replay a WAV file as a contract-format audio source (demo/testing)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import wave
from typing import AsyncIterator

import numpy as np

from .base import FRAME_BYTES, FRAME_MS, AudioFrame, AudioSource, FrameChunker, to_pcm16_mono_16k

log = logging.getLogger(__name__)

_DTYPES = {1: np.uint8, 2: np.dtype("<i2"), 4: np.dtype("<i4")}


def load_wav_as_contract_pcm(path: str | os.PathLike) -> bytes:
    """Read a PCM WAV (8/16/24/32-bit int, any rate/channels) -> 16k mono int16 bytes."""
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"audio file not found: {path}")
    try:
        with wave.open(path, "rb") as wf:
            nch = wf.getnchannels()
            width = wf.getsampwidth()
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
    except wave.Error as e:
        raise ValueError(f"{path}: not a PCM WAV file ({e}); convert to 16-bit PCM WAV") from e

    if width == 3:  # 24-bit: expand to int32
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        i32 = (b[:, 0].astype(np.int32) << 8) | (b[:, 1].astype(np.int32) << 16) | (
            b[:, 2].astype(np.int32) << 24)
        samples = i32
    elif width in _DTYPES:
        samples = np.frombuffer(raw, dtype=_DTYPES[width])
    else:
        raise ValueError(f"{path}: unsupported sample width {width * 8}-bit; use 16-bit PCM WAV")
    return to_pcm16_mono_16k(samples, rate, nch)


class FileReplaySource(AudioSource):
    """Yields frames from a WAV file, paced at real time by default.

    The file is validated/loaded eagerly in the constructor so a bad path fails fast.
    """

    def __init__(self, path: str | os.PathLike, realtime: bool = True, loop: bool = False) -> None:
        self.path = os.fspath(path)
        self.realtime = realtime
        self.loop = loop
        self._pcm = load_wav_as_contract_pcm(self.path)
        if not self._pcm:
            raise ValueError(f"{self.path}: audio file contains no samples")
        chunker = FrameChunker()
        self._frames = chunker.push(self._pcm)
        tail = chunker.flush(pad=True)
        if tail:
            self._frames.append(tail)
        self._started = False
        self._stop_event: asyncio.Event | None = None
        self._stopped = False

    @property
    def source_label(self) -> str:
        return "file_replay"

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    async def start(self) -> None:
        if self._started and not self._stopped:
            return
        self._stop_event = asyncio.Event()
        self._started = True
        self._stopped = False
        log.info("audio source: file_replay (NOT the wearable) path=%s frames=%d realtime=%s",
                 self.path, len(self._frames), self.realtime)

    async def stop(self) -> None:
        self._stopped = True
        if self._stop_event is not None:
            self._stop_event.set()

    def __aiter__(self) -> AsyncIterator[AudioFrame]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[AudioFrame]:
        if not self._started or self._stop_event is None:
            raise RuntimeError("FileReplaySource not started; use 'async with source:'")
        stop_ev = self._stop_event
        period = FRAME_MS / 1000.0
        t0 = time.monotonic()
        seq = 0
        while not stop_ev.is_set():
            for data in self._frames:
                if stop_ev.is_set():
                    return
                if self.realtime:
                    # Absolute schedule from t0: no drift accumulation.
                    delay = (t0 + seq * period) - time.monotonic()
                    if delay > 0:
                        try:
                            await asyncio.wait_for(stop_ev.wait(), timeout=delay)
                            return  # stopped while waiting
                        except asyncio.TimeoutError:
                            pass
                else:
                    await asyncio.sleep(0)
                    if stop_ev.is_set():
                        return
                assert len(data) == FRAME_BYTES
                yield AudioFrame(data=data, seq=seq, timestamp=time.monotonic())
                seq += 1
            if not self.loop:
                return
