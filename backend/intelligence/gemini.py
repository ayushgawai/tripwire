"""Minimal async Gemini REST client (generateContent). Configured from GEMINI_API_KEY and GEMINI_MODEL."""

from __future__ import annotations

import json
import os
import time

import httpx

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_SECONDS = 5.0
BACKOFF_SECONDS = 15.0


class GeminiError(RuntimeError):
    """Any failure to get a usable response. Callers fall back to deterministic behavior."""


class GeminiClient:
    def __init__(self, api_key: str, model: str, *, timeout: float = TIMEOUT_SECONDS, transport=None):
        self.model = model
        self._retry_at = 0.0
        # The key travels in a header, never in the URL, so it cannot leak into request logs.
        self._http = httpx.AsyncClient(
            base_url=API_ROOT, headers={"x-goog-api-key": api_key}, timeout=timeout, transport=transport
        )

    async def generate(self, system: str, prompt: str, *, temperature: float = 0.0, schema: dict | None = None) -> str:
        # After a failure, fail fast for a while so a dead key or outage does not add a timeout to every utterance.
        if time.monotonic() < self._retry_at:
            raise GeminiError("Gemini skipped: backing off after a recent failure")
        config: dict = {"temperature": temperature}
        if schema is not None:
            config |= {"responseMimeType": "application/json", "responseJsonSchema": schema}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }
        try:
            return await self._post(body)
        except GeminiError:
            self._retry_at = time.monotonic() + BACKOFF_SECONDS
            raise

    async def _post(self, body: dict) -> str:
        try:
            response = await self._http.post(f"/models/{self.model}:generateContent", json=body)
            response.raise_for_status()
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except httpx.HTTPStatusError as exc:
            raise GeminiError(f"Gemini HTTP {exc.response.status_code}: {exc.response.text[:300]}") from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise GeminiError(f"Gemini request failed: {type(exc).__name__}: {exc}") from exc
        if not text.strip():
            raise GeminiError("Gemini returned no text")
        return text

    async def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        text = await self.generate(system, prompt, schema=schema)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise GeminiError("Gemini JSON is not an object")
        return data

    async def aclose(self) -> None:
        await self._http.aclose()


_client: GeminiClient | None = None


def get_client() -> GeminiClient | None:
    """Shared client (connection reuse keeps latency down), or None when Gemini is not configured."""
    global _client
    if _client is None:
        api_key, model = os.environ.get("GEMINI_API_KEY", "").strip(), os.environ.get("GEMINI_MODEL", "").strip()
        if api_key and model:
            _client = GeminiClient(api_key, model)
    return _client


def set_client(client: GeminiClient | None) -> None:
    """Override the shared client (tests, or explicit wiring by the backend)."""
    global _client
    _client = client
