"""ElevenLabs TTS for the Tripwire assistant voice."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("tripwire.voice")


# In-memory store: utterance_id -> mp3 bytes
_AUDIO_CACHE: dict[str, bytes] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def speak(session_id: str, text: str) -> None:
    """Synthesise *text* via ElevenLabs and cache the mp3.

    Adds an ``assistant`` utterance to the transcript and publishes an
    ``assistant.spoke`` event.  Fires-and-forgets — exceptions are
    handled internally so this never blocks the caller.
    """
    from backend import session as sess

    ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
    utterance_id = f"ai_{__import__('uuid').uuid4().hex}"

    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        await sess.publish_event(session_id, "assistant.spoke", {
            "utterance_id": utterance_id,
            "text": text,
            "audio_url": None,
        })
        await sess.publish_event(session_id, "error", {
            "source": "elevenlabs",
            "message": "ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID missing",
        })
        return

    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        "?output_format=mp3_44100_64"
    )
    payload = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
    }

    audio_url = f"/api/sessions/{session_id}/assistant-audio/{utterance_id}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers={"xi-api-key": ELEVENLABS_API_KEY},
                json=payload,
            )
        if resp.status_code == 200:
            _AUDIO_CACHE[utterance_id] = resp.content
        else:
            audio_url = None
            logger.error(
                "ElevenLabs returned %s: %s", resp.status_code, resp.text[:200]
            )
            await sess.publish_event(session_id, "error", {
                "source": "elevenlabs",
                "message": f"HTTP {resp.status_code}",
            })
    except Exception as exc:
        logger.error("ElevenLabs TTS error: %s", exc)
        audio_url = None
        await sess.publish_event(session_id, "error", {
            "source": "elevenlabs",
            "message": str(exc),
        })

    # Add to transcript as "assistant" speaker
    utt = {
        "utterance_id": utterance_id,
        "speaker": "assistant",
        "text": text,
        "timestamp": _utc_now(),
    }
    sess.store.add_utterance(session_id, utt)
    await sess.publish_event(session_id, "transcript.final", utt)

    await sess.publish_event(session_id, "assistant.spoke", {
        "utterance_id": utterance_id,
        "text": text,
        "audio_url": audio_url,
    })


def get_cached_audio(utterance_id: str) -> bytes | None:
    """Return cached mp3 bytes for *utterance_id*, or None."""
    return _AUDIO_CACHE.get(utterance_id)
