"""Shared helpers for provider checks. Never prints secret values."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = REPO_ROOT / ".env"
TIMEOUT = 20.0

PASS, FAIL, BLOCKED = "PASS", "FAIL", "BLOCKED"
EXIT_CODES = {PASS: 0, FAIL: 1, BLOCKED: 2}

# Env vars whose values must never appear in output.
SECRET_NAMES = (
    "DAILY_API_KEY",
    "DEEPGRAM_API_KEY",
    "GEMINI_API_KEY",
    "ELEVENLABS_API_KEY",
)

_env_loaded = False


def load_env() -> None:
    """Load repo-root .env (if present) without overriding already-set vars."""
    global _env_loaded
    if _env_loaded:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        load_dotenv = None
    if load_dotenv is not None and ENV_PATH.is_file():
        load_dotenv(ENV_PATH, override=False)
    _env_loaded = True


def env(name: str) -> str:
    load_env()
    return (os.environ.get(name) or "").strip()


def require(*names: str) -> tuple[bool, str]:
    """Return (all_set, 'NAME=set, OTHER=missing'). Values are never included."""
    states = [(n, "set" if env(n) else "missing") for n in names]
    ok = all(s == "set" for _, s in states)
    return ok, ", ".join(f"{n}={s}" for n, s in states)


def scrub(text: object) -> str:
    """Replace any loaded secret value appearing in text with '***'."""
    out = str(text)
    for name in SECRET_NAMES:
        val = env(name)
        if val and len(val) >= 3:
            out = out.replace(val, "***")
    return out


def explain_status(code: int | None) -> str:
    if code is None:
        return "no response"
    if code in (401, 403):
        return f"{code} bad key / missing permission"
    if code == 404:
        return f"{code} not found (bad model / voice / resource id)"
    if code == 429:
        return f"{code} rate limited or out of credits/quota"
    if 500 <= code < 600:
        return f"{code} provider outage / server error"
    if 200 <= code < 300:
        return f"{code} ok"
    return f"{code} unexpected status"


@dataclass
class Result:
    provider: str
    owner: str
    status: str
    http_status: str = "-"
    detail: str = ""

    @property
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)

    def __post_init__(self) -> None:
        self.detail = scrub(self.detail)
        self.http_status = scrub(self.http_status)


def exception_result(provider: str, owner: str, exc: BaseException) -> Result:
    return Result(provider, owner, FAIL, "-", f"{type(exc).__name__}: {scrub(exc)}")


def main_for(check_fn: Callable[[], Result], provider: str = "?", owner: str = "?") -> None:
    try:
        r = check_fn()
    except Exception as exc:  # noqa: BLE001
        r = exception_result(provider, owner, exc)
    print(scrub(f"[{r.status}] {r.provider} (owner: {r.owner}) HTTP {r.http_status}"))
    print(scrub(f"  {r.detail}"))
    sys.exit(r.exit_code)
