"""Vexo band bridge: the band's always-on mic -> Deepgram -> Tripwire risk engine; risk -> band LED.

    python -m backend.band_bridge --band 17 --follow       # stay connected; follow every new session (demo)
    python -m backend.band_bridge --band 17                # new ambient session, prints role links
    python -m backend.band_bridge --band 17 --session ses_x --token <presenter token>
    python -m backend.band_bridge --sim --follow           # pretend band (no Bluetooth)

Double-tap the band first (its light blinks blue). The band connects ONCE and stays connected
(the Vexo library auto-reconnects if the link drops). While the mic is on the band shows solid
blue and refuses LED commands, so on a high-risk decision the bridge turns the mic off and
blinks red. Between sessions the band breathes green (standby).
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


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


class Bridge:
    def __init__(self, band: Band, http: httpx.AsyncClient, backend: str, use_mic: bool, sos: bool):
        self.band, self.http, self.backend, self.use_mic = band, http, backend, use_mic
        self.mic_on = False
        self.audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        self.sid: str | None = None
        self.token: str | None = None
        # Empty packets would tell Deepgram "end of stream", so drop them.
        self.packets = 0
        band.on("audio", self._on_audio)
        band.on("free-fall", lambda e: asyncio.ensure_future(self.band_alert("fall")))
        if sos:
            band.on("double-tap", lambda e: asyncio.ensure_future(self.band_alert("sos")))
        band.on("reconnecting", lambda e: log("band link dropped: reconnecting (no tap needed)"))
        band.on("reconnected", lambda e: log("band link restored"))

    def _on_audio(self, m) -> None:
        self.packets += 1
        if m.opus and self.mic_on and not self.audio_q.full():
            self.audio_q.put_nowait(m.opus)

    async def heartbeat(self) -> None:
        silent = 0
        while True:
            await asyncio.sleep(15)
            state = "link up" if self.band.connected else "LINK DOWN (reconnecting)"
            log(f"heartbeat: {state}, mic {'on' if self.mic_on else 'off'}, {self.packets} audio packets in 15s")
            silent = silent + 1 if (self.mic_on and self.packets == 0) else 0
            self.packets = 0
            if silent >= 2:   # mic on but nothing for 30 s: the band reset or went away. Restart and reconnect.
                log("watchdog: band silent for 30s, reconnecting")
                os._exit(3)   # supervisor (scripts_run_band.sh) restarts the bridge

    async def set_mic(self, on: bool) -> None:
        if on != self.mic_on:
            await self.band.configure(audio=on)
            self.mic_on = on

    async def standby(self) -> None:
        await self.set_mic(False)
        await self.band.set_led(GREEN, pattern="breathe", period=2000)

    async def band_alert(self, kind: str) -> None:
        if self.sid:
            await self.http.post(f"/api/sessions/{self.sid}/band-event", headers={"X-Session-Token": self.token}, json={"kind": kind})
            log(f"BAND {kind.upper()}: family alerted")

    async def post(self, text: str) -> None:
        await self.http.post(f"/api/sessions/{self.sid}/transcripts", headers={"X-Session-Token": self.token},
                             json={"utterance_id": f"band_{uuid.uuid4().hex}", "speaker": "ambient", "text": text, "timestamp": now()})

    async def deepgram(self) -> None:
        while True:  # reconnect if Deepgram drops (idle timeout, network blip)
            try:
                async with websockets.connect(DG_URL, additional_headers={"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}"}) as dg:
                    async def send():
                        while True:
                            try:
                                await dg.send(await asyncio.wait_for(self.audio_q.get(), timeout=8))
                            except asyncio.TimeoutError:
                                await dg.send(json.dumps({"type": "KeepAlive"}))
                    sender = asyncio.create_task(send())
                    buf: list[str] = []
                    try:
                        async for raw in dg:
                            if isinstance(raw, str) and (text := parse_deepgram_message(json.loads(raw), buf)):
                                log(f"heard: {text}")
                                await self.post(text)
                    finally:
                        sender.cancel()
            except (websockets.ConnectionClosed, OSError) as exc:
                log(f"deepgram reconnecting ({exc.__class__.__name__})")
                await asyncio.sleep(1)

    async def events(self) -> None:
        ws_url = self.backend.replace("http", "ws", 1) + f"/ws/sessions/{self.sid}?token={self.token}"
        async with websockets.connect(ws_url) as ws:
            async for raw in ws:
                t = json.loads(raw).get("type")
                if t in ("takeover.started", "family.alert"):
                    await self.set_mic(False)                       # LED is locked while the mic is on
                    await self.band.set_led(RED, pattern="blink", period=400)
                    log("RISK: band blinking red")
                elif t == "family.joined":
                    await self.band.set_led(BLUE_FAMILY, pattern="breathe", period=2000)
                    log("family joined: band breathing blue")
                elif t == "session.ended":
                    return

    async def run_session(self, sid: str, token: str) -> None:
        self.sid, self.token = sid, token
        while not self.audio_q.empty():
            self.audio_q.get_nowait()
        if self.use_mic:
            await self.set_mic(True)                                # solid blue = listening
            log(f"session {sid}: band mic on (solid blue). Listening...")
        else:
            log(f"session {sid}: band ready (no mic). Listening...")
        dg = asyncio.create_task(self.deepgram()) if self.use_mic else None

        async def newer_session() -> None:   # a newer session started: leave this one at once
            while True:
                await asyncio.sleep(1)
                try:
                    latest = (await self.http.get("/api/demo/latest")).json().get("session_id")
                except (httpx.HTTPError, ValueError):
                    continue
                if latest and latest != sid:
                    return
        try:
            done, pending = await asyncio.wait({asyncio.create_task(self.events()), asyncio.create_task(newer_session())},
                                               return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                if t.exception() and not isinstance(t.exception(), (websockets.ConnectionClosed, OSError)):
                    raise t.exception()
        finally:
            if dg:
                dg.cancel()
            self.sid = None
            await self.standby()
            log(f"session {sid} ended: band on standby (breathing green)")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", type=int, default=17)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--backend", default=os.environ.get("BACKEND_URL", "http://localhost:8000"))
    ap.add_argument("--follow", action="store_true", help="stay connected and attach to every new session")
    ap.add_argument("--session")
    ap.add_argument("--token", help="presenter token for --session")
    ap.add_argument("--mode", default="ambient", choices=["ambient", "call"])
    ap.add_argument("--no-mic", action="store_true", help="LED + fall alerts only (audio comes from elsewhere)")
    ap.add_argument("--sos", action="store_true", help="also let a double-tap send an SOS (off: detection is automatic)")
    a = ap.parse_args()

    http = httpx.AsyncClient(base_url=a.backend, timeout=20)
    band = None
    for attempt in range(1, 10_000):                                 # keep trying until the band is discoverable
        try:
            band = await Band.connect(a.band, "sim" if a.sim else "ble", auto_reconnect=True, reconnect_seconds=120)
            break
        except Exception:
            if attempt == 1:
                log(f"waiting for Vexo-HACK-{a.band}: double-tap the band (blue blink)")
            await asyncio.sleep(2)
    log(f"connected to {band.name}")
    bridge = Bridge(band, http, a.backend, use_mic=not a.no_mic, sos=a.sos)
    await band.configure(events=True)
    await bridge.standby()
    asyncio.create_task(bridge.heartbeat())

    try:
        if a.follow:
            seen: set[str] = set()
            log("follow mode: waiting for a session (start one at http://localhost:3000)")
            while True:
                try:
                    latest = (await http.get("/api/demo/latest")).json()
                except httpx.HTTPError:
                    latest = {}
                sid = latest.get("session_id")
                if sid and sid not in seen:
                    seen.add(sid)
                    await bridge.run_session(sid, latest["token"])
                await asyncio.sleep(1)
        else:
            if a.session:
                sid, token = a.session, a.token
            else:
                r = (await http.post("/api/sessions", json={"mode": a.mode, "protection_enabled": True})).json()
                sid, token = r["session_id"], r["tokens"]["presenter"]
                fe = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
                for role, tok in r["tokens"].items():
                    print(f"  {role:9s} {fe}/{role}?session={sid}&token={tok}", flush=True)
            await bridge.run_session(sid, token)
    finally:
        try:
            await bridge.set_mic(False)
            await band.led_off()
        finally:
            await band.disconnect()
            await http.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
