"""Provider credential checks (Daily, Deepgram, Gemini, ElevenLabs).

Run from the repo root:
    python -m backend.audio.provider_checks.run_all
    python -m backend.audio.provider_checks.daily   # etc.

Exit codes: 0 PASS, 1 FAIL, 2 BLOCKED (required env var missing).
"""
