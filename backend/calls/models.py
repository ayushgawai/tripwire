"""Call-session domain models (provider-neutral)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


class SessionState(str, Enum):
    MONITORING = "monitoring"
    PROTECTING = "protecting"
    ASSISTANT_ACTIVE = "assistant_active"
    FAMILY_JOINED = "family_joined"
    ENDED = "ended"


class ParticipantRole(str, Enum):
    CALLER = "caller"
    WEARER = "wearer"
    FAMILY = "family"
    ASSISTANT = "assistant"


class CallUiStatus(str, Enum):
    """UI-facing status labels (demo-readable in <1s)."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    MONITORING = "monitoring"
    PROTECTION_STARTING = "protection_starting"
    PROTECTED = "protected"
    AI_ASSISTANT_ACTIVE = "ai_assistant_active"
    FAMILY_ALERT_SENT = "family_alert_sent"
    FAMILY_JOINING = "family_joining"
    FAMILY_JOINED = "family_joined"
    RECONNECTING_WEARER = "reconnecting_wearer"
    CALL_ENDED = "call_ended"
    TAKEOVER_FAILED = "takeover_failed"
    PROVIDER_ERROR = "provider_error"
    RECONNECTING = "reconnecting"
    LOCAL_FIXTURE = "local_fixture"


ALLOWED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "transcript.final",
        "risk.updated",
        "takeover.started",
        "takeover.active",
        "takeover.failed",
        "family.alert",
        "family.joined",
        "session.ended",
        "error",
        "routing.confirmed",
        "participant.joined",
        "participant.left",
        "worker.ready",
        "worker.error",
        "wearer.reconnected",
    }
)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    session_id: str
    sequence: int
    type: str
    timestamp: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "type": self.type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @staticmethod
    def create(
        session_id: str,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        timestamp: str | None = None,
    ) -> EventEnvelope:
        return EventEnvelope(
            event_id=event_id or f"evt_{uuid4().hex[:12]}",
            session_id=session_id,
            sequence=sequence,
            type=event_type,
            timestamp=timestamp or utc_now_iso(),
            payload=payload,
        )


@dataclass
class ParticipantRecord:
    role: ParticipantRole
    user_id: str
    provider_participant_id: str | None = None
    joined: bool = False
    joined_at: str | None = None
    access_token_jti: str | None = None


@dataclass
class RoutingConfirmation:
    session_id: str
    caller_audio_blocked: bool
    wearer_microphone_paused: bool
    timestamp: str
    confirmed_by_role: ParticipantRole = ParticipantRole.WEARER

    def is_complete(self) -> bool:
        return self.caller_audio_blocked and self.wearer_microphone_paused

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "caller_audio_blocked": self.caller_audio_blocked,
            "wearer_microphone_paused": self.wearer_microphone_paused,
            "timestamp": self.timestamp,
            "confirmed_by_role": self.confirmed_by_role.value,
        }


@dataclass
class ProviderCredentials:
    """Short-lived, role-scoped client credentials. Never log token values."""

    session_id: str
    role: ParticipantRole
    room_name: str
    room_url: str
    token: str
    expires_at: str
    user_id: str
    provider: str
    fixture_mode: bool = False

    def public_dict(self) -> dict[str, Any]:
        """Safe client payload (token is short-lived by design)."""
        return {
            "session_id": self.session_id,
            "role": self.role.value,
            "room_name": self.room_name,
            "room_url": self.room_url,
            "token": self.token,
            "expires_at": self.expires_at,
            "user_id": self.user_id,
            "provider": self.provider,
            "fixture_mode": self.fixture_mode,
        }


@dataclass
class CallSessionSnapshot:
    session_id: str
    state: SessionState
    participants: dict[str, ParticipantRecord] = field(default_factory=dict)
    last_sequence: int = 0
    provider_room_name: str | None = None
    provider_room_url: str | None = None
    takeover_decision_id: str | None = None
    routing_confirmed: bool = False
    worker_ready: bool = False
    family_alert_sent: bool = False
    family_joined: bool = False
    wearer_protected: bool = False
    wearer_reconnected: bool = False
    fixture_mode: bool = False
    last_error: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_public_dict(self, *, for_role: ParticipantRole | None = None) -> dict[str, Any]:
        """Role-filtered snapshot. Caller never receives private evidence fields."""
        base: dict[str, Any] = {
            "session_id": self.session_id,
            "state": self.state.value,
            "last_sequence": self.last_sequence,
            "participants": {
                role: {
                    "role": record.role.value,
                    "joined": record.joined,
                    "joined_at": record.joined_at,
                }
                for role, record in self.participants.items()
            },
            "routing_confirmed": self.routing_confirmed,
            "worker_ready": self.worker_ready,
            "family_alert_sent": self.family_alert_sent,
            "family_joined": self.family_joined,
            "wearer_protected": self.wearer_protected,
            "wearer_reconnected": self.wearer_reconnected,
            "fixture_mode": self.fixture_mode,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }
        if for_role == ParticipantRole.CALLER:
            # Caller must not see wearer-only warnings / private evidence hooks.
            base.pop("last_error", None)
            base["wearer_protected"] = False
        return base
