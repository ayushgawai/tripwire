# Ayush / Dev integration (Manav call module)

Aligned with `shared/COORDINATOR.md`.

## Module exports (`backend/calls/__init__.py`)

```python
async def create_join_credentials(session_id: str, role: str) -> dict
async def start_takeover(session_id: str, decision: dict) -> dict
async def stop_assistant(session_id: str) -> None
async def end_call(session_id: str) -> None
async def on_family_provider_joined(session_id: str, participant: dict) -> dict
```

`app.py` should:

1. `POST /join` → `await calls.create_join_credentials(session_id, role)`
2. After `begin_takeover` → `await calls.start_takeover(session_id, decision)` (exceptions → `fail_takeover`)
3. On family Daily/mock `participant-joined` (or `POST /family-provider-joined` from family client) → `await calls.on_family_provider_joined(...)` which stops the assistant and calls `session.mark_family_joined`
4. On end → `await calls.end_call(session_id)`

Wearer routing confirmation uses the frozen signal:

`POST /api/sessions/{id}/signals` body `{ "signal": "wearer_audio_blocked" }` → `mark_wearer_audio_blocked`.

Family reconnect:

`POST /signals` `{ "signal": "wearer_reconnect" }` (family/presenter token).

## Dev UI

`frontend/components/ui/CallSurface.tsx` mounts `CallPanel` when `sessionId` + `accessToken` are passed.
Pass those props from wearer/caller/family pages (Dev).

```tsx
import { CallPanel } from "@/components/call";
```

## Local Fixture

```bash
CALL_PROVIDER=mock VOICE_WORKER=mock python -m backend.calls.fixture_demo
```

Never claim mock success as live Daily/Pipecat.
