"""Call session manager: rooms, role join, snapshot, cleanup.

Integrates with Ayush's coordinator via SessionBridge.publish_event.
Does not own HTTP routes — expose methods for session.py to call.
"""

from __future__ import annotations

import os
from typing import Any

from .adapters.session_bridge import InviteAccessValidator, SessionBridge
from .errors import RolePermissionError, SessionAccessError
from .factory import create_call_provider, create_voice_worker, fixture_mode_active
from .family_join_controller import FamilyJoinController
from .models import (
    CallSessionSnapshot,
    ParticipantRecord,
    ParticipantRole,
    RoutingConfirmation,
    SessionState,
    utc_now_iso,
)
from .provider_interface import CallProvider, VoiceWorker
from .state_machine import CallStateMachine
from .takeover_controller import TakeoverController


class CallSessionManager:
    """In-memory call sessions keyed by session_id."""

    def __init__(
        self,
        *,
        bridge: SessionBridge | None = None,
        provider: CallProvider | None = None,
        worker_factory: Any = None,
    ) -> None:
        self.bridge = bridge or SessionBridge(
            access=InviteAccessValidator(secret=os.getenv("CALL_ACCESS_SECRET") or "dev-only")
        )
        self.provider = provider or create_call_provider()
        self._worker_factory = worker_factory or create_voice_worker
        self._sessions: dict[str, CallSessionSnapshot] = {}
        self._machines: dict[str, CallStateMachine] = {}
        self._workers: dict[str, VoiceWorker] = {}
        self._invite_tokens: dict[str, dict[str, str]] = {}
        self._ttl = int(os.getenv("CALL_TOKEN_TTL_SECONDS", "600"))
        self.takeover = TakeoverController(self)
        self.family = FamilyJoinController(self)

    def _get(self, session_id: str) -> CallSessionSnapshot:
        if session_id not in self._sessions:
            raise SessionAccessError(f"Unknown call session {session_id}")
        return self._sessions[session_id]

    def _machine(self, session_id: str) -> CallStateMachine:
        return self._machines[session_id]

    async def attach_session(
        self, session_id: str, *, fixture_mode: bool | None = None
    ) -> CallSessionSnapshot:
        """Create call resources for an existing Tripwire session (Ayush creates session_id)."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        room = await self.provider.create_room(session_id)
        fixture = (
            fixture_mode
            if fixture_mode is not None
            else (self.provider.is_fixture_mode() or fixture_mode_active())
        )
        snap = CallSessionSnapshot(
            session_id=session_id,
            state=SessionState.MONITORING,
            provider_room_name=room.room_name,
            provider_room_url=room.room_url,
            fixture_mode=fixture,
        )
        self._sessions[session_id] = snap
        self._machines[session_id] = CallStateMachine(SessionState.MONITORING)
        # Issue invite tokens per role for controlled demo access.
        invites = {
            role.value: self.bridge.access.issue(session_id, role)
            for role in (
                ParticipantRole.CALLER,
                ParticipantRole.WEARER,
                ParticipantRole.FAMILY,
            )
        }
        self._invite_tokens[session_id] = invites
        return snap

    def get_invite_tokens(self, session_id: str) -> dict[str, str]:
        """Server-side only — for Ayush to hand out via secure demo links. Do not log."""
        self._get(session_id)
        return dict(self._invite_tokens[session_id])

    def snapshot(
        self, session_id: str, *, for_role: ParticipantRole | None = None
    ) -> dict[str, Any]:
        snap = self._get(session_id)
        data = snap.to_public_dict(for_role=for_role)
        data["provider_room_name"] = snap.provider_room_name
        data["provider_room_url"] = snap.provider_room_url
        return data

    async def join(
        self,
        session_id: str,
        *,
        role: ParticipantRole,
        access_token: str,
    ) -> dict[str, Any]:
        snap = self._get(session_id)
        machine = self._machine(session_id)
        machine.assert_not_ended()
        if role == ParticipantRole.ASSISTANT:
            raise RolePermissionError("Assistant joins via voice worker, not /join")
        if role == ParticipantRole.FAMILY and snap.state not in {
            SessionState.ASSISTANT_ACTIVE,
            SessionState.PROTECTING,
            SessionState.FAMILY_JOINED,
        }:
            # Family may request credentials after alert; join confirmation is separate.
            if not snap.family_alert_sent and snap.state == SessionState.MONITORING:
                raise RolePermissionError(
                    "Family cannot join before protection/alert phase"
                )
        user_id = self.bridge.access.validate_access(session_id, access_token, role)
        assert snap.provider_room_name and snap.provider_room_url
        creds = await self.provider.create_meeting_token(
            session_id=session_id,
            room_name=snap.provider_room_name,
            role=role,
            user_id=user_id,
            ttl_seconds=self._ttl,
        )
        record = snap.participants.get(role.value)
        if record is None:
            record = ParticipantRecord(role=role, user_id=user_id)
            snap.participants[role.value] = record
        else:
            # Safe duplicate: re-issue credentials for refresh recovery.
            record.user_id = user_id
        record.access_token_jti = creds.token[:16]  # fingerprint only, not full token
        snap.updated_at = utc_now_iso()
        await self.bridge.publish(
            session_id,
            "participant.joined",
            {
                "role": role.value,
                "user_id": user_id,
                "credential_issued": True,
                "provider_joined": False,
                "note": "Credential issued; provider join confirmation is separate",
            },
        )
        return {
            "accepted": True,
            "credentials": creds.public_dict(),
            "state": snap.state.value,
            "fixture_mode": snap.fixture_mode,
            "access_user_id": user_id,
        }

    async def confirm_provider_join(
        self,
        session_id: str,
        *,
        role: ParticipantRole,
        access_token: str,
        provider_participant_id: str,
    ) -> dict[str, Any]:
        """Client reports actual Daily/mock participant-joined. Required for family.joined."""
        snap = self._get(session_id)
        self._machine(session_id).assert_not_ended()
        user_id = self.bridge.access.validate_access(session_id, access_token, role)
        record = snap.participants.get(role.value)
        if record is None or record.user_id != user_id:
            raise SessionAccessError("Join credentials before confirming provider join")
        record.provider_participant_id = provider_participant_id
        record.joined = True
        record.joined_at = utc_now_iso()
        snap.updated_at = utc_now_iso()
        await self.bridge.publish(
            session_id,
            "participant.joined",
            {
                "role": role.value,
                "user_id": user_id,
                "provider_participant_id": provider_participant_id,
                "provider_joined": True,
            },
        )
        return {"accepted": True, "role": role.value, "joined": True}

    async def end_session(self, session_id: str) -> dict[str, Any]:
        snap = self._get(session_id)
        machine = self._machine(session_id)
        if snap.state != SessionState.ENDED:
            machine.transition(SessionState.ENDED, reason="session_end")
            snap.state = SessionState.ENDED
        worker = self._workers.pop(session_id, None)
        if worker is not None and worker.is_running():
            await worker.stop(reason="session_ended")
        if snap.provider_room_name:
            await self.provider.delete_room(snap.provider_room_name)
        snap.updated_at = utc_now_iso()
        await self.bridge.publish(session_id, "session.ended", {"reason": "ended"})
        return {"accepted": True, "state": SessionState.ENDED.value}

    def issue_demo_access_bundle(self, session_id: str) -> dict[str, str]:
        """Convenience for fixture demos — returns role invite tokens (server/demo only)."""
        return self.get_invite_tokens(session_id)

    async def start_takeover(
        self, session_id: str, *, decision_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        return await self.takeover.start_takeover(
            session_id, decision_id=decision_id, **kwargs
        )

    async def confirm_routing(
        self, session_id: str, confirmation: RoutingConfirmation
    ) -> dict[str, Any]:
        return await self.takeover.confirm_routing(session_id, confirmation)

    async def start_voice_worker(self, session_id: str) -> dict[str, Any]:
        return await self.takeover.start_voice_worker(session_id)

    async def confirm_family_joined(
        self,
        session_id: str,
        *,
        access_token: str,
        provider_participant_id: str,
        user_id_from_provider: str | None = None,
    ) -> dict[str, Any]:
        return await self.family.on_family_provider_joined(
            session_id,
            access_token=access_token,
            provider_participant_id=provider_participant_id,
            user_id_from_provider=user_id_from_provider,
        )

    async def reconnect_wearer(
        self, session_id: str, *, access_token: str
    ) -> dict[str, Any]:
        return await self.family.reconnect_wearer(
            session_id, access_token=access_token
        )

    def enable_family_join_credentials(self, session_id: str) -> None:
        """Allow family /join after alert without requiring assistant_active yet."""
        snap = self._get(session_id)
        snap.family_alert_sent = True
        snap.updated_at = utc_now_iso()
