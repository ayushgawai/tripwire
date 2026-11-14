"""Call-module errors. Safe to surface as event payload reasons; never include tokens."""

from __future__ import annotations


class CallError(Exception):
    """Base error for call transport / takeover."""

    code: str = "call_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message

    def as_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class IllegalTransitionError(CallError):
    code = "illegal_transition"


class SessionAccessError(CallError):
    code = "session_access_denied"


class RolePermissionError(CallError):
    code = "role_permission_denied"


class DuplicateOperationError(CallError):
    code = "duplicate_operation"


class ProviderError(CallError):
    code = "provider_error"


class RoutingConfirmationError(CallError):
    code = "routing_confirmation_failed"


class VoiceWorkerError(CallError):
    code = "voice_worker_error"


class TakeoverFailedError(CallError):
    code = "takeover_failed"


class FamilyJoinError(CallError):
    code = "family_join_failed"


class SessionEndedError(CallError):
    code = "session_ended"
