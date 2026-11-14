"""Construct call provider / voice worker from environment (no secrets logged)."""

from __future__ import annotations

import os

from .mock_provider import MockCallProvider
from .mock_voice_worker import MockVoiceWorker
from .provider_interface import CallProvider, VoiceWorker


def create_call_provider(name: str | None = None) -> CallProvider:
    selected = (name or os.getenv("CALL_PROVIDER", "mock")).strip().lower()
    if selected in {"mock", "fixture", "local"}:
        return MockCallProvider()
    if selected == "daily":
        # Lazy import so mock-only envs do not require httpx Daily wiring at import.
        from .daily_adapter import DailyCallProvider

        return DailyCallProvider()
    raise ValueError(f"Unknown CALL_PROVIDER={selected!r} (use mock|daily)")


def create_voice_worker(name: str | None = None, **kwargs: object) -> VoiceWorker:
    selected = (name or os.getenv("VOICE_WORKER", "mock")).strip().lower()
    if selected in {"mock", "fixture", "local"}:
        return MockVoiceWorker(**kwargs)  # type: ignore[arg-type]
    if selected == "pipecat":
        from .voice_worker import PipecatVoiceWorker

        return PipecatVoiceWorker(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"Unknown VOICE_WORKER={selected!r} (use mock|pipecat)")


def fixture_mode_active() -> bool:
    demo = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}
    provider = os.getenv("CALL_PROVIDER", "mock").strip().lower()
    worker = os.getenv("VOICE_WORKER", "mock").strip().lower()
    return demo or provider in {"mock", "fixture", "local"} or worker in {
        "mock",
        "fixture",
        "local",
    }
