"""Vexo band bridge: the band's always-on mic -> Deepgram -> Tripwire risk engine; risk -> band LED.

    python -m backend.band_bridge --band 17                 # new ambient session, prints role links
    python -m backend.band_bridge --band 17 --session ses_x --token <presenter token>   # join a session
    python -m backend.band_bridge --sim                     # pretend band (no Bluetooth)

Double-tap the band first (its light blinks blue). While the mic is on the band shows solid blue
and refuses LED commands, so on a high-risk decision the bridge turns the mic off and blinks red.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
from vexo_open import Band  # noqa: E402  (vendored Vexo Open kit, MIT)

from backend.stt import parse_deepgram_message  # noqa: E402

load_dotenv()
DG_URL = ("wss://api.deepgram.com/v1/listen?model=nova-3&language=en&encoding=opus&sample_rate=16000"
          "&channels=1&smart_format=true&punctuate=true&interim_results=true&endpointing=300&utterance_end_ms=1000")
RED, BLUE_FAMILY, GREEN = "#ff2448", "#3b4fd8", "#1f9d7a"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", type=int, default=17)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--backend", default=os.environ.get("BACKEND_URL", "http://localhost:8000"))
    ap.add_argument("--session")
    ap.add_argument("--token", help="presenter token for --session")
    ap.add_argument("--mode", default="ambient", choices=["ambient", "call"])
    ap.add_argument("--no-mic", action="store_true", help="LED + fall alerts only (audio comes from elsewhere)")
    ap.add_argument("--sos", action="store_true", help="also let a double-tap send an SOS (off: detection is automatic)")
    a = ap.parse_args()

    http = httpx.AsyncClient(base_url=a.backend, timeout=20)
    if a.session:
        sid, token = a.session, a.token
    else:
        r = (await http.post("/api/sessions", json={"mode": a.mode, "protection_enabled": True})).json()
        sid, token = r["session_id"], r["tokens"]["presenter"]
        fe = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
        for role, tok in r["tokens"].items():
            print(f"  {role:9s} {fe}/{role}?session={sid}&token={tok}")
    print(f"session {sid}")

    band = await Band.connect(a.band, "sim" if a.sim else "ble")
    print(f"connected to {band.name}")
    await band.set_led(GREEN, pattern="breathe", period=1500)   # armed
    await asyncio.sleep(1.5)

    async def band_alert(kind: str) -> None:
        await http.post(f"/api/sessions/{sid}/band-event", headers={"X-Session-Token": token}, json={"kind": kind})
        print(f"BAND {kind.upper()}: family alerted")

    if a.sos:
        band.on("double-tap", lambda e: asyncio.ensure_future(band_alert("sos")))
    band.on("free-fall", lambda e: asyncio.ensure_future(band_alert("fall")))
    await band.configure(events=True)

    audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
    # Empty packets would tell Deepgram "end of stream", so drop them.
    band.on("audio", lambda m: audio_q.put_nowait(m.opus) if m.opus and not audio_q.full() else None)
    mic_on = not a.no_mic
    if mic_on:
        await band.configure(audio=True)                        # solid blue = listening
        print("band mic on (solid blue). Listening...")
    else:
        print("band ready (no mic): automatic LED alerts + fall detection. Listening...")

    async def post(text: str) -> None:
        await http.post(f"/api/sessions/{sid}/transcripts", headers={"X-Session-Token": token},
                        json={"utterance_id": f"band_{uuid.uuid4().hex}", "speaker": "ambient", "text": text, "timestamp": now()})

    async def deepgram() -> None:
        while True:  # reconnect if Deepgram drops (idle timeout, network blip)
            try:
                await _deepgram_once()
            except (websockets.ConnectionClosed, OSError) as exc:
                print(f"deepgram reconnecting ({exc.__class__.__name__})")
                await asyncio.sleep(1)

    async def _deepgram_once() -> None:
        async with websockets.connect(DG_URL, additional_headers={"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}"}) as dg:
            async def send():
                while True:
                    try:
                        pkt = await asyncio.wait_for(audio_q.get(), timeout=8)
                        await dg.send(pkt)
                    except asyncio.TimeoutError:
                        await dg.send(json.dumps({"type": "KeepAlive"}))
            sender = asyncio.create_task(send())
            buf: list[str] = []
            try:
                async for raw in dg:
                    if isinstance(raw, str) and (text := parse_deepgram_message(json.loads(raw), buf)):
                        print(f"heard: {text}")
                        await post(text)
            finally:
                sender.cancel()

    async def events() -> None:
        nonlocal mic_on
        ws_url = a.backend.replace("http", "ws", 1) + f"/ws/sessions/{sid}?token={token}"
        async with websockets.connect(ws_url) as ws:
            async for raw in ws:
                t = json.loads(raw).get("type")
                if t in ("takeover.started", "family.alert"):
                    if mic_on:
                        mic_on = False
                        await band.configure(audio=False)           # LED is locked while the mic is on
                    await band.set_led(RED, pattern="blink", period=400)
                    print("RISK: band blinking red")
                elif t == "family.joined":
                    await band.set_led(BLUE_FAMILY, pattern="breathe", period=2000)
                    print("family joined: band breathing blue")
                elif t == "session.ended":
                    return

    try:
        dg_task = asyncio.create_task(deepgram() if mic_on else asyncio.sleep(0))
        try:
            await events()      # returns on session.ended
        except websockets.ConnectionClosed:
            print("session closed")
        dg_task.cancel()
    finally:
        try:
            if mic_on:
                await band.configure(audio=False)
            await band.led_off()
        finally:
            await band.disconnect()
            await http.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
