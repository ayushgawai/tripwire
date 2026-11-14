import asyncio
import logging
import subprocess
import sys
import types
from pathlib import Path

import pytest

from backend.audio import factory
from backend.audio.factory import get_audio_source, open_audio_source
from backend.audio.file_replay import FileReplaySource
from backend.audio.laptop_mic import LaptopMicSource

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setattr(factory, "_dotenv_loaded", True)  # don't read a real .env in tests
    monkeypatch.delenv("AUDIO_SOURCE", raising=False)
    monkeypatch.delenv("AUDIO_FILE_PATH", raising=False)


@pytest.fixture
def no_sounddevice(monkeypatch):
    """Make any accidental hardware access fail loudly."""
    monkeypatch.setitem(sys.modules, "sounddevice", None)


def test_default_is_laptop_without_hardware(no_sounddevice):
    src = get_audio_source()
    assert isinstance(src, LaptopMicSource) and src.source_label == "laptop_mic"


def test_env_selects_kind(monkeypatch, make_wav):
    monkeypatch.setenv("AUDIO_SOURCE", "file")
    monkeypatch.setenv("AUDIO_FILE_PATH", str(make_wav()))
    src = get_audio_source()
    assert isinstance(src, FileReplaySource)


def test_file_kind(make_wav):
    src = get_audio_source("file", path=make_wav(), realtime=False)
    assert src.source_label == "file_replay" and src.realtime is False


def test_file_without_path():
    with pytest.raises(ValueError, match="path"):
        get_audio_source("file")


def test_unknown_kind():
    with pytest.raises(ValueError) as ei:
        get_audio_source("bluetooth")
    for k in ("laptop", "file", "wearable"):
        assert k in str(ei.value)


def test_wearable_missing_falls_back(monkeypatch, caplog, no_sounddevice):
    # None in sys.modules -> ImportError on import
    monkeypatch.setitem(sys.modules, "backend.audio.wearable", None)
    with caplog.at_level(logging.WARNING):
        src = get_audio_source("wearable")
    assert isinstance(src, LaptopMicSource) and src.source_label == "laptop_mic"
    assert "falling back to laptop_mic" in caplog.text and "NOT from the wearable" in caplog.text


def _fake_wearable_module(cls):
    mod = types.ModuleType("backend.audio.wearable")
    mod.WearableAudioSource = cls
    return mod


def test_wearable_constructor_raises(monkeypatch, caplog, no_sounddevice):
    class Boom:
        def __init__(self, **kw):
            raise RuntimeError("no BLE adapter")

    monkeypatch.setitem(sys.modules, "backend.audio.wearable", _fake_wearable_module(Boom))
    with caplog.at_level(logging.WARNING):
        src = get_audio_source("wearable")
    assert src.source_label == "laptop_mic"
    assert "no BLE adapter" in caplog.text


def test_wearable_probe_fails(monkeypatch, no_sounddevice):
    class ProbeFails:
        def probe(self):
            raise ConnectionError("device not paired")

    monkeypatch.setitem(sys.modules, "backend.audio.wearable", _fake_wearable_module(ProbeFails))
    assert get_audio_source("wearable").source_label == "laptop_mic"


def test_wearable_ok_returned(monkeypatch):
    class Good:
        source_label = "wearable"

        def __init__(self, **kw):
            self.kw = kw

        def probe(self):
            return True

    monkeypatch.setitem(sys.modules, "backend.audio.wearable", _fake_wearable_module(Good))
    src = get_audio_source("wearable", mac="AA:BB")
    assert isinstance(src, Good) and src.kw == {"mac": "AA:BB"}


def test_open_wearable_start_fails_falls_back(monkeypatch, caplog):
    class StartFails:
        source_label = "wearable"

        async def start(self):
            raise OSError("stream refused")

        async def stop(self):
            pass

    started = []

    async def fake_start(self):
        started.append(True)

    monkeypatch.setitem(sys.modules, "backend.audio.wearable", _fake_wearable_module(StartFails))
    monkeypatch.setattr(LaptopMicSource, "start", fake_start)
    with caplog.at_level(logging.WARNING):
        src = asyncio.run(open_audio_source("wearable"))
    assert isinstance(src, LaptopMicSource) and started == [True]
    assert "stream refused" in caplog.text


def test_open_file_source_started(make_wav):
    async def main():
        src = await open_audio_source("file", path=make_wav(), realtime=False)
        frames = [f async for f in src]
        await src.stop()
        return frames

    assert len(asyncio.run(main())) == 15


def test_demo_make_wav_and_file_mode(tmp_path):
    wav = tmp_path / "tone.wav"
    r1 = subprocess.run([sys.executable, "-m", "backend.audio.demo", "--make-test-wav", str(wav)],
                        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert r1.returncode == 0, r1.stderr
    assert wav.is_file()
    r2 = subprocess.run([sys.executable, "-m", "backend.audio.demo", "--source", "file",
                         "--file", str(wav), "--seconds", "0.5"],
                        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "file_replay" in r2.stdout and "frames" in r2.stdout
