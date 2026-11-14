"""Wearable (Vexo Band) audio source -- UNVERIFIED (no hardware tested).

UNVERIFIED: no hardware was tested and no Vexo device/audio SDK is publicly
documented (checked 2026-11-14). Public facts only:
  * vexoai.com: "The Band connects to the Vexo app over Bluetooth"; the Band
    "can't work without your phone".
  * vexoai.com/privacy: iOS + Android apps; Band audio is streamed by the phone
    to AssemblyAI for transcription; phone is the primary store.
  * vexoai.com/developers/mcp: the only public developer surface is a
    read-only MCP server (transcripts/memories, scope vexo:read). No raw audio.
  * RuntimeWire (Oct 2026) lists Bluetooth LE in the spec.
So the most likely real transport is a proprietary BLE GATT stream to the
phone app. Whatever "supplied SDK" the organisers hand out supersedes this file.

Must be confirmed on hardware (record answers in the build plan):
  1. Does the Band pair with a laptop at all (Windows 11 / macOS)? Does it show
     up as an OS audio input device (HFP/headset)? -> mode "input_device".
  2. If BLE only: service UUID, audio characteristic UUID, whether notify must
     be enabled by a control write first, MTU.
  3. Codec (PCM16 / Opus / ADPCM / mu-law), sample rate, channel count,
     per-packet header bytes, packet duration.
  4. Whether the phone app must be closed/unpaired for a laptop to connect
     (BLE peripherals usually accept one central at a time).
  5. Latency end-to-end and dropout behaviour.

Modes (env WEARABLE_TRANSPORT):
  input_device (default) -- capture an OS input device whose name contains
      WEARABLE_DEVICE_NAME (default "Vexo") via sounddevice, convert to the
      contract (16 kHz mono int16 LE, 20 ms / 640-byte frames).
  ble -- bleak skeleton. Needs WEARABLE_BLE_ADDRESS and
      WEARABLE_BLE_AUDIO_CHAR_UUID; codec via WEARABLE_BLE_CODEC
      ("pcm16" | "opus"), WEARABLE_BLE_SAMPLE_RATE, WEARABLE_BLE_CHANNELS,
      WEARABLE_BLE_HEADER_BYTES. Raises NotImplementedError where unknown.

Optional deps (lazy-imported): sounddevice (input_device), bleak (ble),
opuslib + system libopus (ble/opus). This module never fabricates frames.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncIterator, Optional

import numpy as np

from .base import (
    CHANNELS,
    ENCODING,
    FRAME_MS,
    SAMPLE_RATE,
    AudioFrame,
    AudioSource,
    FrameChunker,
    to_pcm16_mono_16k,
)

_UNVERIFIED_BLE = "UNVERIFIED: needs vendor characteristic/codec"
log = logging.getLogger(__name__)
# Substrings that match ordinary laptop/headset mics; refusing them keeps the
# "wearable" label honest (a generic match would mislabel laptop audio).
_GENERIC_DEVICE_NAMES = {"microphone", "mic", "realtek", "headset", "input", "audio",
                         "default", "array", "usb", "bluetooth", "hands-free", "airpods"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    except ImportError:
        pass
_SENTINEL = object()


class WearableAudioSource(AudioSource):
    """Audio from the Vexo wearable. See module docstring: UNVERIFIED."""

    def __init__(self, device_name: Optional[str] = None, **_ignored) -> None:
        _load_dotenv()
        self._transport = os.getenv("WEARABLE_TRANSPORT", "input_device").strip().lower()
        self._device_name = (device_name or os.getenv("WEARABLE_DEVICE_NAME", "Vexo")).strip()
        self._ble_address = os.getenv("WEARABLE_BLE_ADDRESS", "").strip()
        self._ble_char_uuid = os.getenv("WEARABLE_BLE_AUDIO_CHAR_UUID", "").strip()
        self._ble_codec = os.getenv("WEARABLE_BLE_CODEC", "").strip().lower()
        self._ble_rate = _env_int("WEARABLE_BLE_SAMPLE_RATE", 16000)
        self._ble_channels = _env_int("WEARABLE_BLE_CHANNELS", 1)
        self._ble_header_bytes = _env_int("WEARABLE_BLE_HEADER_BYTES", 0)

        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._chunker = FrameChunker()
        self._seq = 0
        self._running = False
        self._stream = None  # sounddevice.InputStream
        self._ble_client = None  # bleak.BleakClient
        self._opus_decoder = None
        self._error: Optional[BaseException] = None

    # ---- contract properties -------------------------------------------
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
    def source_label(self) -> str:
        return "wearable"

    # ---- probe (sync; any exception => factory falls back to laptop mic) --
    def probe(self) -> None:
        if self._transport == "input_device":
            self._find_input_device()
        elif self._transport == "ble":
            self._check_ble_config()
            try:
                import bleak  # noqa: F401
            except ImportError as exc:
                raise RuntimeError("WEARABLE_TRANSPORT=ble requires `pip install bleak`") from exc
            # NOTE: does not scan/connect here (probe is sync and must be fast).
        else:
            raise RuntimeError(
                f"Unknown WEARABLE_TRANSPORT={self._transport!r} (use input_device|ble)"
            )

    # ---- lifecycle --------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=500)  # ~10 s of 20 ms frames
        self._chunker = FrameChunker()
        self._seq = 0
        self._error = None
        if self._transport == "input_device":
            await self._start_input_device()
        elif self._transport == "ble":
            await self._start_ble()
        else:
            raise RuntimeError(f"Unknown WEARABLE_TRANSPORT={self._transport!r}")
        self._running = True

    async def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            stream, self._stream = self._stream, None
            try:
                stream.stop()
            finally:
                stream.close()
        if self._ble_client is not None:
            client, self._ble_client = self._ble_client, None
            try:
                if self._ble_char_uuid:
                    await client.stop_notify(self._ble_char_uuid)
            except Exception:
                pass
            await client.disconnect()
        if self._queue is not None:
            try:
                self._queue.put_nowait(_SENTINEL)
            except asyncio.QueueFull:
                pass

    async def __aiter__(self) -> AsyncIterator[AudioFrame]:  # type: ignore[override]
        if self._queue is None:
            raise RuntimeError("WearableAudioSource.start() must be called before iterating")
        while True:
            item = await self._queue.get()
            if item is _SENTINEL:
                if self._error is not None:
                    raise RuntimeError(f"Wearable audio stream failed: {self._error}") from self._error
                return
            yield item

    async def __aenter__(self) -> "WearableAudioSource":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    # ---- shared frame emission (runs on the event loop thread) ------------
    def _emit_pcm16_16k(self, pcm: bytes) -> None:
        if not self._running or self._queue is None:
            return
        now = time.monotonic()
        for frame in self._chunker.push(pcm):
            af = AudioFrame(data=frame, seq=self._seq, timestamp=now)
            self._seq += 1
            try:
                self._queue.put_nowait(af)
            except asyncio.QueueFull:
                # Consumer is behind: drop oldest to keep latency bounded.
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(af)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def _fail(self, exc: BaseException) -> None:
        self._error = exc
        self._running = False
        if self._queue is not None:
            try:
                self._queue.put_nowait(_SENTINEL)
            except asyncio.QueueFull:
                pass

    # ---- mode A: OS input device (Bluetooth headset / HFP) ----------------
    def _find_input_device(self) -> tuple[int, dict]:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("Wearable input_device mode requires `pip install sounddevice`") from exc
        needle = self._device_name.lower()
        if not needle:
            raise RuntimeError("WEARABLE_DEVICE_NAME is empty")
        if needle in _GENERIC_DEVICE_NAMES:
            raise RuntimeError(
                f"WEARABLE_DEVICE_NAME={self._device_name!r} is too generic and could match a "
                f"non-wearable mic; use the band's specific device name"
            )
        matches = [
            (idx, dev)
            for idx, dev in enumerate(sd.query_devices())
            if dev.get("max_input_channels", 0) > 0 and needle in str(dev.get("name", "")).lower()
        ]
        if not matches:
            names = [d["name"] for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
            raise RuntimeError(
                f"No audio input device name contains {self._device_name!r}. "
                f"Pair the band as a Bluetooth headset or set WEARABLE_DEVICE_NAME. "
                f"Input devices seen: {names}"
            )
        # On Windows the same device appears once per host API (MME/WASAPI/...);
        # the first match is fine for capture.
        return matches[0]

    async def _start_input_device(self) -> None:
        import sounddevice as sd

        idx, dev = self._find_input_device()
        src_rate = int(dev.get("default_samplerate") or SAMPLE_RATE)
        src_channels = 1 if dev["max_input_channels"] >= 1 else dev["max_input_channels"]
        loop = self._loop
        assert loop is not None

        def callback(indata, frames, time_info, status) -> None:  # audio thread
            samples = np.array(indata, dtype=np.int16, copy=True)
            pcm = to_pcm16_mono_16k(samples, src_rate, src_channels)
            loop.call_soon_threadsafe(self._emit_pcm16_16k, pcm)

        self._stream = sd.InputStream(
            device=idx,
            samplerate=src_rate,
            channels=src_channels,
            dtype="int16",
            blocksize=int(src_rate * FRAME_MS / 1000),
            callback=callback,
        )
        self._stream.start()
        log.warning("audio source: wearable (UNVERIFIED adapter) via OS input device %r rate=%s "
                    "-- confirm this device really is the band", dev.get("name"), src_rate)

    # ---- mode B: BLE GATT stream (skeleton) -------------------------------
    def _check_ble_config(self) -> None:
        if not self._ble_address or not self._ble_char_uuid:
            raise NotImplementedError(
                f"{_UNVERIFIED_BLE}: set WEARABLE_BLE_ADDRESS and WEARABLE_BLE_AUDIO_CHAR_UUID"
            )
        if self._ble_codec not in ("pcm16", "opus"):
            raise NotImplementedError(
                f"{_UNVERIFIED_BLE}: WEARABLE_BLE_CODEC={self._ble_codec!r} unsupported "
                f"(implemented: pcm16, opus)"
            )

    async def _start_ble(self) -> None:
        self._check_ble_config()
        from bleak import BleakClient

        if self._ble_codec == "opus":
            try:
                import opuslib
            except ImportError as exc:
                raise RuntimeError("Opus decode requires `pip install opuslib` + system libopus") from exc
            self._opus_decoder = opuslib.Decoder(self._ble_rate, self._ble_channels)

        client = BleakClient(self._ble_address, disconnected_callback=lambda _c: self._loop.call_soon_threadsafe(
            self._fail, RuntimeError("BLE device disconnected")) if self._running else None)
        await client.connect()
        self._ble_client = client
        # UNVERIFIED: the vendor may require a control-characteristic write to
        # begin streaming. Add it here once known.
        await client.start_notify(self._ble_char_uuid, self._on_ble_packet)

    def _on_ble_packet(self, _sender, data: bytearray) -> None:
        # bleak delivers notifications on the event loop thread.
        try:
            payload = bytes(data[self._ble_header_bytes:])
            if not payload:
                return
            if self._ble_codec == "pcm16":
                samples = np.frombuffer(payload[: len(payload) // 2 * 2], dtype="<i2")
            else:  # opus; frame_size = max samples/channel (120 ms upper bound)
                decoded = self._opus_decoder.decode(payload, int(self._ble_rate * 0.12))
                samples = np.frombuffer(decoded, dtype="<i2")
            if self._ble_channels > 1:
                samples = samples[: len(samples) // self._ble_channels * self._ble_channels]
                samples = samples.reshape(-1, self._ble_channels)
            pcm = to_pcm16_mono_16k(samples, self._ble_rate, self._ble_channels)
            self._emit_pcm16_16k(pcm)
        except Exception as exc:  # surface decode errors instead of silently faking audio
            self._fail(exc)
