"""LOCAL FIXTURE voice worker — same interface as live Pipecat worker.

Labeled fixture: does not call LLM/TTS providers. Ready after start().
"""

from __future__ import annotations

import asyncio

from .errors import VoiceWorkerError
from .provider_interface import VoiceWorker

DEFAULT_OPENING_LINE = (
    "I am Tripwire, an AI assistant. This conversation has been paused "
    "for family verification. Please explain your request."
)


class MockVoiceWorker(VoiceWorker):
    """Deterministic mock worker for local development and tests."""

    name = "mock"

    def __init__(self, *, fail_on_start: bool = False, ready_delay: float = 0.0) -> None:
        self._fail_on_start = fail_on_start
        self._ready_delay = ready_delay
        self._running = False
        self._ready = False
        self._session_id: str | None = None
        self._opening_line: str | None = None
        self._stop_reason: str | None = None
        self._spoken: list[str] = []
        self._caller_inputs: list[str] = []

    def is_fixture_mode(self) -> bool:
        return True

    def is_running(self) -> bool:
        return self._running

    def is_ready(self) -> bool:
        return self._ready

    async def start(
        self,
        *,
        session_id: str,
        room_url: str,
        token: str,
        opening_line: str = DEFAULT_OPENING_LINE,
    ) -> None:
        # Intentionally ignore token content; never log it.
        _ = room_url, token
        if self._running:
            raise VoiceWorkerError("Mock worker already running (duplicate start)")
        if self._fail_on_start:
            raise VoiceWorkerError("Mock worker forced start failure")
        self._session_id = session_id
        self._opening_line = opening_line
        self._running = True
        self._ready = False
        self._stop_reason = None
        if self._ready_delay > 0:
            await asyncio.sleep(self._ready_delay)
        if not self._running:
            raise VoiceWorkerError("Mock worker stopped before ready")
        self._ready = True
        self._spoken.append(opening_line)

    async def wait_until_ready(self, timeout_seconds: float = 15.0) -> None:
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while not self._ready:
            if not self._running:
                raise VoiceWorkerError("Worker stopped before readiness")
            if asyncio.get_event_loop().time() > deadline:
                raise VoiceWorkerError("Timed out waiting for mock worker readiness")
            await asyncio.sleep(0.01)

    async def stop(self, *, reason: str = "") -> None:
        self._running = False
        self._ready = False
        self._stop_reason = reason or "stopped"

    async def ingest_caller_input(self, text: str) -> str | None:
        """Optional fixture helper: record caller text; never invent payment promises."""
        if not self._running or not self._ready:
            return None
        self._caller_inputs.append(text)
        # One short safe reply only — no negotiation / impersonation.
        reply = (
            "A family member will verify the request before anyone acts."
        )
        self._spoken.append(reply)
        return reply

    @property
    def spoken_lines(self) -> list[str]:
        return list(self._spoken)

    @property
    def stop_reason(self) -> str | None:
        return self._stop_reason
