import sys
import wave
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def write_wav(path, seconds, rate, channels, freq=440.0, amp=0.5):
    n = int(round(seconds * rate))
    t = np.arange(n) / rate
    mono = amp * np.sin(2 * np.pi * freq * t)
    data = np.repeat(mono[:, None], channels, axis=1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return n


@pytest.fixture
def make_wav(tmp_path):
    def _make(name="t.wav", seconds=0.3, rate=16000, channels=1, **kw):
        p = tmp_path / name
        write_wav(p, seconds, rate, channels, **kw)
        return p

    return _make
