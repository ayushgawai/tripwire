"""Tripwire call transport, takeover, and family-join module (Manav).

Ayush coordinator imports (shared/COORDINATOR.md):
  create_join_credentials, start_takeover, stop_assistant, end_call
"""

from .coordinator_api import (
    create_join_credentials,
    end_call,
    get_call_manager,
    on_family_provider_joined,
    reset_call_manager_for_tests,
    start_takeover,
    stop_assistant,
)
from .errors import CallError, IllegalTransitionError, TakeoverFailedError
from .models import (
    CallSessionSnapshot,
    ParticipantRole,
    ProviderCredentials,
    RoutingConfirmation,
    SessionState,
)
from .provider_interface import CallProvider, VoiceWorker
from .session_manager import CallSessionManager
from .state_machine import CallStateMachine

__all__ = [
    "CallError",
    "CallProvider",
    "CallSessionManager",
    "CallSessionSnapshot",
    "CallStateMachine",
    "IllegalTransitionError",
    "ParticipantRole",
    "ProviderCredentials",
    "RoutingConfirmation",
    "SessionState",
    "TakeoverFailedError",
    "VoiceWorker",
    "create_join_credentials",
    "end_call",
    "get_call_manager",
    "on_family_provider_joined",
    "reset_call_manager_for_tests",
    "start_takeover",
    "stop_assistant",
]

__version__ = "0.1.0"
