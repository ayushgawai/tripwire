"""Verified AI takeover lifecycle with routing + worker readiness gates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .errors import (
    DuplicateOperationError,
    IllegalTransitionError,
    RoutingConfirmationError,
    TakeoverFailedError,
    VoiceWorkerError,
)
from .mock_voice_worker import DEFAULT_OPENING_LINE
from .models import (
    ParticipantRole,
    RoutingConfirmation,
    SessionState,
    utc_now_iso,
)

if TYPE_CHECKING:
    from .session_manager import CallSessionManager


class TakeoverController:
    """Owns protecting → assistant_active transitions for a CallSessionManager."""

    def __init__(self, manager: CallSessionManager) -> None:
        self._m = manager

    async def start_takeover(
        self,
        session_id: str,
        *,
        decision_id: str,
        recommended_action: str = "takeover",
        risk: str = "high",
    ) -> dict[str, Any]:
        snap = self._m._get(session_id)
        machine = self._m._machine(session_id)
        machine.assert_not_ended()

        if recommended_action != "takeover" or risk != "high":
            return {
                "accepted": False,
                "reason": "decision_does_not_recommend_takeover",
                "state": snap.state.value,
            }

        # Duplicate high-risk: do not spawn another worker/alert.
        if snap.takeover_decision_id is not None:
            if snap.state in {
                SessionState.PROTECTING,
                SessionState.ASSISTANT_ACTIVE,
                SessionState.FAMILY_JOINED,
            }:
                raise DuplicateOperationError(
                    "Takeover already in progress or completed for this session"
                )

        if snap.state != SessionState.MONITORING:
            raise IllegalTransitionError(
                f"Cannot start takeover from state {snap.state.value}"
            )

        machine.transition(SessionState.PROTECTING, reason="takeover_started")
        snap.state = SessionState.PROTECTING
        snap.takeover_decision_id = decision_id
        snap.wearer_protected = True
        snap.routing_confirmed = False
        snap.worker_ready = False
        snap.updated_at = utc_now_iso()

        await self._m.bridge.publish(
            session_id,
            "takeover.started",
            {
                "decision_id": decision_id,
                "routing_command": {
                    "block_caller_audio_for_wearer": True,
                    "pause_wearer_microphone": True,
                    "do_not_mute_caller_globally": True,
                },
                "fixture_mode": snap.fixture_mode,
            },
        )
        return {"accepted": True, "state": snap.state.value, "decision_id": decision_id}

    async def confirm_routing(
        self, session_id: str, confirmation: RoutingConfirmation
    ) -> dict[str, Any]:
        snap = self._m._get(session_id)
        self._m._machine(session_id).assert_not_ended()
        if confirmation.session_id != session_id:
            raise RoutingConfirmationError("Routing confirmation session mismatch")
        if snap.state != SessionState.PROTECTING:
            raise RoutingConfirmationError(
                f"Routing confirmation only valid in protecting (got {snap.state.value})"
            )
        if not confirmation.is_complete():
            await self.fail_takeover(
                session_id,
                reason="routing_incomplete",
                detail=confirmation.to_dict(),
            )
            raise RoutingConfirmationError(
                "caller_audio_blocked and wearer_microphone_paused required"
            )

        snap.routing_confirmed = True
        snap.updated_at = utc_now_iso()
        await self._m.bridge.publish(
            session_id,
            "routing.confirmed",
            confirmation.to_dict(),
        )
        return await self._maybe_activate(session_id)

    async def start_voice_worker(self, session_id: str) -> dict[str, Any]:
        snap = self._m._get(session_id)
        self._m._machine(session_id).assert_not_ended()
        if snap.state != SessionState.PROTECTING:
            raise TakeoverFailedError("Worker start requires protecting state")
        if session_id in self._m._workers and self._m._workers[session_id].is_running():
            raise DuplicateOperationError("Voice worker already running")

        assert snap.provider_room_url and snap.provider_room_name
        # Bot token: assistant role, server-minted (not client invite).
        bot_user = f"asst_{session_id.replace('-', '')[:12]}"[:36]
        try:
            creds = await self._m.provider.create_meeting_token(
                session_id=session_id,
                room_name=snap.provider_room_name,
                role=ParticipantRole.ASSISTANT,
                user_id=bot_user,
                ttl_seconds=self._m._ttl,
            )
            worker = self._m._worker_factory()
            self._m._workers[session_id] = worker
            await worker.start(
                session_id=session_id,
                room_url=snap.provider_room_url,
                token=creds.token,
                opening_line=DEFAULT_OPENING_LINE,
            )
            await worker.wait_until_ready(timeout_seconds=15.0)
        except (VoiceWorkerError, Exception) as exc:  # noqa: BLE001
            await self.fail_takeover(session_id, reason="worker_failed", detail=str(exc))
            raise TakeoverFailedError(f"Voice worker failed: {exc}") from exc

        snap.worker_ready = True
        snap.updated_at = utc_now_iso()
        await self._m.bridge.publish(
            session_id,
            "worker.ready",
            {
                "fixture_mode": worker.is_fixture_mode(),
                "worker": worker.name,
            },
        )
        return await self._maybe_activate(session_id)

    async def _maybe_activate(self, session_id: str) -> dict[str, Any]:
        snap = self._m._get(session_id)
        if snap.state != SessionState.PROTECTING:
            return {"accepted": True, "state": snap.state.value, "activated": False}
        if not (snap.routing_confirmed and snap.worker_ready):
            return {
                "accepted": True,
                "state": snap.state.value,
                "activated": False,
                "waiting_for": [
                    name
                    for name, ok in (
                        ("routing_confirmation", snap.routing_confirmed),
                        ("worker_ready", snap.worker_ready),
                    )
                    if not ok
                ],
            }
        # Final gate: session still active.
        self._m._machine(session_id).assert_not_ended()
        self._m._machine(session_id).transition(
            SessionState.ASSISTANT_ACTIVE, reason="takeover_active"
        )
        snap.state = SessionState.ASSISTANT_ACTIVE
        snap.updated_at = utc_now_iso()
        await self._m.bridge.publish(
            session_id,
            "takeover.active",
            {
                "decision_id": snap.takeover_decision_id,
                "caller_audio_blocked": True,
                "wearer_microphone_paused": True,
                "worker_ready": True,
                "fixture_mode": snap.fixture_mode,
            },
        )
        # Family alert once at activation (duplicate-safe).
        if not snap.family_alert_sent:
            snap.family_alert_sent = True
            await self._m.bridge.publish(
                session_id,
                "family.alert",
                {
                    "decision_id": snap.takeover_decision_id,
                    "message": "Tripwire paused a call for family verification.",
                },
            )
        return {"accepted": True, "state": snap.state.value, "activated": True}

    async def fail_takeover(
        self, session_id: str, *, reason: str, detail: Any = None
    ) -> dict[str, Any]:
        snap = self._m._get(session_id)
        snap.last_error = reason
        snap.updated_at = utc_now_iso()
        worker = self._m._workers.pop(session_id, None)
        if worker is not None and worker.is_running():
            await worker.stop(reason=f"takeover_failed:{reason}")
        await self._m.bridge.publish(
            session_id,
            "takeover.failed",
            {"reason": reason, "detail": detail, "offer_end_call": True},
        )
        return {"accepted": True, "failed": True, "reason": reason}
