"""Explicit call session state machine with illegal-transition rejection."""

from __future__ import annotations

from .errors import IllegalTransitionError, SessionEndedError
from .models import SessionState

# Allowed directed edges. Self-transitions are handled as safe duplicates separately.
ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.MONITORING: frozenset(
        {SessionState.PROTECTING, SessionState.ENDED}
    ),
    SessionState.PROTECTING: frozenset(
        {
            SessionState.ASSISTANT_ACTIVE,
            # Family may join after alert even if activation was incomplete.
            SessionState.FAMILY_JOINED,
            SessionState.ENDED,
        }
    ),
    SessionState.ASSISTANT_ACTIVE: frozenset(
        {SessionState.FAMILY_JOINED, SessionState.ENDED}
    ),
    SessionState.FAMILY_JOINED: frozenset({SessionState.ENDED}),
    SessionState.ENDED: frozenset(),
}


class CallStateMachine:
    """Validates and applies session state transitions."""

    def __init__(self, initial: SessionState = SessionState.MONITORING) -> None:
        self._state = initial

    @property
    def state(self) -> SessionState:
        return self._state

    def can_transition(self, target: SessionState) -> bool:
        if self._state == SessionState.ENDED and target != SessionState.ENDED:
            return False
        if self._state == target:
            return True  # idempotent no-op
        return target in ALLOWED_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: SessionState, *, reason: str = "") -> SessionState:
        if self._state == SessionState.ENDED and target != SessionState.ENDED:
            raise SessionEndedError(
                f"Cannot transition from ended to {target.value}"
                + (f" ({reason})" if reason else "")
            )
        if self._state == target:
            return self._state
        allowed = ALLOWED_TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            raise IllegalTransitionError(
                f"Illegal transition {self._state.value} -> {target.value}"
                + (f": {reason}" if reason else ""),
                code="illegal_transition",
            )
        self._state = target
        return self._state

    def assert_not_ended(self) -> None:
        if self._state == SessionState.ENDED:
            raise SessionEndedError("Session has ended")

    def reset_for_tests(self, state: SessionState = SessionState.MONITORING) -> None:
        """Test helper only — production sessions create a new machine."""
        self._state = state
