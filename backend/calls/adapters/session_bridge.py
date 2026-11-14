"""Integration adapters for Ayush's session coordinator.

Prefer the coordinator exports in `backend.calls` (see shared/COORDINATOR.md):
  create_join_credentials, start_takeover, stop_assistant, end_call,
  on_family_provider_joined.

Standalone tests still use InMemoryEventPublisher + InviteAccessValidator.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from ..errors import RolePermissionError, SessionAccessError
from ..models import ALLOWED_EVENT_TYPES, EventEnvelope, ParticipantRole, utc_now_iso
from ..provider_interface import EventPublisher, SessionAccessValidator


class InMemoryEventPublisher:
    """Fixture/test publisher that assigns monotonic sequences per session."""

    def __init__(self) -> None:
        self._sequences: dict[str, int] = {}
        self.events: list[EventEnvelope] = []
        self._handlers: list[EventPublisher] = []

    def add_listener(self, handler: EventPublisher) -> None:
        self._handlers.append(handler)

    async def publish_event(
        self, session_id: str, event_type: str, payload: dict[str, Any]
    ) -> EventEnvelope:
        if event_type not in ALLOWED_EVENT_TYPES:
            # Allow extension events used by call module; still envelope them.
            pass
        seq = self._sequences.get(session_id, 0) + 1
        self._sequences[session_id] = seq
        envelope = EventEnvelope.create(session_id, seq, event_type, payload)
        self.events.append(envelope)
        for handler in self._handlers:
            await handler.publish_event(session_id, event_type, payload)
        return envelope

    def events_for(self, session_id: str) -> list[EventEnvelope]:
        return [e for e in self.events if e.session_id == session_id]

    def last_sequence(self, session_id: str) -> int:
        return self._sequences.get(session_id, 0)

    def reset(self) -> None:
        self._sequences.clear()
        self.events.clear()


class InviteAccessValidator:
    """HMAC invite tokens: session_id + role + secret. Role alone is rejected."""

    def __init__(self, secret: str | None = None) -> None:
        self._secret = (secret or secrets.token_hex(16)).encode("utf-8")

    def issue(self, session_id: str, role: ParticipantRole) -> str:
        body = f"{session_id}:{role.value}".encode("utf-8")
        sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return f"{session_id}.{role.value}.{sig}"

    def validate_access(
        self, session_id: str, access_token: str, role: ParticipantRole
    ) -> str:
        if not access_token or access_token.count(".") != 2:
            raise SessionAccessError("Missing or malformed session access token")
        sid, role_str, sig = access_token.split(".", 2)
        if sid != session_id:
            raise SessionAccessError("Access token does not match session")
        if role_str != role.value:
            raise RolePermissionError("Access token role mismatch")
        expected = self.issue(session_id, role)
        if not hmac.compare_digest(access_token, expected):
            raise SessionAccessError("Invalid session access token")
        # Stable user_id bound to session+role (Daily user_id max 36 chars).
        digest = hmac.new(
            self._secret, f"uid:{session_id}:{role.value}".encode(), hashlib.sha256
        ).hexdigest()[:10]
        # role(6) + _ + sess(12) + _ + dig(10) ~= 30 chars typical.
        sid_part = session_id.replace("-", "")[:12]
        return f"{role.value[:6]}_{sid_part}_{digest}"[:36]


class SessionBridge:
    """Convenience bundle Manav's controllers expect from the session layer."""

    def __init__(
        self,
        publisher: InMemoryEventPublisher | None = None,
        access: InviteAccessValidator | None = None,
    ) -> None:
        self.publisher = publisher or InMemoryEventPublisher()
        self.access = access or InviteAccessValidator()

    async def publish(
        self, session_id: str, event_type: str, payload: dict[str, Any]
    ) -> EventEnvelope:
        if "timestamp" not in payload:
            payload = {**payload, "recorded_at": utc_now_iso()}
        return await self.publisher.publish_event(session_id, event_type, payload)
