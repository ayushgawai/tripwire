"""Coordinator-facing exports used by Ayush app.py."""

from __future__ import annotations

import pytest

from backend.calls import (
    create_join_credentials,
    end_call,
    reset_call_manager_for_tests,
    start_takeover,
    stop_assistant,
)
from backend.calls.coordinator_api import get_call_manager


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    reset_call_manager_for_tests()
    yield
    reset_call_manager_for_tests()


@pytest.mark.asyncio
async def test_create_join_credentials_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALL_PROVIDER", "mock")
    monkeypatch.setenv("VOICE_WORKER", "mock")
    reset_call_manager_for_tests()
    creds = await create_join_credentials("ses_abc123", "caller")
    assert creds["session_id"] == "ses_abc123"
    assert creds["role"] == "caller"
    assert creds["token"].startswith("fixture.")
    assert creds["fixture_mode"] is True


@pytest.mark.asyncio
async def test_start_takeover_starts_mock_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALL_PROVIDER", "mock")
    monkeypatch.setenv("VOICE_WORKER", "mock")
    reset_call_manager_for_tests()
    await create_join_credentials("ses_t1", "caller")
    result = await start_takeover(
        "ses_t1",
        {
            "decision_id": "decision_001",
            "risk": "high",
            "recommended_action": "takeover",
        },
    )
    assert result["accepted"] is True
    mgr = get_call_manager()
    assert mgr._workers["ses_t1"].is_ready()
    await stop_assistant("ses_t1")
    assert "ses_t1" not in mgr._workers or not mgr._workers.get("ses_t1")
    await end_call("ses_t1")
