"""Bridge between Manav's backend/calls (CallSessionManager) and Ayush's coordinator.

Implements the 4 functions shared/COORDINATOR.md expects from the calls module, makes Manav's layer
use OUR session tokens (one token per role works everywhere), and maps Manav's lifecycle events onto
coordinator hooks so the coordinator remains the only source of state + event sequence.
"""

from __future__ import annotations

from typing import Any

from backend import session
from backend.calls.adapters.session_bridge import SessionBridge
from backend.calls.errors import SessionAccessError
from backend.calls.models import ParticipantRole, RoutingConfirmation, utc_now_iso
from backend.calls.session_manager import CallSessionManager

# Events whose meaning the coordinator owns: translate to hooks instead of re-publishing.
_COORDINATOR_OWNED = {"takeover.started", "family.alert", "session.ended"}


class _CoordinatorAccess:
    """Manav's SessionAccessValidator backed by coordinator tokens.

    ponytail: any valid token of this session is accepted for any role (app.py routes already
    enforce per-role auth); user_id derives from the requested role so join/confirm ids match.
    """

    def issue(self, session_id: str, role: ParticipantRole) -> str:
        tokens = session.get_session(session_id).tokens
        return tokens.get(role.value) or tokens["presenter"]

    def validate_access(self, session_id: str, access_token: str, role: ParticipantRole) -> str:
        if not access_token or session.store.role_for_token(session_id, access_token) is None:
            raise SessionAccessError("Invalid session access token")
        return f"{role.value[:6]}_{session_id.replace('-', '')[:16]}"[:36]


class _CoordinatorPublisher:
    async def publish_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> dict:
        if event_type == "takeover.active":
            await session.mark_wearer_audio_blocked(session_id)
            await session.mark_assistant_ready(session_id)
            return {}
        if event_type == "takeover.failed":
            await session.fail_takeover(session_id, str(payload.get("reason", "calls failure")))
            return {}
        if event_type == "family.joined":
            await session.mark_family_joined(session_id, payload)
            return {}
        if event_type == "wearer.reconnected":
            await session.wearer_reconnect(session_id)
            return {}
        if event_type in _COORDINATOR_OWNED:
            return {}
        # Call-module detail events (participant.joined, routing.confirmed, worker.ready, ...).
        try:
            return await session.publish_event(session_id, event_type, payload)
        except (KeyError, session.SessionGone):
            return {}


manager = CallSessionManager(
    bridge=SessionBridge(publisher=_CoordinatorPublisher(), access=_CoordinatorAccess())
)


async def _attach(session_id: str) -> None:
    await manager.attach_session(session_id)  # idempotent


# ── shared/COORDINATOR.md interface ─────────────────────────────────────

async def create_join_credentials(session_id: str, role: str) -> dict:
    await _attach(session_id)
    r = ParticipantRole(role)
    if r == ParticipantRole.FAMILY:
        manager.enable_family_join_credentials(session_id)
    return await manager.join(session_id, role=r, access_token=_CoordinatorAccess().issue(session_id, r))


async def start_takeover(session_id: str, decision: dict) -> dict:
    """Ayush already published takeover.started and entered protecting.

    Sync Manav's call snapshot, start the voice worker, then notify
    mark_assistant_ready. Wearer routing confirmation arrives separately via
    POST /signals {wearer_audio_blocked}.
    """
    await _attach(session_id)
    manager.enable_family_join_credentials(session_id)
    await manager.prepare_coordinator_takeover(
        session_id, decision_id=str(decision.get("decision_id", ""))
    )
    await manager.start_voice_worker(session_id)
    # Coordinator owns takeover.active gating (routing signal + assistant ready).
    await session.mark_assistant_ready(session_id)
    return {"accepted": True, "worker_ready": True}


async def stop_assistant(session_id: str) -> None:
    worker = manager._workers.pop(session_id, None)
    if worker is not None and worker.is_running():
        await worker.stop(reason="family_joined")


async def end_call(session_id: str) -> None:
    if session_id in manager._sessions:
        await manager.end_session(session_id)


# ── extra routes Manav's frontend hook calls (wired in app.py) ──────────

async def confirm_routing(session_id: str, body: dict) -> dict:
    await _attach(session_id)
    conf = RoutingConfirmation(
        session_id=session_id,
        caller_audio_blocked=bool(body.get("caller_audio_blocked")),
        wearer_microphone_paused=bool(body.get("wearer_microphone_paused")),
        timestamp=body.get("timestamp") or utc_now_iso(),
    )
    return await manager.confirm_routing(session_id, conf)


async def confirm_provider_join(session_id: str, body: dict, token: str) -> dict:
    await _attach(session_id)
    return await manager.confirm_provider_join(
        session_id,
        role=ParticipantRole(body["role"]),
        access_token=token,
        provider_participant_id=str(body.get("provider_participant_id", "")),
    )


async def confirm_family_joined(session_id: str, body: dict, token: str) -> dict:
    await _attach(session_id)
    return await manager.confirm_family_joined(
        session_id,
        access_token=token,
        provider_participant_id=str(body.get("provider_participant_id", "")),
        user_id_from_provider=body.get("user_id_from_provider"),
    )


async def reconnect_wearer(session_id: str, token: str) -> dict:
    return await manager.reconnect_wearer(session_id, access_token=token)
