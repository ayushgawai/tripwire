# Tripwire

Tripwire is a real-time call safety assistant that monitors suspicious conversations, detects scam patterns through live transcription analysis, and automatically brings in a trusted family member before a risky decision is made. It uses in-memory session state, WebSocket event streaming, and pluggable provider modules for call transport, transcription, risk detection, and AI voice.

## Ownership

| Person | Owns | Files / folders |
| --- | --- | --- |
| Ayush | Integration, backend session coordinator, demo planning, video, final fixes | `backend/app.py`, `backend/session.py`, `shared/`, `demo/`, root configuration |
| Manav | Call transport, audio routing, voice worker, takeover, daughter joining | `backend/calls/`, `frontend/components/call/` |
| Pratham | Transcript normalization, risk detector, evidence and intervention text | `backend/intelligence/`, `fixtures/` |
| Naman | All API keys, provider access, wearable audio adapter, setup instructions | `backend/audio/`, `docs/setup.md`, `.env.example` |
| Dev | Wearer, caller, family, and presenter pages | `frontend/app/`, `frontend/components/ui/` |

## Quickstart

```
make venv
cp .env.example .env
make backend
make test
```

Naman owns `.env.example` and the setup instructions at `docs/setup.md`.

## Contracts

The frozen API and event contract is at `shared/COORDINATOR.md`.
