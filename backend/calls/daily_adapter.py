"""Daily.co REST adapter — rooms and short-lived meeting tokens.

API key stays server-side. Never log tokens or Authorization headers.
Verified against Daily REST docs (POST /rooms, POST /meeting-tokens).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from .errors import DuplicateOperationError, ProviderError
from .models import ParticipantRole, ProviderCredentials, utc_now_iso
from .provider_interface import CallProvider, RoomInfo

DAILY_API_BASE = "https://api.daily.co/v1"


def _role_user_name(role: ParticipantRole) -> str:
    return {
        ParticipantRole.CALLER: "Caller",
        ParticipantRole.WEARER: "Wearer",
        ParticipantRole.FAMILY: "Family",
        ParticipantRole.ASSISTANT: "Tripwire Assistant",
    }[role]


def _clip_user_id(user_id: str) -> str:
    """Daily user_id max length is 36 characters."""
    return user_id[:36]


class DailyCallProvider(CallProvider):
    name = "daily"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("DAILY_API_KEY", "")
        self._owns_client = client is None
        self._client = client
        self._rooms: dict[str, RoomInfo] = {}
        self._rooms_by_name: dict[str, str] = {}

    def is_fixture_mode(self) -> bool:
        return False

    def _require_key(self) -> str:
        if not self._api_key:
            raise ProviderError(
                "DAILY_API_KEY missing — use CALL_PROVIDER=mock for Local Fixture mode",
                code="daily_key_missing",
            )
        return self._api_key

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=DAILY_API_BASE,
                timeout=20.0,
                headers={
                    "Authorization": f"Bearer {self._require_key()}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def create_room(self, session_id: str) -> RoomInfo:
        if session_id in self._rooms:
            return self._rooms[session_id]
        self._require_key()
        # Room names: lowercase alphanumeric + dashes; keep opaque + short.
        room_name = f"tw-{session_id.replace('_', '-')[:40]}"
        if room_name in self._rooms_by_name and self._rooms_by_name[room_name] != session_id:
            raise DuplicateOperationError("Daily room name already bound to another session")
        client = await self._http()
        # Private room: join requires meeting token.
        payload: dict[str, Any] = {
            "name": room_name,
            "privacy": "private",
            "properties": {
                "start_audio_off": False,
                "start_video_off": True,
                "enable_chat": False,
                "exp": int(time.time()) + 60 * 60 * 4,
            },
        }
        resp = await client.post("/rooms", json=payload)
        if resp.status_code == 400 and "already exists" in resp.text.lower():
            # Idempotent recovery: fetch existing room.
            get = await client.get(f"/rooms/{room_name}")
            if get.status_code >= 400:
                raise ProviderError(f"Daily room exists but fetch failed: HTTP {get.status_code}")
            data = get.json()
        elif resp.status_code >= 400:
            raise ProviderError(f"Daily create room failed: HTTP {resp.status_code}")
        else:
            data = resp.json()
        info = RoomInfo(
            room_name=data["name"],
            room_url=data["url"],
            provider=self.name,
            fixture_mode=False,
        )
        self._rooms[session_id] = info
        self._rooms_by_name[info.room_name] = session_id
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
        owner = self._rooms_by_name.get(room_name)
        if owner is not None and owner != session_id:
            raise ProviderError("Refusing token: room belongs to a different session")
        if session_id not in self._rooms:
            raise ProviderError("Create the room before issuing tokens")
        clipped = _clip_user_id(user_id)
        exp = int(time.time()) + max(60, ttl_seconds)
        properties: dict[str, Any] = {
            "room_name": room_name,
            "exp": exp,
            "eject_at_token_exp": True,
            "user_id": clipped,
            "user_name": _role_user_name(role),
            "start_video_off": True,
            "start_audio_off": False,
            "is_owner": role == ParticipantRole.ASSISTANT,
            "permissions": {
                "hasPresence": True,
                "canSend": ["audio"],
                "canAdmin": role == ParticipantRole.ASSISTANT,
            },
        }
        client = await self._http()
        resp = await client.post("/meeting-tokens", json={"properties": properties})
        if resp.status_code >= 400:
            raise ProviderError(f"Daily meeting token failed: HTTP {resp.status_code}")
        token = resp.json().get("token")
        if not token or not isinstance(token, str):
            raise ProviderError("Daily meeting token response missing token")
        room = self._rooms[session_id]
        from datetime import datetime, timezone

        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return ProviderCredentials(
            session_id=session_id,
            role=role,
            room_name=room_name,
            room_url=room.room_url,
            token=token,
            expires_at=expires_at,
            user_id=clipped,
            provider=self.name,
            fixture_mode=False,
        )

    async def delete_room(self, room_name: str) -> None:
        if not self._api_key:
            return
        try:
            client = await self._http()
            await client.delete(f"/rooms/{room_name}")
        except Exception:
            # Best-effort cleanup; do not raise into session end path.
            pass
        sid = self._rooms_by_name.pop(room_name, None)
        if sid:
            self._rooms.pop(sid, None)
