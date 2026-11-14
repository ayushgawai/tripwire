"""Laptop microphone source (fallback when the wearable is unavailable)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

import numpy as np

from .base import (
    CHANNELS,
    FRAME_MS,
    FRAME_SAMPLES,
    SAMPLE_RATE,
    AudioFrame,
    AudioSource,
    FrameChunker,
    to_pcm16_mono_16k,
)

log = logging.getLogger(__name__)

_STOP = object()


class LaptopMicSource(AudioSource):
    """Captures from a local input device via sounddevice (PortAudio).

    The constructor never touches hardware; the device is opened in start().
    ``device`` may be an index, a name substring, or None for the default input.
    """

    def __init__(self, device: int | str | None = None, max_queue_frames: int = 250) -> None:
        self._device_arg = device
        self._max_queue = max_queue_frames
        self._queue: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None
        self._chunker = FrameChunker()
        self._seq = 0
        self._running = False
        self._stopped = False
        self.dropped_frames = 0
        self.device_name: str | None = None
        self.capture_rate: int | None = None

    @property
    def source_label(self) -> str:
        return "laptop_mic"

    # -- device helpers ---------------------------------------------------
    @staticmethod
    def _resolve_device(sd, device):
        if device is None or isinstance(device, int):
            return device
        if isinstance(device, str) and device.strip().isdigit():
            return int(device)
        needle = str(device).lower()
        for idx, info in enumerate(sd.query_devices()):
            if info.get("max_input_channels", 0) > 0 and needle in info["name"].lower():
                return idx
        raise ValueError(f"no input device matching {device!r}")

    # -- lifecycle --------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        import sounddevice as sd  # lazy: keep imports/tests free of PortAudio

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self._max_queue)
        self._chunker = FrameChunker()
        self._seq = 0
        self._stopped = False
        self.dropped_frames = 0

        device = self._resolve_device(sd, self._device_arg)
        info = sd.query_devices(device, kind="input")
        self.device_name = info["name"]

        try:
            sd.check_input_settings(device=device, channels=CHANNELS, dtype="int16",
                                    samplerate=SAMPLE_RATE)
            stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
                blocksize=FRAME_SAMPLES, device=device, callback=self._callback_native,
            )
            self.capture_rate = SAMPLE_RATE
        except Exception as e:  # device rejects 16 kHz -> capture natively and convert
            rate = int(info["default_samplerate"])
            log.info("device rejected %d Hz (%s); capturing at %d Hz and converting",
                     SAMPLE_RATE, e, rate)
            stream = sd.RawInputStream(
                samplerate=rate, channels=1, dtype="int16",
                blocksize=int(round(rate * FRAME_MS / 1000)), device=device,
                callback=self._callback_convert,
            )
            self.capture_rate = rate

        self._stream = stream
        stream.start()
        self._running = True
        log.info("audio source: laptop_mic (NOT the wearable) device=%s rate=%s",
                 self.device_name, self.capture_rate)

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._running = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        if self._queue is not None:
            self._put(_STOP, force=True)
        if self.dropped_frames:
            log.warning("laptop_mic dropped %d frames (consumer too slow)", self.dropped_frames)

    # -- PortAudio callback thread -> event loop --------------------------
    def _callback_native(self, indata, frames, time_info, status) -> None:
        self._emit(bytes(indata))

    def _callback_convert(self, indata, frames, time_info, status) -> None:
        samples = np.frombuffer(bytes(indata), dtype="<i2")
        self._emit(to_pcm16_mono_16k(samples, self.capture_rate, 1))

    def _emit(self, pcm: bytes) -> None:
        loop = self._loop
        if loop is None or self._stopped:
            return
        now = time.monotonic()
        for chunk in self._chunker.push(pcm):
            try:
                loop.call_soon_threadsafe(self._put, (chunk, now))
            except RuntimeError:  # loop closed
                return

    def _put(self, item, force: bool = False) -> None:
        q = self._queue
        if q is None:
            return
        if item is not _STOP and self._stopped:
            return
        while q.full():
            try:
                q.get_nowait()
                if not force:
                    self.dropped_frames += 1
            except asyncio.QueueEmpty:
                break
        q.put_nowait(item)

    # -- iteration --------------------------------------------------------
    def __aiter__(self) -> AsyncIterator[AudioFrame]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[AudioFrame]:
        if self._queue is None:
            raise RuntimeError("LaptopMicSource not started; use 'async with source:'")
        q = self._queue
        while True:
            item = await q.get()
            if item is _STOP:
                q.put_nowait(_STOP)  # let other iterators finish too
                return
            data, ts = item
            frame = AudioFrame(data=data, seq=self._seq, timestamp=ts)
            self._seq += 1
            yield frame
