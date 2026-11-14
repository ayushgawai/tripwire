"""Deepgram STT WebSocket relay — pure parsing function + connection handler."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import websockets
from fastapi import status

logger = logging.getLogger("tripwire.stt")


# ── Pure function (unit-testable) ────────────────────────────────────────────


def parse_deepgram_message(msg: dict, buffer: list[str]) -> str | None:
    """Process a single Deepgram JSON message.

    Accumulates transcripts from ``is_final`` segments in *buffer*.
    Returns the complete utterance text when ``speech_final`` or an
    ``UtteranceEnd`` message arrives, otherwise ``None``.
    """
    msg_type = msg.get("type", "")

    if msg_type == "UtteranceEnd":
        if buffer:
            text = " ".join(buffer).strip()
            buffer.clear()
            return text
        return None

    if msg_type == "KeepAlive":
        return None

    # ── Results message ──────────────────────────────────────────────
    is_final = msg.get("is_final", False)
    speech_final = msg.get("speech_final", False)

    channel = msg.get("channel", {})
    alternatives = channel.get("alternatives", [])
    if not alternatives:
        return None

    transcript = alternatives[0].get("transcript", "").strip()
    if not transcript:
        return None

    if is_final or speech_final:
        buffer.append(transcript)

    if speech_final and buffer:
        text = " ".join(buffer).strip()
        buffer.clear()
        return text

    return None


# ── WebSocket relay ───────────────────────────────────────────────────────────


async def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def run_stt_ws(websocket, session_id: str, role: str, ingest_fn) -> None:
    """Run the Deepgram STT relay for one browser WebSocket connection.

    *ingest_fn* is ``ingest_utterance`` from ``backend.app`` — passed in
    to avoid a circular import.
    """
    DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
    if not DEEPGRAM_API_KEY:
        await websocket.send_json({"type": "error", "message": "DEEPGRAM_API_KEY missing"})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    DG_URL = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-3&smart_format=true&punctuate=true"
        "&interim_results=true&endpointing=300&utterance_end_ms=1000"
    )

    buffer: list[str] = []

    async def _keepalive(dg):
        while True:
            await asyncio.sleep(8)
            try:
                await dg.send(json.dumps({"type": "KeepAlive"}))
            except Exception:
                break

    async def _recv_client(dg):
        try:
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                data = msg.get("bytes")
                if data is not None:
                    await dg.send(data)
        except Exception:
            pass
        finally:
            try:
                await dg.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                pass

    async def _recv_deepgram():
        nonlocal buffer
        try:
            while True:
                raw = await dg_ws.recv()
                if not isinstance(raw, str):
                    continue
                msg = json.loads(raw)

                # Interim text → browser (skip if final/speech_final — those are handled below)
                if msg.get("type") == "Results" and not msg.get("is_final") and not msg.get("speech_final"):
                    alts = msg.get("channel", {}).get("alternatives", [])
                    if alts:
                        t = alts[0].get("transcript", "").strip()
                        if t:
                            try:
                                await websocket.send_json({"type": "interim", "text": t})
                            except Exception:
                                return

                # Completed utterance?
                text = parse_deepgram_message(msg, buffer)
                if text is not None:
                    utt = {
                        "utterance_id": f"stt_{uuid.uuid4().hex}",
                        "speaker": role,
                        "text": text,
                        "timestamp": await _utc_now(),
                    }
                    try:
                        await ingest_fn(session_id, utt)
                        await websocket.send_json({"type": "final", "text": text})
                    except Exception:
                        return
        except Exception:
            pass

    try:
        async with websockets.connect(
            DG_URL,
            additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
        ) as dg_ws:
            ka = asyncio.create_task(_keepalive(dg_ws))
            await asyncio.gather(
                _recv_client(dg_ws),
                _recv_deepgram(),
                return_exceptions=True,
            )
            ka.cancel()
            try:
                await ka
            except asyncio.CancelledError:
                pass
    except Exception as exc:
        logger.error("Deepgram connection error for session %s: %s", session_id, exc)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
