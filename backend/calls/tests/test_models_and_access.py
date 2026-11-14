"""Model and access-validator tests."""

from __future__ import annotations

import pytest

from backend.calls.adapters.session_bridge import (
    InMemoryEventPublisher,
    InviteAccessValidator,
)
from backend.calls.errors import RolePermissionError, SessionAccessError
from backend.calls.models import (
    CallSessionSnapshot,
    ParticipantRole,
    RoutingConfirmation,
    SessionState,
)


def test_routing_confirmation_complete() -> None:
    conf = RoutingConfirmation(
        session_id="s1",
        caller_audio_blocked=True,
        wearer_microphone_paused=True,
        timestamp="2026-11-14T20:00:00Z",
    )
    assert conf.is_complete()
    assert conf.to_dict()["caller_audio_blocked"] is True


def test_routing_confirmation_incomplete() -> None:
    conf = RoutingConfirmation(
        session_id="s1",
        caller_audio_blocked=True,
        wearer_microphone_paused=False,
        timestamp="2026-11-14T20:00:00Z",
    )
    assert not conf.is_complete()


def test_snapshot_hides_wearer_fields_from_caller() -> None:
    snap = CallSessionSnapshot(
        session_id="s1",
        state=SessionState.PROTECTING,
        wearer_protected=True,
        last_error="secret",
    )
    caller_view = snap.to_public_dict(for_role=ParticipantRole.CALLER)
    assert caller_view["wearer_protected"] is False
    assert "last_error" not in caller_view


@pytest.mark.asyncio
async def test_event_publisher_sequences() -> None:
    pub = InMemoryEventPublisher()
    e1 = await pub.publish_event("s1", "takeover.started", {"a": 1})
    e2 = await pub.publish_event("s1", "takeover.active", {"a": 2})
    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e1.event_id != e2.event_id


def test_access_validator_rejects_role_alone() -> None:
    v = InviteAccessValidator(secret="test-secret")
    with pytest.raises(SessionAccessError):
        v.validate_access("s1", "caller", ParticipantRole.CALLER)


def test_access_validator_accepts_issued_token() -> None:
    v = InviteAccessValidator(secret="test-secret")
    token = v.issue("s1", ParticipantRole.WEARER)
    uid = v.validate_access("s1", token, ParticipantRole.WEARER)
    assert uid.startswith("wearer_s1_")


def test_access_validator_rejects_cross_session() -> None:
    v = InviteAccessValidator(secret="test-secret")
    token = v.issue("s1", ParticipantRole.FAMILY)
    with pytest.raises(SessionAccessError):
        v.validate_access("s2", token, ParticipantRole.FAMILY)


def test_access_validator_rejects_role_mismatch() -> None:
    v = InviteAccessValidator(secret="test-secret")
    token = v.issue("s1", ParticipantRole.CALLER)
    with pytest.raises(RolePermissionError):
        v.validate_access("s1", token, ParticipantRole.FAMILY)
