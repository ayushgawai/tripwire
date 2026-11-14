"""Ayush coordinator interface (shared/COORDINATOR.md).

app.py imports these from backend.calls:
  create_join_credentials, start_takeover, stop_assistant, end_call
"""

from __future__ import annotations

import logging
from typing import Any

from .factory import create_call_provider, create_voice_worker
from .models import ParticipantRole
from .session_manager import CallSessionManager

logger = logging.getLogger("tripwire.calls")

_manager: CallSessionManager | None = None


def get_call_manager() -> CallSessionManager:
    global _manager
    if _manager is None:
        _manager = CallSessionManager(
            provider=create_call_provider(),
            worker_factory=create_voice_worker,
        )
    return _manager


def reset_call_manager_for_tests() -> None:
    """Test helper — drop singleton so fixtures stay isolated."""
    global _manager
    _manager = None


def _role(role: str) -> ParticipantRole:
    try:
        return ParticipantRole(role)
    except ValueError as exc:
        raise ValueError(f"Unsupported call role: {role}") from exc


async def create_join_credentials(session_id: str, role: str) -> dict[str, Any]:
    """Issue short-lived provider credentials for a role already authorized by Ayush."""
    mgr = get_call_manager()
    await mgr.attach_session(session_id)
    participant_role = _role(role)
    if participant_role == ParticipantRole.ASSISTANT:
        raise ValueError("Assistant joins via voice worker, not /join")
    # Ayush already validated X-Session-Token; mint provider creds bound to session+role.
    return await mgr.issue_coordinator_credentials(session_id, role=participant_role)


async def start_takeover(session_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    """Called by Ayush after begin_takeover published takeover.started + family.alert.

    Starts the voice worker only. Wearer routing is confirmed via
    POST /signals {signal: wearer_audio_blocked} -> mark_wearer_audio_blocked.
    Worker readiness notifies Ayush via mark_assistant_ready.
    """
    mgr = get_call_manager()
    await mgr.attach_session(session_id)
    decision_id = str(decision.get("decision_id", ""))
    try:
        await mgr.prepare_coordinator_takeover(session_id, decision_id=decision_id)
        await mgr.start_voice_worker(session_id)
        # Notify Ayush — takeover.active only when routing also confirmed.
        try:
            from backend.session import mark_assistant_ready

            await mark_assistant_ready(session_id)
        except ImportError:
            logger.warning("backend.session unavailable; standalone worker ready only")
            await mgr.takeover.confirm_worker_ready_standalone(session_id)
        return {"accepted": True, "worker_ready": True, "decision_id": decision_id}
    except Exception as exc:  # noqa: BLE001 — surface to Ayush fail_takeover
        try:
            from backend.session import fail_takeover as session_fail

            await session_fail(session_id, str(exc))
        except ImportError:
            await mgr.takeover.fail_takeover(session_id, reason=str(exc))
        raise


async def stop_assistant(session_id: str) -> None:
    """Stop voice worker immediately (family joined or session end)."""
    mgr = get_call_manager()
    await mgr.stop_voice_worker(session_id, reason="stop_assistant")


async def end_call(session_id: str) -> None:
    """Cleanup provider room + worker for an ended session."""
    mgr = get_call_manager()
    try:
        await mgr.end_session(session_id)
    except Exception:  # noqa: BLE001 — best-effort cleanup
        await mgr.stop_voice_worker(session_id, reason="end_call")
        snap = mgr._sessions.get(session_id)
        if snap and snap.provider_room_name:
            await mgr.provider.delete_room(snap.provider_room_name)


async def on_family_provider_joined(
    session_id: str, participant: dict[str, Any]
) -> dict[str, Any]:
    """Call from app.py when family Daily/mock participant-joined is confirmed.

    Stops the assistant and asks Ayush to transition to family_joined.
    """
    await stop_assistant(session_id)
    try:
        from backend.session import mark_family_joined

        ok = await mark_family_joined(session_id, participant)
        return {"accepted": bool(ok), "assistant_stopped": True}
    except ImportError:
        mgr = get_call_manager()
        # Standalone fixture path.
        from .models import ParticipantRole

        invites = mgr._invite_tokens.get(session_id, {})
        token = invites.get("family")
        if not token:
            return {"accepted": False, "reason": "no_family_invite"}
        result = await mgr.confirm_family_joined(
            session_id,
            access_token=token,
            provider_participant_id=str(
                participant.get("provider_participant_id")
                or participant.get("id")
                or "unknown"
            ),
            user_id_from_provider=participant.get("user_id"),
        )
        return result
