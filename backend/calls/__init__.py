"""Tripwire call transport, takeover, and family-join module (Manav).

Wire into Ayush's session coordinator via adapters.session_bridge.SessionBridge.
"""

from .errors import CallError, IllegalTransitionError, TakeoverFailedError
from .models import (
    CallSessionSnapshot,
    ParticipantRole,
    ProviderCredentials,
    RoutingConfirmation,
    SessionState,
)
from .provider_interface import CallProvider, VoiceWorker
from .state_machine import CallStateMachine

__all__ = [
    "CallError",
    "CallProvider",
    "CallSessionSnapshot",
    "CallStateMachine",
    "IllegalTransitionError",
    "ParticipantRole",
    "ProviderCredentials",
    "RoutingConfirmation",
    "SessionState",
    "TakeoverFailedError",
    "VoiceWorker",
]

__version__ = "0.1.0"
