"""Gemini check: verify model exists, then a tiny generateContent call.

Docs: https://ai.google.dev/api/models  (GET v1beta/models/{model}, list models)
      https://ai.google.dev/api/generate-content  (POST v1beta/models/{model}:generateContent)
Key is sent via the x-goog-api-key header, never in the URL.

    python -m backend.audio.provider_checks.gemini --list-models
"""
from __future__ import annotations

import sys

import httpx

from .common import BLOCKED, FAIL, PASS, TIMEOUT, Result, env, explain_status, main_for, require, scrub

PROVIDER, OWNER = "Gemini", "Pratham+Manav"
API = "https://generativelanguage.googleapis.com/v1beta"
LIST_HINT = "list models with: python -m backend.audio.provider_checks.gemini --list-models"
# Thinking models count reasoning tokens against the budget; leave headroom so
# the call still returns 200 with text. No thinkingConfig is sent because it
# errors on models that do not support thinking (and thinkingLevel errors on 2.x).
MAX_OUTPUT_TOKENS = 512


def _explain(r: httpx.Response) -> str:
    """Gemini returns 400 API_KEY_INVALID (not 401) for a bad key."""
    if r.status_code == 400 and "API_KEY_INVALID" in r.text:
        return "400 bad key (API_KEY_INVALID)"
    return explain_status(r.status_code)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"x-goog-api-key": env("GEMINI_API_KEY")})


def _model_path(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


def list_models() -> int:
    ok, vars_ = require("GEMINI_API_KEY")
    if not ok:
        print(vars_)
        return 2
    names: list[str] = []
    token = None
    with _client() as c:
        while True:
            params = {"pageSize": 1000}
            if token:
                params["pageToken"] = token
            r = c.get(f"{API}/models", params=params)
            if r.status_code != 200:
                print(f"HTTP {_explain(r)}")
                return 1
            data = r.json()
            for m in data.get("models", []):
                if "generateContent" in (m.get("supportedGenerationMethods") or []):
                    names.append(m.get("name", "").removeprefix("models/"))
            token = data.get("nextPageToken")
            if not token:
                break
    for n in names:
        print(scrub(n))
    return 0


def check() -> Result:
    ok_key, key_vars = require("GEMINI_API_KEY")
    ok_all, vars_ = require("GEMINI_API_KEY", "GEMINI_MODEL")
    if not ok_all:
        detail = vars_ + ("; " + LIST_HINT if ok_key else "")
        return Result(PROVIDER, OWNER, BLOCKED, "-", detail)
    model = env("GEMINI_MODEL")
    path = _model_path(model)
    with _client() as c:
        m = c.get(f"{API}/{path}")
        if m.status_code == 404:
            return Result(PROVIDER, OWNER, FAIL, "404",
                          f"model '{model}' not found; {LIST_HINT}")
        if m.status_code != 200:
            return Result(PROVIDER, OWNER, FAIL, str(m.status_code),
                          f"get model: {_explain(m)}")
        methods = m.json().get("supportedGenerationMethods") or []
        if methods and "generateContent" not in methods:
            return Result(PROVIDER, OWNER, FAIL, "200",
                          f"model '{model}' does not support generateContent; {LIST_HINT}")
        body = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with OK"}]}],
            "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS},
        }
        g = c.post(f"{API}/{path}:generateContent", json=body)
    if g.status_code != 200:
        return Result(PROVIDER, OWNER, FAIL, f"{m.status_code}/{g.status_code}",
                      f"model={model}; generateContent: {_explain(g)}")
    data = g.json()
    cands = data.get("candidates") or []
    text = ""
    finish = ""
    if cands:
        finish = cands[0].get("finishReason", "")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    got = "text returned" if text.strip() else f"no text (finishReason={finish or 'n/a'})"
    return Result(PROVIDER, OWNER, PASS, f"{m.status_code}/{g.status_code}", f"model={model}; {got}")


if __name__ == "__main__":
    if "--list-models" in sys.argv[1:]:
        try:
            sys.exit(list_models())
        except Exception as exc:  # noqa: BLE001
            print(f"{type(exc).__name__}: {scrub(exc)}")
            sys.exit(1)
    main_for(check, PROVIDER, OWNER)
