"""Pick an audio source: wearable (preferred) with automatic laptop-mic fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import AudioSource
from .file_replay import FileReplaySource
from .laptop_mic import LaptopMicSource

log = logging.getLogger(__name__)

VALID_KINDS = ("laptop", "file", "wearable")
_ALIASES = {"laptop_mic": "laptop", "mic": "laptop", "file_replay": "file"}

_dotenv_loaded = False


def _load_dotenv_once() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _normalise_kind(kind: str | None) -> str:
    _load_dotenv_once()
    k = (kind or os.environ.get("AUDIO_SOURCE") or "laptop").strip().lower()
    k = _ALIASES.get(k, k)
    if k not in VALID_KINDS:
        raise ValueError(f"unknown audio source kind {k!r}; valid values: {', '.join(VALID_KINDS)}")
    return k


def _fallback_warning(reason: object) -> None:
    log.warning("wearable unavailable (%s); falling back to laptop_mic -- audio is NOT from the wearable",
                reason)


def _laptop(kwargs: dict) -> LaptopMicSource:
    return LaptopMicSource(device=kwargs.get("device"))


def _make_wearable(kwargs: dict) -> AudioSource:
    from .wearable import WearableAudioSource  # lazy: module may not exist yet

    wkw = {k: v for k, v in kwargs.items() if k not in ("device", "path")}
    src = WearableAudioSource(**wkw)
    probe = getattr(src, "probe", None)
    if callable(probe):
        result = probe()
        if result is False:
            raise RuntimeError("probe() returned False")
    return src


def get_audio_source(kind: str | None = None, **kwargs) -> AudioSource:
    """Return an (unstarted) AudioSource.

    kind: "laptop" | "file" | "wearable"; defaults to env AUDIO_SOURCE or "laptop".
    kwargs: ``path`` (file; else env AUDIO_FILE_PATH), ``realtime``/``loop`` (file),
    ``device`` (laptop), anything else is passed to the wearable adapter.
    "wearable" never raises: any failure falls back to LaptopMicSource with a WARNING.
    """
    k = _normalise_kind(kind)
    if k == "laptop":
        return _laptop(kwargs)
    if k == "file":
        path = kwargs.get("path") or os.environ.get("AUDIO_FILE_PATH")
        if not path:
            raise ValueError("audio source 'file' requires a path (pass path=... or set AUDIO_FILE_PATH)")
        return FileReplaySource(path, realtime=kwargs.get("realtime", True),
                                loop=kwargs.get("loop", False))
    # wearable
    try:
        return _make_wearable(kwargs)
    except Exception as e:  # ImportError, constructor/probe failure, anything
        _fallback_warning(f"{type(e).__name__}: {e}")
        return _laptop(kwargs)


async def open_audio_source(kind: str | None = None, **kwargs) -> AudioSource:
    """Like get_audio_source() but returns a *started* source.

    If the wearable's start() raises, falls back to a started LaptopMicSource.
    Caller is responsible for ``await source.stop()``.
    """
    k = _normalise_kind(kind)
    src = get_audio_source(k, **kwargs)
    if k == "wearable" and not isinstance(src, LaptopMicSource):
        try:
            await src.start()
            return src
        except Exception as e:
            try:
                await src.stop()
            except Exception:
                pass
            _fallback_warning(f"start failed: {type(e).__name__}: {e}")
            src = _laptop(kwargs)
    await src.start()
    return src
