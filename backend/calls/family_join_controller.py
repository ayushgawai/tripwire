"""Family join confirmation and explicit wearer reconnection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .errors import FamilyJoinError, RolePermissionError, SessionAccessError
from .models import ParticipantRole, SessionState, utc_now_iso

if TYPE_CHECKING:
    from .session_manager import CallSessionManager


class FamilyJoinController:
    def __init__(self, manager: CallSessionManager) -> None:
        self._m = manager

    async def on_family_provider_joined(
        self,
        session_id: str,
        *,
        access_token: str,
        provider_participant_id: str,
        user_id_from_provider: str | None = None,
    ) -> dict[str, Any]:
        """Publish family.joined only after real provider participant confirmation."""
        snap = self._m._get(session_id)
        machine = self._m._machine(session_id)
        machine.assert_not_ended()

        if not snap.family_alert_sent and snap.state == SessionState.MONITORING:
            raise FamilyJoinError("Family cannot join before alert/protection")

        expected_uid = self._m.bridge.access.validate_access(
            session_id, access_token, ParticipantRole.FAMILY
        )
        if user_id_from_provider and user_id_from_provider != expected_uid:
            raise SessionAccessError(
                "Family provider user_id does not match session-scoped credential"
            )

        # Ensure credentials were issued for this session (not another).
        record = snap.participants.get(ParticipantRole.FAMILY.value)
        if record is None:
            # Allow confirm after join() issued creds in same flow.
            raise FamilyJoinError(
                "Issue family join credentials before confirming provider join"
            )
        if record.user_id != expected_uid:
            raise SessionAccessError("Family user mismatch for session")

        record.provider_participant_id = provider_participant_id
        record.joined = True
        record.joined_at = utc_now_iso()
        snap.family_joined = True
        snap.wearer_protected = True
        snap.wearer_reconnected = False
        snap.updated_at = utc_now_iso()

        # Stop assistant immediately.
        worker = self._m._workers.pop(session_id, None)
        if worker is not None and worker.is_running():
            await worker.stop(reason="family_joined")

        if snap.state != SessionState.FAMILY_JOINED:
            if snap.state in {
                SessionState.ASSISTANT_ACTIVE,
                SessionState.PROTECTING,
            }:
                machine.transition(SessionState.FAMILY_JOINED, reason="family_joined")
                snap.state = SessionState.FAMILY_JOINED
            else:
                raise FamilyJoinError(
                    f"Cannot mark family joined from state {snap.state.value}"
                )

        await self._m.bridge.publish(
            session_id,
            "family.joined",
            {
                "provider_participant_id": provider_participant_id,
                "user_id": expected_uid,
                "assistant_stopped": True,
                "wearer_protected": True,
                "family_in_control": True,
            },
        )
        return {
            "accepted": True,
            "state": snap.state.value,
            "family_joined": True,
            "assistant_stopped": True,
        }

    async def reconnect_wearer(
        self, session_id: str, *, access_token: str
    ) -> dict[str, Any]:
        """Explicit action only — never auto-reconnect after family join."""
        snap = self._m._get(session_id)
        self._m._machine(session_id).assert_not_ended()
        if snap.state != SessionState.FAMILY_JOINED:
            raise RolePermissionError("Reconnect wearer only after family_joined")
        self._m.bridge.access.validate_access(
            session_id, access_token, ParticipantRole.WEARER
        )
        if not snap.family_joined:
            raise FamilyJoinError("Family must be joined before reconnecting wearer")

        snap.wearer_reconnected = True
        snap.wearer_protected = False
        snap.updated_at = utc_now_iso()
        await self._m.bridge.publish(
            session_id,
            "wearer.reconnected",
            {
                "explicit": True,
                "wearer_protected": False,
            },
        )
        return {
            "accepted": True,
            "wearer_reconnected": True,
            "wearer_protected": False,
            "state": snap.state.value,
        }
