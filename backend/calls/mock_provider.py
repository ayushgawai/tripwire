"""LOCAL FIXTURE call provider — deterministic rooms/tokens, clearly labeled.

Never present MockCallProvider success as live Daily success.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .errors import DuplicateOperationError, ProviderError
from .models import ParticipantRole, ProviderCredentials, utc_now_iso
from .provider_interface import CallProvider, RoomInfo


def _exp_iso(ttl_seconds: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


class MockCallProvider(CallProvider):
    """In-memory provider for local fixture / demo replay mode."""

    name = "mock"

    def __init__(self) -> None:
        self._rooms: dict[str, RoomInfo] = {}  # session_id -> room
        self._rooms_by_name: dict[str, str] = {}  # room_name -> session_id
        self._tokens_issued: set[str] = set()
        self._deleted: set[str] = set()

    def is_fixture_mode(self) -> bool:
        return True

    async def create_room(self, session_id: str) -> RoomInfo:
        if session_id in self._rooms:
            # Idempotent: return existing room; do not create duplicates.
            return self._rooms[session_id]
        room_name = f"fixture_{hashlib.sha256(session_id.encode()).hexdigest()[:12]}"
        if room_name in self._rooms_by_name:
            raise DuplicateOperationError(
                f"Room name collision for session {session_id}"
            )
        info = RoomInfo(
            room_name=room_name,
            room_url=f"https://fixture.tripwire.local/{room_name}",
            provider=self.name,
            fixture_mode=True,
        )
        self._rooms[session_id] = info
        self._rooms_by_name[room_name] = session_id
        return info

    async def create_meeting_token(
        self,
        *,
        session_id: str,
        room_name: str,
        role: ParticipantRole,
        user_id: str,
        ttl_seconds: int = 600,
    ) -> ProviderCredentials:
        if room_name in self._deleted:
            raise ProviderError(f"Room {room_name} has been deleted")
        owner = self._rooms_by_name.get(room_name)
        if owner is None:
            raise ProviderError(f"Unknown room {room_name}")
        if owner != session_id:
            raise ProviderError("Token session does not match room owner session")
        # Opaque fixture token — not a real Daily JWT. Prefix makes misuse obvious.
        nonce = secrets.token_hex(8)
        token = f"fixture.{session_id}.{role.value}.{nonce}"
        self._tokens_issued.add(token)
        return ProviderCredentials(
            session_id=session_id,
            role=role,
            room_name=room_name,
            room_url=self._rooms[session_id].room_url,
            token=token,
            expires_at=_exp_iso(ttl_seconds),
            user_id=user_id,
            provider=self.name,
            fixture_mode=True,
        )

    async def delete_room(self, room_name: str) -> None:
        sid = self._rooms_by_name.pop(room_name, None)
        if sid and sid in self._rooms:
            del self._rooms[sid]
        self._deleted.add(room_name)

    def room_for_session(self, session_id: str) -> RoomInfo | None:
        return self._rooms.get(session_id)

    def was_token_issued(self, token: str) -> bool:
        return token in self._tokens_issued
