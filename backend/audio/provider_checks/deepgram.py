"""Deepgram check: auth (list projects), optional balance, tiny prerecorded transcription.

Docs: https://developers.deepgram.com/reference/manage/v-1/projects/list
      https://developers.deepgram.com/reference/manage/v-1/projects/balances/list
      https://developers.deepgram.com/docs/pre-recorded-audio
      https://developers.deepgram.com/docs/models-languages-overview (nova-3 = prerecorded default)
"""
from __future__ import annotations

import io
import math
import struct
import wave

import httpx

from .common import BLOCKED, FAIL, PASS, TIMEOUT, Result, env, explain_status, main_for, require

PROVIDER, OWNER = "Deepgram", "Manav+Pratham"
API = "https://api.deepgram.com/v1"
MODEL = "nova-3"


def make_wav(seconds: float = 1.0, rate: int = 16000, freq: float = 440.0) -> bytes:
    """~1s 16 kHz mono 16-bit PCM sine tone, in memory."""
    n = int(seconds * rate)
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def check() -> Result:
    ok, vars_ = require("DEEPGRAM_API_KEY")
    if not ok:
        return Result(PROVIDER, OWNER, BLOCKED, "-", vars_)
    headers = {"Authorization": f"Token {env('DEEPGRAM_API_KEY')}"}
    notes: list[str] = []
    with httpx.Client(timeout=TIMEOUT, headers=headers) as c:
        p = c.get(f"{API}/projects")
        if p.status_code != 200:
            return Result(PROVIDER, OWNER, FAIL, str(p.status_code),
                          f"auth (projects): {explain_status(p.status_code)}")
        notes.append(f"projects {p.status_code}")
        projects = p.json().get("projects") or []
        if projects:
            try:
                b = c.get(f"{API}/projects/{projects[0]['project_id']}/balances")
                if b.status_code == 200:
                    bal = b.json().get("balances") or []
                    if bal:
                        notes.append(f"balance={bal[0].get('amount')} {bal[0].get('units', '')}".strip())
                    else:
                        notes.append("balance=none listed")
                else:
                    notes.append(f"balance n/a ({b.status_code})")
            except (httpx.HTTPError, KeyError, ValueError):
                notes.append("balance n/a")
        t = c.post(
            f"{API}/listen",
            params={"model": MODEL},
            content=make_wav(),
            headers={"Content-Type": "audio/wav"},
        )
        if t.status_code != 200:
            notes.append(f"listen: {explain_status(t.status_code)}")
            return Result(PROVIDER, OWNER, FAIL, f"{p.status_code}/{t.status_code}", "; ".join(notes))
        data = t.json()
        if not isinstance(data.get("results"), dict):
            notes.append("listen 200 but no results object")
            return Result(PROVIDER, OWNER, FAIL, f"{p.status_code}/{t.status_code}", "; ".join(notes))
        try:
            text = data["results"]["channels"][0]["alternatives"][0].get("transcript", "")
        except (KeyError, IndexError, TypeError):
            text = ""
        notes.append(f"listen {t.status_code} model={MODEL} transcript_chars={len(text)} (tone: empty ok)")
    return Result(PROVIDER, OWNER, PASS, f"{p.status_code}/{t.status_code}", "; ".join(notes))


if __name__ == "__main__":
    main_for(check, PROVIDER, OWNER)
