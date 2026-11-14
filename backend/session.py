from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class IllegalTransition(Exception):
    """Raised when a state transition is not allowed."""


class SessionGone(Exception):
    """Raised when an operation is attempted on an ended session."""


class SessionState(StrEnum):
    monitoring = "monitoring"
    protecting = "protecting"
    assistant_active = "assistant_active"
    family_joined = "family_joined"
    ended = "ended"


LEGAL_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.monitoring: {SessionState.protecting, SessionState.ended},
    SessionState.protecting: {SessionState.assistant_active, SessionState.ended},
    SessionState.assistant_active: {SessionState.family_joined, SessionState.ended},
    SessionState.family_joined: {SessionState.ended},
}


@dataclass
class Session:
    session_id: str
    mode: str
    protection_enabled: bool
    state: SessionState
    wearer_connected: bool
    tokens: dict[str, str] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    utterance_ids: set[str] = field(default_factory=set)
    latest_decision: dict[str, Any] | None = None
    alerted_decision_ids: set[str] = field(default_factory=set)
    alert: dict[str, Any] | None = None
    last_sequence: int = 0
    takeover: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "idle",
            "wearer_audio_blocked": False,
            "assistant_ready": False,
        }
    )
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    timeout_task: asyncio.Task | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "protection_enabled": self.protection_enabled,
            "state": self.state,
            "wearer_connected": self.wearer_connected,
            "transcript": list(self.transcript),
            "latest_decision": self.latest_decision,
            "alert": self.alert,
            "last_sequence": self.last_sequence,
            "takeover": dict(self.takeover),
        }


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    env: dict[str, Any] = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "session_id": session_id,
        "timestamp": _utcnow(),
        "type": event_type,
        "payload": dict(payload),
    }
    if os.environ.get("DEMO_MODE") == "true":
        env["payload"]["demo_replay"] = True
    return env


class SessionStore:

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, mode: str, protection_enabled: bool) -> Session:
        session_id = f"ses_{secrets.token_hex(6)}"
        roles = ("caller", "wearer", "family", "presenter")
        tokens = {role: secrets.token_urlsafe(16) for role in roles}
        session = Session(
            session_id=session_id,
            mode=mode,
            protection_enabled=protection_enabled,
            state=SessionState.monitoring,
            wearer_connected=True,
            tokens=tokens,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise KeyError(session_id)

    def role_for_token(self, session_id: str, token: str) -> str | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        for role, tok in session.tokens.items():
            if secrets.compare_digest(tok, token):
                return role
        return None

    def add_utterance(self, session_id: str, utt: dict[str, Any]) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        uid = utt.get("utterance_id", "")
        if uid in session.utterance_ids:
            return False
        session.utterance_ids.add(uid)
        session.transcript.append(dict(utt))
        return True

    def transition(self, session_id: str, new_state: SessionState) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.state == SessionState.ended:
            raise IllegalTransition(f"session {session_id} is ended")
        allowed = LEGAL_TRANSITIONS.get(session.state, set())
        if new_state not in allowed:
            raise IllegalTransition(
                f"{session.state.value} -> {new_state.value}"
            )
        session.state = new_state

    def subscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        session.subscribers.append(queue)

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        try:
            session.subscribers.remove(queue)
        except ValueError:
            pass

    async def publish(self, session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.state == SessionState.ended:
            raise SessionGone(session_id)
        session.last_sequence += 1
        envelope = _envelope(session_id, event_type, payload)
        envelope["sequence"] = session.last_sequence
        dead: list[asyncio.Queue] = []
        for q in session.subscribers:
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                session.subscribers.remove(q)
            except ValueError:
                pass
        return envelope

    async def end(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        session.state = SessionState.ended
        session.wearer_connected = False
        if session.timeout_task and not session.timeout_task.done():
            session.timeout_task.cancel()
            try:
                await session.timeout_task
            except asyncio.CancelledError:
                pass
            session.timeout_task = None
        for q in list(session.subscribers):
            session.subscribers.remove(q)
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass


store = SessionStore()

# Module-level hook functions


async def publish_event(session_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await store.publish(session_id, event_type, payload)


def begin_takeover(session_id: str, decision: dict[str, Any]) -> bool:
    session = store._sessions.get(session_id)
    if session is None:
        raise KeyError(session_id)

    if session.state != SessionState.monitoring:
        return False

    decision_id = decision.get("decision_id", "")
    if decision_id in session.alerted_decision_ids:
        return False

    store.transition(session_id, SessionState.protecting)
    session.wearer_connected = False
    session.takeover["status"] = "starting"
    session.alert = {
        "decision_id": decision_id,
        "summary": decision.get("summary", ""),
        "reasons": decision.get("reasons", []),
        "evidence": decision.get("evidence", []),
    }
    session.alerted_decision_ids.add(decision_id)

    async def _publish_started() -> None:
        try:
            await store.publish(
                session_id,
                "takeover.started",
                {"decision_id": decision_id},
            )
            await store.publish(
                session_id,
                "family.alert",
                {
                    "decision_id": decision_id,
                    "summary": decision.get("summary", ""),
                    "reasons": decision.get("reasons", []),
                    "evidence": decision.get("evidence", []),
                },
            )
        except (KeyError, SessionGone):
            pass

    async def _schedule_timeout() -> None:
        timeout_s = int(os.environ.get("TAKEOVER_TIMEOUT_S", "15"))
        try:
            await asyncio.sleep(timeout_s)
            s = store._sessions.get(session_id)
            if s is not None and s.state == SessionState.protecting and s.takeover["status"] == "starting":
                s.takeover["status"] = "failed"
                try:
                    await store.publish(session_id, "takeover.failed", {"reason": "timeout"})
                except (KeyError, SessionGone):
                    pass
        except asyncio.CancelledError:
            pass

    async def _run() -> None:
        await _publish_started()
        session.timeout_task = asyncio.create_task(_schedule_timeout())

    asyncio.create_task(_run())
    return True


async def mark_assistant_ready(session_id: str) -> None:
    session = store._sessions.get(session_id)
    if session is None or session.state != SessionState.protecting:
        return
    if session.takeover["status"] == "failed":
        return
    session.takeover["assistant_ready"] = True
    if session.takeover["wearer_audio_blocked"]:
        session.takeover["status"] = "active"
        try:
            store.transition(session_id, SessionState.assistant_active)
        except IllegalTransition:
            pass
        else:
            try:
                await store.publish(session_id, "takeover.active", {})
            except (KeyError, SessionGone):
                pass


async def mark_wearer_audio_blocked(session_id: str) -> None:
    session = store._sessions.get(session_id)
    if session is None or session.state != SessionState.protecting:
        return
    if session.takeover["status"] == "failed":
        return
    session.takeover["wearer_audio_blocked"] = True
    if session.takeover["assistant_ready"]:
        session.takeover["status"] = "active"
        try:
            store.transition(session_id, SessionState.assistant_active)
        except IllegalTransition:
            pass
        else:
            try:
                await store.publish(session_id, "takeover.active", {})
            except (KeyError, SessionGone):
                pass


async def mark_family_joined(session_id: str, participant: dict[str, Any]) -> bool:
    session = store._sessions.get(session_id)
    if session is None:
        raise KeyError(session_id)
    if session.state not in (SessionState.protecting, SessionState.assistant_active):
        return False
    if session.timeout_task and not session.timeout_task.done():
        session.timeout_task.cancel()
        try:
            await session.timeout_task
        except asyncio.CancelledError:
            pass
        session.timeout_task = None
    try:
        store.transition(session_id, SessionState.family_joined)
    except IllegalTransition:
        return False
    try:
        await store.publish(session_id, "family.joined", {"participant": dict(participant)})
    except (KeyError, SessionGone):
        pass
    return True


async def fail_takeover(session_id: str, reason: str) -> None:
    session = store._sessions.get(session_id)
    if session is None:
        return
    if session.state != SessionState.protecting:
        return
    if session.takeover["status"] != "starting":
        return
    session.takeover["status"] = "failed"
    if session.timeout_task and not session.timeout_task.done():
        session.timeout_task.cancel()
        try:
            await session.timeout_task
        except asyncio.CancelledError:
            pass
        session.timeout_task = None
    try:
        await store.publish(session_id, "takeover.failed", {"reason": reason})
    except (KeyError, SessionGone):
        pass


def record_decision(session_id: str, decision: dict[str, Any]) -> None:
    session = store._sessions.get(session_id)
    if session is None:
        raise KeyError(session_id)
    session.latest_decision = dict(decision)


async def wearer_reconnect(session_id: str) -> None:
    session = store._sessions.get(session_id)
    if session is None:
        raise KeyError(session_id)
    if session.state != SessionState.family_joined:
        return
    session.wearer_connected = True
    try:
        await store.publish(session_id, "wearer.reconnected", {})
    except (KeyError, SessionGone):
        pass


async def end_session(session_id: str) -> None:
    await store.end(session_id)


def get_session(session_id: str) -> Session:
    return store.get(session_id)
