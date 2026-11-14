"""Session attach, role join, cross-session rejection, cleanup."""

from __future__ import annotations

import pytest

from backend.calls.adapters.session_bridge import SessionBridge
from backend.calls.errors import RolePermissionError, SessionAccessError
from backend.calls.mock_provider import MockCallProvider
from backend.calls.models import ParticipantRole, SessionState
from backend.calls.session_manager import CallSessionManager


@pytest.fixture
def manager() -> CallSessionManager:
    return CallSessionManager(provider=MockCallProvider(), bridge=SessionBridge())


@pytest.mark.asyncio
async def test_attach_and_join_caller_wearer(manager: CallSessionManager) -> None:
    await manager.attach_session("demo_001")
    invites = manager.get_invite_tokens("demo_001")
    caller = await manager.join(
        "demo_001",
        role=ParticipantRole.CALLER,
        access_token=invites["caller"],
    )
    wearer = await manager.join(
        "demo_001",
        role=ParticipantRole.WEARER,
        access_token=invites["wearer"],
    )
    assert caller["accepted"] is True
    assert wearer["credentials"]["role"] == "wearer"
    assert caller["credentials"]["token"].startswith("fixture.")
    assert caller["credentials"]["session_id"] == "demo_001"
    snap = manager.snapshot("demo_001")
    assert snap["state"] == SessionState.MONITORING.value
    assert snap["fixture_mode"] is True


@pytest.mark.asyncio
async def test_cross_session_token_rejected(manager: CallSessionManager) -> None:
    await manager.attach_session("s1")
    await manager.attach_session("s2")
    invites_s1 = manager.get_invite_tokens("s1")
    with pytest.raises(SessionAccessError):
        await manager.join(
            "s2",
            role=ParticipantRole.CALLER,
            access_token=invites_s1["caller"],
        )


@pytest.mark.asyncio
async def test_family_blocked_during_monitoring(manager: CallSessionManager) -> None:
    await manager.attach_session("s1")
    invites = manager.get_invite_tokens("s1")
    with pytest.raises(RolePermissionError):
        await manager.join(
            "s1",
            role=ParticipantRole.FAMILY,
            access_token=invites["family"],
        )


@pytest.mark.asyncio
async def test_refresh_reissue_credentials(manager: CallSessionManager) -> None:
    await manager.attach_session("s1")
    invites = manager.get_invite_tokens("s1")
    first = await manager.join(
        "s1", role=ParticipantRole.CALLER, access_token=invites["caller"]
    )
    second = await manager.join(
        "s1", role=ParticipantRole.CALLER, access_token=invites["caller"]
    )
    assert first["accepted"] and second["accepted"]
    assert first["credentials"]["token"] != second["credentials"]["token"]


@pytest.mark.asyncio
async def test_provider_join_confirmation_and_end(manager: CallSessionManager) -> None:
    await manager.attach_session("s1")
    invites = manager.get_invite_tokens("s1")
    await manager.join("s1", role=ParticipantRole.WEARER, access_token=invites["wearer"])
    conf = await manager.confirm_provider_join(
        "s1",
        role=ParticipantRole.WEARER,
        access_token=invites["wearer"],
        provider_participant_id="prov_wearer_1",
    )
    assert conf["joined"] is True
    ended = await manager.end_session("s1")
    assert ended["state"] == SessionState.ENDED.value
    with pytest.raises(Exception):
        await manager.join(
            "s1", role=ParticipantRole.CALLER, access_token=invites["caller"]
        )


@pytest.mark.asyncio
async def test_daily_adapter_requires_key() -> None:
    from backend.calls.daily_adapter import DailyCallProvider

    p = DailyCallProvider(api_key="")
    with pytest.raises(Exception):
        await p.create_room("x")
