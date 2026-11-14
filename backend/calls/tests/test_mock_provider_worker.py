"""Mock provider and mock voice worker tests."""

from __future__ import annotations

import pytest

from backend.calls.errors import ProviderError, VoiceWorkerError
from backend.calls.factory import create_call_provider, create_voice_worker
from backend.calls.mock_provider import MockCallProvider
from backend.calls.mock_voice_worker import DEFAULT_OPENING_LINE, MockVoiceWorker
from backend.calls.models import ParticipantRole


@pytest.mark.asyncio
async def test_mock_room_idempotent() -> None:
    p = MockCallProvider()
    r1 = await p.create_room("sess_a")
    r2 = await p.create_room("sess_a")
    assert r1.room_name == r2.room_name
    assert r1.fixture_mode is True
    assert p.is_fixture_mode()


@pytest.mark.asyncio
async def test_mock_token_scoped_to_session_room() -> None:
    p = MockCallProvider()
    room = await p.create_room("sess_a")
    creds = await p.create_meeting_token(
        session_id="sess_a",
        room_name=room.room_name,
        role=ParticipantRole.CALLER,
        user_id="caller_sess_a_x",
    )
    assert creds.token.startswith("fixture.")
    assert creds.session_id == "sess_a"
    assert creds.fixture_mode is True
    with pytest.raises(ProviderError):
        await p.create_meeting_token(
            session_id="sess_other",
            room_name=room.room_name,
            role=ParticipantRole.CALLER,
            user_id="bad",
        )


@pytest.mark.asyncio
async def test_mock_worker_lifecycle() -> None:
    w = MockVoiceWorker()
    await w.start(
        session_id="s1",
        room_url="https://fixture.local/r",
        token="fixture.token",
    )
    await w.wait_until_ready()
    assert w.is_ready()
    assert DEFAULT_OPENING_LINE in w.spoken_lines
    reply = await w.ingest_caller_input("It has to happen now.")
    assert reply is not None
    assert "payment" not in reply.lower()
    await w.stop(reason="family_joined")
    assert not w.is_running()
    assert w.stop_reason == "family_joined"


@pytest.mark.asyncio
async def test_mock_worker_duplicate_start() -> None:
    w = MockVoiceWorker()
    await w.start(session_id="s1", room_url="u", token="t")
    with pytest.raises(VoiceWorkerError):
        await w.start(session_id="s1", room_url="u", token="t")


@pytest.mark.asyncio
async def test_mock_worker_fail_on_start() -> None:
    w = MockVoiceWorker(fail_on_start=True)
    with pytest.raises(VoiceWorkerError):
        await w.start(session_id="s1", room_url="u", token="t")


def test_factory_defaults_to_mock() -> None:
    assert create_call_provider("mock").name == "mock"
    assert create_voice_worker("mock").name == "mock"
