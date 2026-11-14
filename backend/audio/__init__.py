"""Tripwire audio input layer: wearable / laptop mic / WAV replay -> 16 kHz mono linear16."""

from .base import (
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
from .factory import get_audio_source, open_audio_source

__all__ = [
    "AudioFrame",
    "AudioSource",
    "FrameChunker",
    "rms_dbfs",
    "to_pcm16_mono_16k",
    "get_audio_source",
    "open_audio_source",
    "SAMPLE_RATE",
    "CHANNELS",
    "SAMPLE_WIDTH",
    "ENCODING",
    "FRAME_MS",
    "FRAME_SAMPLES",
    "FRAME_BYTES",
]
