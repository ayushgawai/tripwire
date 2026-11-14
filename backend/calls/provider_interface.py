"""Provider-neutral call provider interfaces.

UI and controllers depend on these protocols, never on Daily types directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from .models import ParticipantRole, ProviderCredentials


ParticipantJoinedHandler = Callable[[dict[str, Any]], Awaitable[None] | None]
ProviderErrorHandler = Callable[[str], Awaitable[None] | None]


@dataclass(frozen=True)
class RoomInfo:
    room_name: str
    room_url: str
    provider: str
    fixture_mode: bool = False


class CallProvider(ABC):
    """Server-side room + credential lifecycle."""

    name: str = "abstract"

    @abstractmethod
    async def create_room(self, session_id: str) -> RoomInfo:
        """Create or reuse a single room for the session. Must be idempotent per session."""

    @abstractmethod
    async def create_meeting_token(
        self,
        *,
        session_id: str,
        room_name: str,
        role: ParticipantRole,
        user_id: str,
        ttl_seconds: int = 600,
    ) -> ProviderCredentials:
        """Return short-lived, room-scoped credentials. Never log the token."""

    @abstractmethod
    async def delete_room(self, room_name: str) -> None:
        """Best-effort room cleanup."""

    @abstractmethod
    def is_fixture_mode(self) -> bool:
        ...


class VoiceWorker(ABC):
    """Provider-neutral voice worker: hears caller, speaks assistant, stops on command."""

    name: str = "abstract"

    @abstractmethod
    async def start(
        self,
        *,
        session_id: str,
        room_url: str,
        token: str,
        opening_line: str,
    ) -> None:
        ...

    @abstractmethod
    async def wait_until_ready(self, timeout_seconds: float = 15.0) -> None:
        ...

    @abstractmethod
    async def stop(self, *, reason: str = "") -> None:
        ...

    @abstractmethod
    def is_running(self) -> bool:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    @abstractmethod
    def is_fixture_mode(self) -> bool:
        ...


class EventPublisher(Protocol):
    """Integration point for Ayush's session coordinator / WebSocket fan-out."""

    async def publish_event(
        self, session_id: str, event_type: str, payload: dict[str, Any]
    ) -> None: ...


class SessionAccessValidator(Protocol):
    """Validate invite/session access. Role string alone is insufficient."""

    def validate_access(
        self, session_id: str, access_token: str, role: ParticipantRole
    ) -> str:
        """Return validated user_id or raise SessionAccessError / RolePermissionError."""
        ...
