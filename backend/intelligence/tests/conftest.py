import json

import httpx
import pytest

from backend.intelligence import detector, gemini


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Tests never reach the network: Gemini is off unless a test installs a fake."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini.set_client(None)
    detector._llm_cache.clear()
    yield
    gemini.set_client(None)
    detector._llm_cache.clear()


@pytest.fixture
def fake_gemini():
    """install(reply) -> list of captured requests. reply is a str/dict response text, or an int HTTP status."""

    def install(reply):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if isinstance(reply, int):
                return httpx.Response(reply, text="boom")
            text = reply if isinstance(reply, str) else json.dumps(reply)
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

        gemini.set_client(gemini.GeminiClient("test-key", "test-model", transport=httpx.MockTransport(handler)))
        return requests

    return install
