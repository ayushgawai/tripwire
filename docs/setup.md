# Tripwire setup

Owner: Naman (API keys, provider access, wearable audio adapter, setup instructions).

Everything below runs **from the repo root** (the folder that contains `backend/` and `.env.example`).

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
| Wearable env vars (added, UNVERIFIED adapter) | `WEARABLE_TRANSPORT` (`input_device` \| `ble`, default `input_device`), `WEARABLE_DEVICE_NAME` (default `Vexo`), `WEARABLE_BLE_ADDRESS`, `WEARABLE_BLE_AUDIO_CHAR_UUID`, `WEARABLE_BLE_CODEC` (`pcm16` \| `opus`), `WEARABLE_BLE_SAMPLE_RATE` (`16000`), `WEARABLE_BLE_CHANNELS` (`1`), `WEARABLE_BLE_HEADER_BYTES` (`0`). Read from env by `backend/audio/wearable.py` but **not yet in `.env.example`** (all optional). | added by Naman (not in plan; flagged) |

## 1. Prerequisites

| Need | Notes |
| --- | --- |
| Python 3.11 | `python --version` should print 3.11.x. On macOS you may need `python3` instead of `python`. |
| git | To clone the repo. |
| PortAudio | Bundled inside the `sounddevice` wheels on Windows and macOS (nothing to install). Linux: `sudo apt install libportaudio2`. |
| Headphones | Use them when testing audio so speaker output doesn't feed back into the mic. |

## 2. Install

All commands from the repo root.

| Step | Windows (PowerShell) | macOS / Linux |
| --- | --- | --- |
| Create venv | `python -m venv .venv` | `python3 -m venv .venv` |
| Activate | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Install deps | `pip install -r backend/audio/requirements.txt` | same |
| Create `.env` | `Copy-Item .env.example .env` | `cp .env.example .env` |

- If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.
- Fill `.env` with real values (section 3). **Never commit `.env`** (see section 12: there is no `.gitignore` yet).
- Optional, only for the UNVERIFIED BLE wearable path: `pip install bleak` (Opus also needs `opuslib` + system libopus).

## 3. Getting credentials

| Provider | Where | What you need | Notes |
| --- | --- | --- | --- |
| Daily | dashboard.daily.co → Developers → API key | `DAILY_API_KEY` | Free tier is fine. |
| Deepgram | console.deepgram.com → API keys | `DEEPGRAM_API_KEY` | New accounts get free credit. Key needs **Member** scope or higher to call `/v1/listen`. The check uses model `nova-3`. |
| Gemini | aistudio.google.com/apikey | `GEMINI_API_KEY`, `GEMINI_MODEL` | Pick a model id from `python -m backend.audio.provider_checks.gemini --list-models`. Do **not** use "Gemini Decision 1" — not a real model id. |
| ElevenLabs | elevenlabs.io → Profile → API keys | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Restricted key: enable **Text to Speech**, **Voices (read)**, **User (read)**. Pick a voice in Voice Library / My Voices and copy its voice ID. The check uses `eleven_flash_v2_5` (low latency). Free tier has a monthly character quota. |

Share keys only by private DM or a secret manager (section 10).

## 4. Environment variables

| Name | Used by | Owner | Required? |
| --- | --- | --- | --- |
| `DAILY_API_KEY` | backend / calls (Daily rooms) | Manav | required |
| `DEEPGRAM_API_KEY` | voice worker STT (Manav) + transcripts (Pratham) | Manav | required |
| `GEMINI_API_KEY` | risk detector (Pratham) + assistant dialogue (Manav) | Pratham / Manav | required |
| `GEMINI_MODEL` | same as above | Pratham / Manav | required |
| `ELEVENLABS_API_KEY` | assistant speech (TTS) | Manav | required |
| `ELEVENLABS_VOICE_ID` | assistant speech (TTS) | Manav | required |
| `BACKEND_URL` | backend | Ayush | has default (`http://localhost:8000`) |
| `NEXT_PUBLIC_BACKEND_URL` | frontend | Dev | has default (`http://localhost:8000`). **The only var exposed to the browser. Never put a secret in any `NEXT_PUBLIC_` var.** |
| `DEMO_MODE` | everyone (scripted demo fallback) | Ayush | has default (`false`) |
| `AUDIO_SOURCE` | backend/audio (`laptop` \| `file` \| `wearable`) | Naman | optional (added; default `laptop`) |
| `AUDIO_FILE_PATH` | backend/audio, for `AUDIO_SOURCE=file` | Naman | optional (added) |
| `WEARABLE_*` | backend/audio wearable adapter (see DECISIONS) | Naman | optional (added; not in `.env.example`) |

## 5. Verify credentials

| Command | What it does |
| --- | --- |
| `python -m backend.audio.provider_checks.run_all` | Runs all four checks, prints a table. |
| `python -m backend.audio.provider_checks.run_all --markdown` | Same, as a Markdown table to paste into section 6. |
| `python -m backend.audio.provider_checks.daily` | Daily only. |
| `python -m backend.audio.provider_checks.deepgram` | Deepgram only. |
| `python -m backend.audio.provider_checks.gemini` | Gemini only (`--list-models` lists model ids). |
| `python -m backend.audio.provider_checks.elevenlabs` | ElevenLabs only. |

Exit codes: **0 = PASS, 1 = FAIL, 2 = BLOCKED** (var missing). Output shows only `set`/`missing` and HTTP status, never key values.

| Check | What it calls |
| --- | --- |
| Daily | Creates a private room with `exp` = now + 5 min, then deletes it. |
| Deepgram | `GET /v1/projects`, reads balance, sends a 1 s tone to `/v1/listen` with `nova-3`. |
| Gemini | `GET` the model, then `generateContent` with "Reply with OK". Key sent in a header only (never in the URL). |
| ElevenLabs | `/v1/user` (tier + characters remaining), `/v1/voices/{id}`, one short TTS request (prints byte count). |

| Result | Meaning |
| --- | --- |
| 401 / 403 | Bad key or missing scope/permission. |
| 400 `API_KEY_INVALID` | Gemini's way of saying bad key. |
| 404 | Bad model id (Gemini) or voice id (ElevenLabs). |
| 429 | Rate limited or out of credits/quota. |
| BLOCKED | The env var is missing from `.env`. |

## 6. Credential test status

| Provider | Owner | Status | Date | Notes |
| --- | --- | --- | --- | --- |
| Daily | Manav | BLOCKED | 2026-11-14 | key missing: no .env on Naman's machine yet |
| Deepgram | Manav (+ Pratham) | BLOCKED | 2026-11-14 | key missing: no .env on Naman's machine yet |
| Gemini | Pratham (+ Manav) | BLOCKED | 2026-11-14 | key missing: no .env on Naman's machine yet |
| ElevenLabs | Manav | BLOCKED | 2026-11-14 | key missing: no .env on Naman's machine yet |

- FAIL path verified with fake keys: all four report "bad key" correctly and no key is echoed.
- PASS path is untested until real keys exist.
- **Each module owner runs their check once they have real keys and sends the result (`--markdown` output) to Naman, who updates this table.**

## 7. Audio adapter (`backend/audio`)

**Contract:** 16 kHz, mono, linear16 (signed 16-bit LE), 20 ms frames = 640 bytes. Each frame is `AudioFrame(data, seq, timestamp)`.

Consumer usage (e.g. ambient-mode Deepgram streamer):

```python
from backend.audio import open_audio_source

src = await open_audio_source()          # kind from AUDIO_SOURCE; returns a STARTED source
try:
    print(src.source_label)              # wearable | laptop_mic | file_replay
    async for frame in src:
        await ws.send(frame.data)        # 640 bytes of linear16
finally:
    await src.stop()
```

- Deepgram live params: `encoding=linear16&sample_rate=16000&channels=1`.
- In ambient mode, finalized transcripts are posted with `speaker="ambient"` to `POST /api/sessions/{id}/transcripts`.
- `get_audio_source()` returns an unstarted source (use `async with src:`).

**Switching source:** set `AUDIO_SOURCE` in `.env` to `laptop` (default), `file` (also set `AUDIO_FILE_PATH` to a 16 kHz mono WAV), or `wearable` (falls back to laptop mic if unavailable). The demo's `--source` flag overrides it.

**Quick checks:**

| Command | Purpose |
| --- | --- |
| `python -m backend.audio.demo --make-test-wav test.wav` | Write a 3 s 440 Hz 16 kHz mono test WAV. |
| `python -m backend.audio.demo --source file --file test.wav --seconds 5` | Replay the file in real time. |
| `python -m backend.audio.demo --source laptop --seconds 5` | Capture from the laptop mic. |
| `python -m backend.audio.demo --source wearable` | Try the wearable (falls back to laptop mic with a warning). |
| `python -m pytest backend/audio/tests -q` | Unit tests: 36 pass, no hardware needed. |

The demo prints source label, frames, frames/sec (expected 50), bytes and average RMS in dBFS.

**Measured on Naman's Windows laptop, 2026-11-14:**

| Source | Result |
| --- | --- |
| file | 101 frames / 2 s ≈ 50 fps |
| laptop mic (Realtek) | 149 frames / 3 s; opened natively at 16 kHz |
| wearable | fell back to `laptop_mic` with a warning (no band available) |

## 8. Wearable audio (Vexo Band) — UNVERIFIED, fallback active

**Status:** adapter is written against guesses; never tested with hardware. Laptop-mic fallback is active and always labeled `laptop_mic`. The plan treats wearable/ambient as **optional, after the required flow works**.

**What we know (public sources):**

- VexoAI (YC F26) sells the Vexo Band, a $199 bracelet with a mic — https://www.vexoai.com/, https://www.ycombinator.com/companies/vexo
- No public SDK, developer docs or GitHub.
- Site says the band connects to the Vexo phone app over Bluetooth and "can't work without your phone".
- Privacy policy (https://www.vexoai.com/privacy): phone apps stream band audio to AssemblyAI.
- Only public developer surface: read-only MCP server `https://api.vexoai.com/mcp` (OAuth; transcripts/memories, **no raw audio**) — https://www.vexoai.com/developers/mcp
- Likely transport: proprietary BLE to the phone (inference).

**Not known:** whether it pairs with a laptop (Windows/macOS), whether it exposes a Bluetooth headset profile, BLE service/characteristic UUIDs, codec, sample rate, whether the phone app must disconnect first, latency.

**Adapter modes (`WEARABLE_TRANSPORT`):**

| Mode | How it works | Needs |
| --- | --- | --- |
| `input_device` (default) | Opens an OS audio input whose name contains `WEARABLE_DEVICE_NAME` via sounddevice, converts to 16 kHz mono 640 B frames. | Band paired as a Bluetooth headset/mic; `WEARABLE_DEVICE_NAME` (default `Vexo`). |
| `ble` | bleak skeleton that subscribes to an audio characteristic. Raises `NotImplementedError` where details are unknown. | `pip install bleak`; `WEARABLE_BLE_ADDRESS`, `WEARABLE_BLE_AUDIO_CHAR_UUID`, `WEARABLE_BLE_CODEC` (`pcm16` \| `opus`), `WEARABLE_BLE_SAMPLE_RATE`, `WEARABLE_BLE_CHANNELS`, `WEARABLE_BLE_HEADER_BYTES`. |

**Testing with hardware:**

1. Pair the band with the laptop over Bluetooth (OS settings).
2. List devices: `python -c "import sounddevice as sd; print(sd.query_devices())"`
3. Set `WEARABLE_DEVICE_NAME` in `.env` to part of the band's input device name.
4. Run `python -m backend.audio.demo --source wearable`.
5. If the output says **NOT the wearable**, you are on the laptop-mic fallback; read the warning for the reason.

**Ask organizers for the "supplied SDK"** the plan mentions — it is not in the repo and nothing public exists.

## 9. Troubleshooting

| Symptom | Fix |
| --- | --- |
| "No input device" / PortAudio error | Check a mic is connected and enabled; list devices with `python -c "import sounddevice as sd; print(sd.query_devices())"`. Linux: `sudo apt install libportaudio2`. |
| macOS: zero frames or silence | System Settings → Privacy & Security → Microphone → allow your terminal / IDE, then restart it. |
| Windows: zero frames or silence | Settings → Privacy & security → Microphone → turn on "Let desktop apps access your microphone". |
| Average RMS around -60 dBFS | That is silence: mic muted, wrong device, or permission denied. |
| `ModuleNotFoundError: No module named 'backend'` | Run from the repo root with `python -m ...` (not from inside `backend/`). |
| Provider check exits 1 / 2 | 1 = FAIL (see section 5 result table), 2 = BLOCKED (var missing in `.env`). |
| Garbled characters in Windows console | Use Windows Terminal, or run `$env:PYTHONIOENCODING="utf-8"` (or `chcp 65001`) before the command. |
| PowerShell won't run `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## 10. Secret handling policy

- Keys live **only** in your local `.env`.
- Share keys by private DM or a secret manager — never in group chat, issues, PRs or docs.
- Never put keys in: frontend bundles / `NEXT_PUBLIC_` vars, screenshots, prompts to AI tools, logs, issues, commits.
- The check scripts print only `set` / `missing` and HTTP status.
- If a key leaks anywhere, **rotate it immediately** in the provider dashboard and re-share privately.

## 11. Recommended tooling (all optional)

`backend/audio/provider_checks/` scripts are the source of truth. **No MCP server is required.**

| Tool | Use | Notes |
| --- | --- | --- |
| Deepgram official MCP server — github.com/deepgram/mcp (MIT), docs https://developers.deepgram.com/cli/mcp-server | Check usage / models | Uses your own key; install at user level only, not in the repo. |
| Deepgram docs MCP — https://api.dx.deepgram.com/kapa/mcp | Search Deepgram docs | Read-only, no key. |
| ElevenLabs hosted MCP — https://api.elevenlabs.io/v1/mcp | Check voices / credits | OAuth. The local `elevenlabs-mcp` repo was archived 2026-08-20. Generating speech spends credits. |
| Pipecat examples — github.com/pipecat-ai/pipecat-examples (BSD-2) | Reference for Manav's Daily + Deepgram + ElevenLabs + Gemini worker | Read for patterns. |

Never add third-party skills/plugins to the repo.

## 12. Requests to other owners

| To | Request | Priority |
| --- | --- | --- |
| Ayush (root config) | Add a root `.gitignore` containing at least `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `node_modules/`, `.next/`. **The repo currently has NO `.gitignore`, so `.env` is NOT ignored.** | HIGH |
| Ayush (shared deps) | When a root/backend requirements file exists, include `-r backend/audio/requirements.txt` or merge its packages (`python-dotenv`, `httpx`, `numpy`, `sounddevice`, `pytest`). | medium |
| Ayush | `backend/__init__.py` is not needed (namespace package works); adding one breaks nothing. | info |
| Manav / Pratham | Confirm who opens the Deepgram live stream for ambient mode. Run your provider check once real keys are shared; report the exact missing permission (if any) to Naman. | medium |
| Manav | Confirm the ElevenLabs model (`eleven_flash_v2_5` used in the check) and whether you want an `ELEVENLABS_MODEL` env var (would be a plan change). | low |
