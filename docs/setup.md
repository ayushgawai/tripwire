# Tripwire setup

Owner: Naman (API keys, provider access, wearable audio adapter, setup instructions).

## DECISIONS (frozen; change only by agreement)

| Topic | Decision | Source |
| --- | --- | --- |
| Language / runtime | Python 3.11, `pip` + `venv` (`.venv` at repo root). Repo had no deps file when this was written. | repo state |
| My deps file | `backend/audio/requirements.txt` (inside my path). Shared dependency files are Ayush's; see "Requests to other owners". | plan: Ayush owns dependency files |
| Audio format contract | **16 kHz, mono, signed 16-bit PCM little-endian (Deepgram `encoding=linear16`), 20 ms frames = 320 samples = 640 bytes.** The plan does not state a format; this is our default and matches Deepgram live streaming params `encoding=linear16&sample_rate=16000&channels=1`. | default (flagged) |
| Who consumes my adapter | Ambient mode only (optional feature): wearable/laptop audio → Deepgram live STT → finalized text posted as `speaker="ambient"` to `POST /api/sessions/{id}/transcripts`. In call mode, audio goes through Daily in the browser, not through this adapter. | plan: "Optional only after the required flow works: one ambient conversation using the wearable microphone"; "In ambient mode use speaker=ambient" |
| Adapter interface | `backend/audio/base.py`: abstract `AudioSource` with `async start()`, `async stop()`, `async for frame in source` yielding `AudioFrame(data: bytes, seq: int, timestamp: float)` where `len(data) == 640`; properties `sample_rate`, `channels`, `encoding`, `frame_ms`, `source_label`. Usable as `async with source:`. | this module |
| Source labels | `wearable`, `laptop_mic`, `file_replay`. Labels always reflect the real source; a fallback never reports `wearable`. | plan: "label it honestly" |
| File layout | `backend/audio/{__init__,base,laptop_mic,file_replay,wearable,factory,demo}.py`, `backend/audio/tests/`, `backend/audio/provider_checks/{common,daily,deepgram,gemini,elevenlabs,run_all}.py` | this module |
| Selection | `get_audio_source()` in `factory.py` reads `AUDIO_SOURCE` (`wearable` \| `laptop` \| `file`, default `laptop`) and `AUDIO_FILE_PATH`. `wearable` init failure → warning + laptop mic fallback. | added by Naman (not in plan; flagged) |
| Env vars | Plan contract: `DAILY_API_KEY, DEEPGRAM_API_KEY, GEMINI_API_KEY, GEMINI_MODEL, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, BACKEND_URL=http://localhost:8000, NEXT_PUBLIC_BACKEND_URL=http://localhost:8000, DEMO_MODE=false`. Additions: `AUDIO_SOURCE=laptop`, `AUDIO_FILE_PATH=`. | plan + addition |
| Env loading | `python-dotenv`, loading `.env` from the repo root. | default |
| Provider checks | One script per provider; exit 0 = PASS, 1 = FAIL, 2 = BLOCKED (key missing). Never print key values; print only `set`/`missing` and HTTP status. Run: `python -m backend.audio.provider_checks.run_all`. | this module |
| Provider owners | Daily: Manav (call transport). Deepgram: Manav (live STT in voice worker) with Pratham consuming transcripts. Gemini: Pratham (risk detector) + Manav (assistant dialogue). ElevenLabs: Manav (assistant speech). Naman verifies all credentials. | plan ownership table (Deepgram owner inferred; flagged) |
| Wearable | Plan names "Vexo hardware" / "the band" with a "supplied SDK". SDK is not in the repo. | plan |
