"""Takeover lifecycle, routing confirmation, family join, reconnect."""

from __future__ import annotations

import pytest

from backend.calls.adapters.session_bridge import SessionBridge
from backend.calls.errors import (
    DuplicateOperationError,
    IllegalTransitionError,
    RoutingConfirmationError,
    TakeoverFailedError,
)
from backend.calls.mock_provider import MockCallProvider
from backend.calls.mock_voice_worker import MockVoiceWorker
from backend.calls.models import (
    ParticipantRole,
    RoutingConfirmation,
    SessionState,
    utc_now_iso,
)
from backend.calls.session_manager import CallSessionManager


@pytest.fixture
def manager() -> CallSessionManager:
    return CallSessionManager(
        provider=MockCallProvider(),
        bridge=SessionBridge(),
        worker_factory=lambda: MockVoiceWorker(),
    )


async def _bootstrap(manager: CallSessionManager, sid: str = "demo_001") -> dict[str, str]:
    await manager.attach_session(sid)
    invites = manager.get_invite_tokens(sid)
    await manager.join(sid, role=ParticipantRole.CALLER, access_token=invites["caller"])
    await manager.join(sid, role=ParticipantRole.WEARER, access_token=invites["wearer"])
    return invites


@pytest.mark.asyncio
async def test_low_risk_does_not_takeover(manager: CallSessionManager) -> None:
    await _bootstrap(manager)
    result = await manager.start_takeover(
        "demo_001", decision_id="d1", risk="low", recommended_action="none"
    )
    assert result["accepted"] is False
    assert manager.snapshot("demo_001")["state"] == SessionState.MONITORING.value


@pytest.mark.asyncio
async def test_review_risk_stays_monitoring(manager: CallSessionManager) -> None:
    await _bootstrap(manager)
    result = await manager.start_takeover(
        "demo_001", decision_id="d1", risk="review", recommended_action="alert"
    )
    assert result["accepted"] is False
    assert manager.snapshot("demo_001")["state"] == SessionState.MONITORING.value


@pytest.mark.asyncio
async def test_high_risk_takeover_requires_routing_and_worker(
    manager: CallSessionManager,
) -> None:
    await _bootstrap(manager)
    started = await manager.start_takeover(
        "demo_001", decision_id="decision_001", risk="high", recommended_action="takeover"
    )
    assert started["accepted"] is True
    assert manager.snapshot("demo_001")["state"] == SessionState.PROTECTING.value

    types = [e.type for e in manager.bridge.publisher.events_for("demo_001")]
    assert "takeover.started" in types
    assert "takeover.active" not in types

    # Worker ready alone is insufficient.
    await manager.start_voice_worker("demo_001")
    types = [e.type for e in manager.bridge.publisher.events_for("demo_001")]
    assert "worker.ready" in types
    assert "takeover.active" not in types

    conf = RoutingConfirmation(
        session_id="demo_001",
        caller_audio_blocked=True,
        wearer_microphone_paused=True,
        timestamp=utc_now_iso(),
    )
    activated = await manager.confirm_routing("demo_001", conf)
    assert activated["activated"] is True
    assert manager.snapshot("demo_001")["state"] == SessionState.ASSISTANT_ACTIVE.value
    types = [e.type for e in manager.bridge.publisher.events_for("demo_001")]
    assert "takeover.active" in types
    assert "family.alert" in types
    assert "routing.confirmed" in types


@pytest.mark.asyncio
async def test_duplicate_high_risk_rejected(manager: CallSessionManager) -> None:
    await _bootstrap(manager)
    await manager.start_takeover(
        "demo_001", decision_id="d1", risk="high", recommended_action="takeover"
    )
    with pytest.raises(DuplicateOperationError):
        await manager.start_takeover(
            "demo_001", decision_id="d2", risk="high", recommended_action="takeover"
        )


@pytest.mark.asyncio
async def test_incomplete_routing_fails_takeover(manager: CallSessionManager) -> None:
    await _bootstrap(manager)
    await manager.start_takeover(
        "demo_001", decision_id="d1", risk="high", recommended_action="takeover"
    )
    with pytest.raises(RoutingConfirmationError):
        await manager.confirm_routing(
            "demo_001",
            RoutingConfirmation(
                session_id="demo_001",
                caller_audio_blocked=True,
                wearer_microphone_paused=False,
                timestamp=utc_now_iso(),
            ),
        )
    types = [e.type for e in manager.bridge.publisher.events_for("demo_001")]
    assert "takeover.failed" in types


@pytest.mark.asyncio
async def test_worker_failure_publishes_takeover_failed(
    manager: CallSessionManager,
) -> None:
    mgr = CallSessionManager(
        provider=MockCallProvider(),
        bridge=SessionBridge(),
        worker_factory=lambda: MockVoiceWorker(fail_on_start=True),
    )
    await _bootstrap(mgr)
    await mgr.start_takeover(
        "demo_001", decision_id="d1", risk="high", recommended_action="takeover"
    )
    with pytest.raises(TakeoverFailedError):
        await mgr.start_voice_worker("demo_001")
    types = [e.type for e in mgr.bridge.publisher.events_for("demo_001")]
    assert "takeover.failed" in types


@pytest.mark.asyncio
async def test_family_join_stops_ai_and_keeps_wearer_protected(
    manager: CallSessionManager,
) -> None:
    invites = await _bootstrap(manager)
    await manager.start_takeover(
        "demo_001", decision_id="d1", risk="high", recommended_action="takeover"
    )
    await manager.start_voice_worker("demo_001")
    await manager.confirm_routing(
        "demo_001",
        RoutingConfirmation(
            session_id="demo_001",
            caller_audio_blocked=True,
            wearer_microphone_paused=True,
            timestamp=utc_now_iso(),
        ),
    )
    assert manager._workers["demo_001"].is_running()

    await manager.join(
        "demo_001", role=ParticipantRole.FAMILY, access_token=invites["family"]
    )
    # Token alone must NOT mark family joined.
    assert manager.snapshot("demo_001")["family_joined"] is False

    joined = await manager.confirm_family_joined(
        "demo_001",
        access_token=invites["family"],
        provider_participant_id="prov_family_1",
    )
    assert joined["family_joined"] is True
    assert joined["assistant_stopped"] is True
    assert "demo_001" not in manager._workers or not manager._workers.get(
        "demo_001", MockVoiceWorker()
    ).is_running()
    snap = manager.snapshot("demo_001")
    assert snap["state"] == SessionState.FAMILY_JOINED.value
    assert snap["wearer_protected"] is True
    assert snap["wearer_reconnected"] is False

    # Explicit reconnect required.
    recon = await manager.reconnect_wearer(
        "demo_001", access_token=invites["wearer"]
    )
    assert recon["wearer_reconnected"] is True
    assert manager.snapshot("demo_001")["wearer_protected"] is False


@pytest.mark.asyncio
async def test_cross_session_family_rejected(manager: CallSessionManager) -> None:
    invites1 = await _bootstrap(manager, "s1")
    await manager.attach_session("s2")
    invites2 = manager.get_invite_tokens("s2")
    await manager.start_takeover(
        "s1", decision_id="d1", risk="high", recommended_action="takeover"
    )
    manager.enable_family_join_credentials("s1")
    with pytest.raises(Exception):
        await manager.join(
            "s1", role=ParticipantRole.FAMILY, access_token=invites2["family"]
        )
    _ = invites1


@pytest.mark.asyncio
async def test_illegal_transition_monitoring_to_assistant(
    manager: CallSessionManager,
) -> None:
    await _bootstrap(manager)
    with pytest.raises(IllegalTransitionError):
        manager._machine("demo_001").transition(SessionState.ASSISTANT_ACTIVE)


@pytest.mark.asyncio
async def test_full_fixture_flow_repeatable(manager: CallSessionManager) -> None:
    for i in range(3):
        sid = f"repeat_{i}"
        mgr = CallSessionManager(
            provider=MockCallProvider(),
            bridge=SessionBridge(),
            worker_factory=lambda: MockVoiceWorker(),
        )
        invites = await _bootstrap(mgr, sid)
        await mgr.start_takeover(
            sid, decision_id=f"d_{i}", risk="high", recommended_action="takeover"
        )
        await mgr.start_voice_worker(sid)
        await mgr.confirm_routing(
            sid,
            RoutingConfirmation(
                session_id=sid,
                caller_audio_blocked=True,
                wearer_microphone_paused=True,
                timestamp=utc_now_iso(),
            ),
        )
        await mgr.join(sid, role=ParticipantRole.FAMILY, access_token=invites["family"])
        await mgr.confirm_family_joined(
            sid,
            access_token=invites["family"],
            provider_participant_id=f"fam_{i}",
        )
        await mgr.reconnect_wearer(sid, access_token=invites["wearer"])
        await mgr.end_session(sid)
        assert mgr.snapshot(sid)["state"] == SessionState.ENDED.value
