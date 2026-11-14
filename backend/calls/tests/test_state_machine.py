"""State machine unit tests."""

from __future__ import annotations

import pytest

from backend.calls.errors import IllegalTransitionError, SessionEndedError
from backend.calls.models import SessionState
from backend.calls.state_machine import CallStateMachine


def test_initial_monitoring() -> None:
    sm = CallStateMachine()
    assert sm.state == SessionState.MONITORING


def test_happy_path_transitions() -> None:
    sm = CallStateMachine()
    sm.transition(SessionState.PROTECTING)
    sm.transition(SessionState.ASSISTANT_ACTIVE)
    sm.transition(SessionState.FAMILY_JOINED)
    sm.transition(SessionState.ENDED)
    assert sm.state == SessionState.ENDED


def test_idempotent_same_state() -> None:
    sm = CallStateMachine()
    assert sm.transition(SessionState.MONITORING) == SessionState.MONITORING


def test_illegal_skip_to_family() -> None:
    sm = CallStateMachine()
    with pytest.raises(IllegalTransitionError):
        sm.transition(SessionState.FAMILY_JOINED)


def test_illegal_from_ended() -> None:
    sm = CallStateMachine()
    sm.transition(SessionState.ENDED)
    with pytest.raises(SessionEndedError):
        sm.transition(SessionState.MONITORING)


def test_low_risk_stays_monitoring() -> None:
    """Low/review risk must not force a transition — callers leave state alone."""
    sm = CallStateMachine()
    assert sm.state == SessionState.MONITORING
    assert sm.can_transition(SessionState.PROTECTING)
    # Explicit: monitoring -> assistant_active is illegal
    assert not sm.can_transition(SessionState.ASSISTANT_ACTIVE)


def test_monitoring_can_end() -> None:
    sm = CallStateMachine()
    sm.transition(SessionState.ENDED)
    assert sm.state == SessionState.ENDED
