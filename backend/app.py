"""Tripwire backend — FastAPI app.

Implements every HTTP + WS route from shared/COORDINATOR.md,
the transcript flow, takeover wiring, and the on_family_joined hook
that Manav's voice worker calls when a real provider participant-joined
event arrives.
"""

from __future__ import annotations

import asyncio
import uuid
import logging
import os
import sys
from typing import Annotated, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend import session  # noqa: E402
from backend import assistant_voice, gemini_decision, stt  # noqa: E402

logger = logging.getLogger("tripwire")

VALID_RISKS = {"low", "medium", "high", "review"}
VALID_ACTIONS = {"none", "alert", "takeover"}

Token = Annotated[Optional[str], Header(alias="X-Session-Token")]


# ── Lazy optional-module helpers ────────────────────────────────────────

def _load_intelligence() -> Any | None:
    try:
        mod = sys.modules.get("backend.intelligence")
        if mod is None:
            import backend.intelligence as _m  # noqa: F401
            mod = sys.modules["backend.intelligence"]
        if not hasattr(mod, "analyze_transcript"):
            return None
        return mod
    except ImportError:
        return None


def _load_calls() -> Any | None:
    required = ("create_join_credentials", "start_takeover", "stop_assistant", "end_call")
    mod = sys.modules.get("backend.calls")
    # Test doubles replace backend.calls with a non-package object that implements the contract.
    if (
        mod is not None
        and not hasattr(mod, "__path__")
        and all(hasattr(mod, f) for f in required)
    ):
        return mod
    # Production: prefer calls_bridge (session-token aware) over invite-HMAC coordinator_api.
    try:
        from backend import calls_bridge

        if all(hasattr(calls_bridge, f) for f in required):
            return calls_bridge
    except ImportError:
        pass
    if mod is not None and all(hasattr(mod, f) for f in required):
        return mod
    return _demo_calls_or_none()


def _demo_calls_or_none() -> Any | None:
    # ponytail: DEMO_MODE-only stand-in until Manav's backend/calls lands. No real audio routing;
    # every event carries demo_replay=true so UIs label it. Delete once backend/calls exists.
    return _DemoCalls if os.environ.get("DEMO_MODE", "false").lower() == "true" else None


class _DemoCalls:
    @staticmethod
    async def create_join_credentials(session_id: str, role: str) -> dict:
        if role == "family":
            async def _join() -> None:
                await asyncio.sleep(0.5)
                await on_family_joined(session_id, {"role": "family", "demo": True})
            asyncio.create_task(_join())
        return {"provider": "demo", "role": role, "room_url": None, "token": None, "demo": True}

    @staticmethod
    async def start_takeover(session_id: str, decision: dict) -> dict:
        async def _ready() -> None:
            await asyncio.sleep(1.5)
            await session.mark_wearer_audio_blocked(session_id)
            await session.mark_assistant_ready(session_id)
        asyncio.create_task(_ready())
        return {"accepted": True, "demo": True}

    @staticmethod
    async def stop_assistant(session_id: str) -> None:
        return None

    @staticmethod
    async def end_call(session_id: str) -> None:
        return None


# ── CORS ────────────────────────────────────────────────────────────────

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

app = FastAPI(title="Tripwire", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _alias_access_header(request, call_next):
    """Manav's call components send X-Tripwire-Access; treat it as X-Session-Token."""
    h = request.scope["headers"]
    if not any(k == b"x-session-token" for k, _ in h):
        v = next((v for k, v in h if k == b"x-tripwire-access"), None)
        if v is not None:
            request.scope["headers"] = [*h, (b"x-session-token", v)]
    return await call_next(request)


try:
    from backend.calls.errors import CallError, RolePermissionError, SessionAccessError

    @app.exception_handler(CallError)
    async def _call_error(request, exc):
        from fastapi.responses import JSONResponse
        code = 403 if isinstance(exc, (SessionAccessError, RolePermissionError)) else 409
        return JSONResponse(status_code=code, content={"detail": str(exc), "source": "calls"})
except ImportError:
    pass


# ── Auth helpers ────────────────────────────────────────────────────────

def _role_for(session_id: str, token: str) -> str | None:
    s = session.store._sessions.get(session_id)
    if s is None:
        return None
    return session.store.role_for_token(session_id, token)


def _auth_or_raise(session_id: str, token: str | None, allowed: set[str]) -> str:
    if token is None:
        s = session.store._sessions.get(session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        raise HTTPException(status_code=403, detail="bad token")
    role = _role_for(session_id, token)
    if role is None:
        s = session.store._sessions.get(session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        raise HTTPException(status_code=403, detail="bad token")
    s = session.store._sessions.get(session_id)
    if s is not None and s.state == session.SessionState.ended:
        raise HTTPException(status_code=410, detail="session ended")
    if role != "presenter" and role not in allowed:
        raise HTTPException(status_code=403, detail="forbidden")
    return role


def _session_or_raise(session_id: str) -> session.Session:
    try:
        return session.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")


# ── Decision validation ─────────────────────────────────────────────────

def _validate_decision(decision: dict, utterances: list[dict]) -> str | None:
    risk = decision.get("risk")
    if risk not in VALID_RISKS:
        return f"invalid risk: {risk}"
    action = decision.get("recommended_action")
    if action not in VALID_ACTIONS:
        return f"invalid action: {action}"
    text_by_id = {u["utterance_id"]: u.get("text", "") for u in utterances}
    for ev in decision.get("evidence", []):
        ref_id = ev.get("utterance_id", "")
        quote = ev.get("quote", "")
        source_text = text_by_id.get(ref_id, "")
        if quote not in source_text:
            return f"evidence quote not in utterance {ref_id}"
    return None


# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"ok": True}


_LATEST_SESSION: str | None = None


@app.get("/api/demo/latest")
def demo_latest(request: Request):
    """Lets the Vexo band bridge follow the newest session without reconnecting the band.
    ponytail: local demo convenience; only answers requests from this machine."""
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="local only")
    s = session.store._sessions.get(_LATEST_SESSION or "")
    if s is None or s.state == session.SessionState.ended:
        return {"session_id": None}
    return {"session_id": s.session_id, "mode": s.mode, "token": s.tokens["presenter"]}


@app.post("/api/sessions")
def create_session(body: dict):
    s = session.store.create(body["mode"], body.get("protection_enabled", True))
    global _LATEST_SESSION
    _LATEST_SESSION = s.session_id
    return {
        "session_id": s.session_id,
        "state": s.state.value,
        "tokens": s.tokens,
    }


@app.get("/api/sessions/{session_id}")
def get_session_route(session_id: str, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "family", "presenter"})
    s = _session_or_raise(session_id)
    return s.snapshot()


@app.post("/api/sessions/{session_id}/join")
async def join_session(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "family", "presenter"})
    calls = _load_calls()
    if calls is None:
        raise HTTPException(status_code=501, detail="calls module unavailable")
    return await calls.create_join_credentials(session_id, body["role"])


@app.post("/api/sessions/{session_id}/transcripts")
async def post_transcript(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "family", "presenter"})
    return await ingest_utterance(session_id, {k: body[k] for k in ("utterance_id", "speaker", "text", "timestamp")})


MAX_ASSISTANT_REPLIES = int(os.environ.get("MAX_ASSISTANT_REPLIES", "50"))  # keep stalling until family joins


async def ingest_utterance(session_id: str, body: dict) -> dict:
    """Store + publish one finalized utterance, run risk analysis, trigger takeover / AI reply.
    Shared by POST /transcripts and the live STT relay."""
    s = _session_or_raise(session_id)
    if s.state == session.SessionState.ended:
        raise HTTPException(status_code=410, detail="session ended")
    if body["speaker"] != "assistant" and _is_assistant_echo(s, body["text"]):
        return {"accepted": True, "duplicate": True, "echo": True}
    if s.state == session.SessionState.family_joined and body["speaker"] == "caller":
        body = {**body, "speaker": "family"}   # demo: one laptop mic; after the join it's the family member talking

    duplicate = not session.store.add_utterance(session_id, {
        "utterance_id": body["utterance_id"],
        "speaker": body["speaker"],
        "text": body["text"],
        "timestamp": body["timestamp"],
    })
    if duplicate:
        return {"accepted": True, "duplicate": True}

    utterance = {
        "utterance_id": body["utterance_id"],
        "speaker": body["speaker"],
        "text": body["text"],
        "timestamp": body["timestamp"],
    }
    await session.publish_event(session_id, "transcript.final", utterance)

    if s.state == session.SessionState.assistant_active and body["speaker"] == "caller":
        n = getattr(s, "assistant_replies", 0)
        if n < MAX_ASSISTANT_REPLIES:
            s.assistant_replies = n + 1
            asyncio.create_task(_assistant_reply(session_id, body["text"]))

    if not s.protection_enabled or s.state != session.SessionState.monitoring:
        return {"accepted": True, "duplicate": False}

    mode = s.mode
    if mode == "call" and body["speaker"] not in {"caller", "wearer", "ambient"}:  # ambient = Vexo band room mic
        return {"accepted": True, "duplicate": False}
    if mode == "ambient" and body["speaker"] != "ambient":
        return {"accepted": True, "duplicate": False}

    utterances_for_analysis = [dict(u) for u in s.transcript]
    intel = _load_intelligence()
    if intel is None:
        return {"accepted": True, "duplicate": False}

    try:
        # Rules/evidence (Pratham's analyzer) and Gemini Decision 1 run in parallel.
        decision, gd = await asyncio.gather(
            intel.analyze_transcript(session_id, utterances_for_analysis),
            gemini_decision.decide([u for u in utterances_for_analysis if u.get("speaker") != "assistant"]),
        )
    except Exception as exc:
        await session.publish_event(session_id, "error", {"source": "intelligence", "message": str(exc)})
        return {"accepted": True, "duplicate": False}

    err = _validate_decision(decision, utterances_for_analysis)
    if err:
        await session.publish_event(session_id, "error", {"source": "intelligence", "message": err})
        return {"accepted": True, "duplicate": False}

    if gd:
        decision["gemini_decision"] = gd
        # Decision 1 is >=90% sure it's a scam and rules already found evidence: escalate review -> takeover.
        if decision.get("risk") == "review" and decision.get("evidence") and gd["action"] == "takeover" and gd["p_scam"] >= 0.9:
            decision["risk"], decision["recommended_action"] = "high", "takeover"
            decision["reasons"] = list(decision.get("reasons", [])) + ["gemini_decision_high"]

    session.record_decision(session_id, decision)
    await session.publish_event(session_id, "risk.updated", dict(decision))  # full risk_result

    risk = decision.get("risk", "")
    action = decision.get("recommended_action", "")
    did = decision.get("decision_id", "")

    if mode == "call" and risk == "high" and action in ("takeover", "alert"):  # band-heard (ambient) high risk on a call also takes over
        taken = session.begin_takeover(session_id, decision)
        if taken:
            calls = _load_calls()
            if calls is None:
                await session.fail_takeover(session_id, "calls module unavailable")
            else:
                asyncio.create_task(_takeover_task(session_id, decision))

    elif (risk in ("review", "high") and action == "alert") or (mode == "ambient" and risk == "high"):
        # Ambient (in-person, heard by the Vexo band): nothing to take over, so alert family once.
        sess = session.get_session(session_id)
        if did not in sess.alerted_decision_ids and (mode == "ambient" or not sess.alert):
            sess.alerted_decision_ids.add(did)
            alert = {"decision_id": did, "summary": decision.get("summary", ""),
                     "reasons": decision.get("reasons", []), "evidence": decision.get("evidence", [])}
            sess.alert = alert
            await session.publish_event(session_id, "family.alert", alert)

    return {"accepted": True, "duplicate": False}


async def _takeover_task(session_id: str, decision: dict) -> None:
    calls = _load_calls()
    if calls is None:
        await session.fail_takeover(session_id, "calls module unavailable")
        return
    try:
        await calls.start_takeover(session_id, decision)
    except Exception as exc:
        await session.fail_takeover(session_id, str(exc))


@app.post("/api/sessions/{session_id}/takeover")
async def post_takeover(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "presenter"})
    s = _session_or_raise(session_id)
    if s.state == session.SessionState.ended:
        raise HTTPException(status_code=410, detail="session ended")

    latest_id = s.latest_decision.get("decision_id") if s.latest_decision else None
    if body["decision_id"] != latest_id:
        raise HTTPException(status_code=409, detail="decision_id mismatch")
    if s.state != session.SessionState.monitoring:
        raise HTTPException(status_code=409, detail="state not monitoring")

    taken = session.begin_takeover(session_id, s.latest_decision)
    if not taken:
        raise HTTPException(status_code=409, detail="takeover already started")

    calls = _load_calls()
    if calls is None:
        await session.fail_takeover(session_id, "calls module unavailable")
    else:
        asyncio.create_task(_takeover_task(session_id, s.latest_decision))
    return {"accepted": True}


@app.post("/api/sessions/{session_id}/signals")
async def post_signal(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    s = _session_or_raise(session_id)
    if s.state == session.SessionState.ended:
        raise HTTPException(status_code=410, detail="session ended")

    sig = body["signal"]
    if sig == "wearer_audio_blocked":
        _auth_or_raise(session_id, x_session_token, {"wearer", "presenter"})
        await session.mark_wearer_audio_blocked(session_id)
    elif sig == "wearer_reconnect":
        _auth_or_raise(session_id, x_session_token, {"family", "presenter"})
        if s.state != session.SessionState.family_joined:
            raise HTTPException(status_code=409, detail="state not family_joined")
        await session.wearer_reconnect(session_id)
    else:
        raise HTTPException(status_code=400, detail=f"unknown signal: {sig}")
    return {"accepted": True}


# ── Routes Manav's call components call (backend/calls via calls_bridge) ──

def _bridge_or_501():
    calls = _load_calls()
    if calls is None or not hasattr(calls, "confirm_routing"):
        raise HTTPException(status_code=501, detail="calls module unavailable")
    return calls


@app.post("/api/sessions/{session_id}/routing-confirmation")
async def routing_confirmation(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"wearer", "presenter"})
    return await _bridge_or_501().confirm_routing(session_id, body)


@app.post("/api/sessions/{session_id}/provider-join")
async def provider_join(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "family", "presenter"})
    return await _bridge_or_501().confirm_provider_join(session_id, body, x_session_token)


@app.post("/api/sessions/{session_id}/family-joined")
async def family_joined(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"family", "presenter"})
    return await _bridge_or_501().confirm_family_joined(session_id, body, x_session_token)


@app.post("/api/sessions/{session_id}/reconnect-wearer")
async def reconnect_wearer(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"family", "wearer", "presenter"})
    return await _bridge_or_501().reconnect_wearer(session_id, x_session_token)


# ── Vexo band events (SOS double-tap, free-fall) ───────────────────────

BAND_ALERTS = {
    "sos": ("sos", "Your family member pressed their Vexo band for help."),
    "fall": ("possible_fall", "The Vexo band detected a possible fall."),
}


@app.post("/api/sessions/{session_id}/band-event")
async def band_event(session_id: str, body: dict, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"presenter", "wearer"})
    kind = body.get("kind")
    if kind not in BAND_ALERTS:
        raise HTTPException(status_code=422, detail="kind must be sos or fall")
    reason, summary = BAND_ALERTS[kind]
    alert = {"decision_id": f"band_{kind}_{uuid.uuid4().hex[:8]}", "summary": summary, "reasons": [reason], "evidence": [], "source": "vexo_band"}
    session.get_session(session_id).alert = alert
    await session.publish_event(session_id, "family.alert", alert)
    return {"accepted": True}


# ── Assistant voice + live transcription ────────────────────────────────

PERSONA = (
    "You are Linda, the elderly man's neighbor who happened to pick up his phone because he is in the other room. "
    "Your only goal is to keep the caller talking, calmly and naturally, until his daughter joins the call. "
    "Sound like a real, warm, slightly slow person on the phone: short spoken sentences, small fillers like 'oh' or 'hmm'. "
    "Ask simple questions (which grandson is this, what happened, where are you, what number can he call you back on), "
    "mishear a little, say he's coming or looking for his glasses. "
    "Never say you are an AI or an assistant, never mention scams, verification, family members joining, or the police. "
    "Never agree to buy gift cards, send money, or share any personal or financial information. "
    "Reply with one or two short sentences only, no stage directions."
)
FALLBACK_STALLS = [
    "Oh, hold on dear, he's just finding his glasses. Which grandson did you say this is?",
    "Sorry, the line's a bit crackly. What happened, are you alright?",
    "Hmm, where are you calling from, sweetheart?",
    "He's coming, he's coming. What's a good number for him to call you back on?",
]
_reply_busy: set[str] = set()


async def _stall_reply(session_id: str) -> str:
    """Human-sounding stalling reply from Gemini (fast model), with canned fallbacks."""
    s = session.get_session(session_id)
    convo = "\n".join(
        f"{'Linda' if u['speaker'] == 'assistant' else 'Caller'}: {u['text']}"
        for u in s.transcript[-8:] if u["speaker"] in ("caller", "assistant")
    )
    key, model = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    n = sum(1 for u in s.transcript if u["speaker"] == "assistant")
    if key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=4) as c:
                r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 headers={"x-goog-api-key": key},
                                 json={"systemInstruction": {"parts": [{"text": PERSONA}]},
                                       "contents": [{"role": "user", "parts": [{"text": convo + "\nLinda:"}]}],
                                       "generationConfig": {"maxOutputTokens": 60, "temperature": 0.8}})
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"')
            low = text.lower()
            if text and not any(w in low for w in ("ai ", "assistant", "scam", "verif", "police", "gift card", "send money")):
                return text
        except Exception:
            logger.exception("stall reply failed")
    return FALLBACK_STALLS[n % len(FALLBACK_STALLS)]


async def _assistant_reply(session_id: str, caller_text: str) -> None:
    if session_id in _reply_busy:          # one reply at a time; never talk over itself
        return
    _reply_busy.add(session_id)
    try:
        text = await _stall_reply(session_id)
        if session.get_session(session_id).state == session.SessionState.assistant_active:
            await assistant_voice.speak(session_id, text)
    finally:
        _reply_busy.discard(session_id)


OPENING_LINE = os.environ.get("ASSISTANT_OPENING_LINE",
    "Hi, sorry, he just stepped away for a second. Who am I speaking with, and what's this regarding?")


async def _on_event(envelope: dict) -> None:
    if envelope["type"] == "takeover.active":
        await assistant_voice.speak(envelope["session_id"], OPENING_LINE)


def _is_assistant_echo(s, text: str) -> bool:
    """The laptop mic can hear the AI voice from the speakers; drop transcripts that repeat it."""
    words = set(w.strip(".,?!'").lower() for w in text.split())
    if not words:
        return True
    for u in s.transcript[-4:]:
        if u.get("speaker") == "assistant":
            aw = set(w.strip(".,?!'").lower() for w in u["text"].split())
            if len(words & aw) / len(words) >= 0.6:
                return True
    return False


session.listeners[:] = [f for f in session.listeners if getattr(f, "__name__", "") != "_on_event"] + [_on_event]  # idempotent on reload


@app.get("/api/sessions/{session_id}/assistant-audio/{utterance_id}")
def assistant_audio(session_id: str, utterance_id: str, token: Optional[str] = None):
    _auth_or_raise(session_id, token, {"caller", "wearer", "family", "presenter"})
    audio = assistant_voice.get_cached_audio(utterance_id)
    if audio is None:
        raise HTTPException(status_code=404, detail="audio not found")
    return Response(content=audio, media_type="audio/mpeg")


@app.websocket("/ws/sessions/{session_id}/stt")
async def stt_ws(websocket: WebSocket, session_id: str, token: str = "", role: str = ""):
    tok_role = _role_for(session_id, token) if token else None
    s = session.store._sessions.get(session_id)
    speaker = role if tok_role == "presenter" else tok_role
    if s is None or tok_role is None or s.state == session.SessionState.ended or speaker not in {"caller", "wearer", "family", "ambient"} or (role and role != speaker):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    await stt.run_stt_ws(websocket, session_id, speaker, ingest_utterance)


@app.post("/api/sessions/{session_id}/end")
async def end_session_route(session_id: str, x_session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    _auth_or_raise(session_id, x_session_token, {"caller", "wearer", "family", "presenter"})
    s = _session_or_raise(session_id)
    calls = _load_calls()
    if calls is not None:
        try:
            await calls.end_call(session_id)
        except Exception as exc:
            logger.error("end_call error for %s: %s", session_id, exc)
    await session.end_session(session_id)
    return {"accepted": True}


# ── WebSocket ───────────────────────────────────────────────────────────

@app.websocket("/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    token = websocket.query_params.get("token", "")
    role = _role_for(session_id, token)
    if role is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        s = session.get_session(session_id)
    except KeyError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if s.state == session.SessionState.ended:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    session.store.subscribe(session_id, q)

    # Flush pre-existing events
    try:
        while True:
            item = await asyncio.wait_for(q.get(), timeout=0.05)
            if item is None:
                break
            await websocket.send_json(item)
    except asyncio.TimeoutError:
        pass

    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    cs = session.get_session(session_id)
                    if cs.state == session.SessionState.ended:
                        break
                except KeyError:
                    break
                continue
            if item is None:
                break
            await websocket.send_json(item)
    except WebSocketDisconnect:
        pass
    finally:
        session.store.unsubscribe(session_id, q)


# ── on_family_joined hook ───────────────────────────────────────────────


async def on_family_joined(session_id: str, participant: dict) -> None:
    """Called by Manav's voice worker on real provider participant-joined events.

    1. Marks the session as family_joined via session.mark_family_joined.
    2. If the family member is newly joined (transition succeeded), stops
       the AI assistant via calls.stop_assistant.

    This is the bridge between the provider event and the Tripwire state
    machine — Manav wires his callback here.
    """
    try:
        session.get_session(session_id)
    except KeyError:
        return
    newly = await session.mark_family_joined(session_id, participant)
    if not newly:
        return
    calls = _load_calls()
    if calls is not None:
        try:
            await calls.stop_assistant(session_id)
        except Exception as exc:
            logger.error("stop_assistant error for %s: %s", session_id, exc)
