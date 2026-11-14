"""ElevenLabs check: account/quota, voice lookup, tiny TTS.

Docs: https://elevenlabs.io/docs/api-reference/user/get
      https://elevenlabs.io/docs/api-reference/voices/get
      https://elevenlabs.io/docs/api-reference/text-to-speech/convert
      https://elevenlabs.io/docs/overview/models  (eleven_flash_v2_5: ~100ms, cost-effective)
"""
from __future__ import annotations

import httpx

from .common import BLOCKED, FAIL, PASS, TIMEOUT, Result, env, explain_status, main_for, require

PROVIDER, OWNER = "ElevenLabs", "Manav"
API = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_flash_v2_5"
VOICE_HINT = ("set ELEVENLABS_VOICE_ID (copy a voice id from the ElevenLabs Voices page "
              "or GET /v1/voices)")


def check() -> Result:
    ok, vars_ = require("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID")
    if not env("ELEVENLABS_API_KEY"):
        return Result(PROVIDER, OWNER, BLOCKED, "-", vars_)
    headers = {"xi-api-key": env("ELEVENLABS_API_KEY")}
    notes: list[str] = []
    codes: list[str] = []
    with httpx.Client(timeout=TIMEOUT, headers=headers) as c:
        u = c.get(f"{API}/user")
        codes.append(str(u.status_code))
        if u.status_code == 200:
            sub = u.json().get("subscription") or {}
            used, limit = sub.get("character_count"), sub.get("character_limit")
            notes.append(f"tier={sub.get('tier', '?')}")
            if isinstance(used, int) and isinstance(limit, int):
                notes.append(f"chars remaining={limit - used}/{limit}")
        elif u.status_code == 401 and "invalid_api_key" in u.text:
            return Result(PROVIDER, OWNER, FAIL, "401", f"/user: {explain_status(401)} (invalid_api_key)")
        elif u.status_code in (401, 403):
            # Restricted keys may lack user_read; keep going, TTS is what matters.
            notes.append(f"/user {u.status_code} (restricted key? continuing)")
        else:
            notes.append(f"/user: {explain_status(u.status_code)}")

        voice_id = env("ELEVENLABS_VOICE_ID")
        if not voice_id:
            notes.insert(0, vars_)
            notes.append(VOICE_HINT)
            return Result(PROVIDER, OWNER, BLOCKED, "/".join(codes), "; ".join(notes))

        v = c.get(f"{API}/voices/{voice_id}")
        codes.append(str(v.status_code))
        if v.status_code == 200:
            notes.append(f"voice={v.json().get('name', '?')}")
        else:
            notes.append(f"voice: {explain_status(v.status_code)}")

        t = c.post(
            f"{API}/text-to-speech/{voice_id}",
            params={"output_format": "mp3_22050_32"},
            json={"text": "Tripwire check.", "model_id": MODEL_ID},
            headers={"Accept": "audio/mpeg"},
        )
        codes.append(str(t.status_code))
    http = "/".join(codes)
    if t.status_code != 200:
        notes.append(f"tts: {explain_status(t.status_code)}")
        return Result(PROVIDER, OWNER, FAIL, http, "; ".join(notes))
    notes.append(f"tts model={MODEL_ID} audio_bytes={len(t.content)}")
    status = PASS if v.status_code == 200 and t.content else FAIL
    return Result(PROVIDER, OWNER, status, http, "; ".join(notes))


if __name__ == "__main__":
    main_for(check, PROVIDER, OWNER)
