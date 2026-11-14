"""Wearable adapter tests (no hardware). The adapter itself is UNVERIFIED on real hardware."""
import asyncio
import sys
import types

import numpy as np
import pytest

from backend.audio import factory
from backend.audio.base import FRAME_BYTES
from backend.audio.wearable import WearableAudioSource


def _fake_sd(devices):
    mod = types.ModuleType("sounddevice")
    mod.query_devices = lambda: devices
    return mod


def test_label_is_wearable():
    assert WearableAudioSource().source_label == "wearable"


def test_probe_raises_when_no_matching_input_device(monkeypatch):
    monkeypatch.setenv("WEARABLE_TRANSPORT", "input_device")
    monkeypatch.setitem(
        sys.modules, "sounddevice",
        _fake_sd([{"name": "Microphone (Realtek)", "max_input_channels": 2, "default_samplerate": 48000}]),
    )
    with pytest.raises(RuntimeError, match="No audio input device"):
        WearableAudioSource(device_name="Vexo").probe()


def test_probe_finds_named_device(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "sounddevice",
        _fake_sd([{"name": "Vexo Band Headset", "max_input_channels": 1, "default_samplerate": 16000}]),
    )
    WearableAudioSource(device_name="vexo").probe()  # case-insensitive, no exception


def test_ble_mode_unconfigured_is_unverified(monkeypatch):
    monkeypatch.setenv("WEARABLE_TRANSPORT", "ble")
    for k in ("WEARABLE_BLE_ADDRESS", "WEARABLE_BLE_AUDIO_CHAR_UUID", "WEARABLE_BLE_CODEC"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(NotImplementedError, match="UNVERIFIED"):
        WearableAudioSource().probe()


def test_factory_falls_back_to_laptop_when_band_absent(monkeypatch):
    monkeypatch.setenv("WEARABLE_TRANSPORT", "input_device")
    monkeypatch.setitem(sys.modules, "sounddevice", _fake_sd([]))
    src = factory.get_audio_source("wearable")
    assert src.source_label == "laptop_mic"


def test_ble_pcm16_packets_become_contract_frames(monkeypatch):
    monkeypatch.setenv("WEARABLE_BLE_CODEC", "pcm16")
    monkeypatch.setenv("WEARABLE_BLE_SAMPLE_RATE", "16000")

    async def run():
        src = WearableAudioSource()
        src._loop = asyncio.get_running_loop()
        src._queue = asyncio.Queue()
        src._running = True
        pkt = np.zeros(480, dtype="<i2").tobytes()  # 30 ms
        src._on_ble_packet(None, bytearray(pkt))
        src._on_ble_packet(None, bytearray(pkt))  # 60 ms total -> 3 frames
        frames = [src._queue.get_nowait() for _ in range(src._queue.qsize())]
        assert len(frames) == 3
        assert all(len(f.data) == FRAME_BYTES for f in frames)
        assert [f.seq for f in frames] == [0, 1, 2]

    asyncio.run(run())


def test_generic_device_name_rejected(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "sounddevice",
        _fake_sd([{"name": "Microphone (Realtek)", "max_input_channels": 2, "default_samplerate": 48000}]),
    )
    with pytest.raises(RuntimeError, match="too generic"):
        WearableAudioSource(device_name="Microphone").probe()


def test_blank_int_env_uses_default(monkeypatch):
    monkeypatch.setenv("WEARABLE_BLE_SAMPLE_RATE", "")
    assert WearableAudioSource()._ble_rate == 16000
