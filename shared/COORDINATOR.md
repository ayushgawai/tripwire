# Session coordinator contract (owner: Ayush)

Source of truth for how `backend/app.py` + `backend/session.py` behave and how other modules plug in.
Product spec: `Tripwire_Quick_Build_Plan.md`. Machine-readable schemas: `shared/contracts.json`.
Ask Ayush before changing anything here.

## Event envelope
```json
{"event_id": "evt_<uuid hex>", "session_id": "...", "sequence": 1, "type": "transcript.final",
 "timestamp": "2026-11-14T20:00:00Z", "payload": {}}
```
`sequence` starts at 1 per session and increases by 1 per event. Timestamps are UTC ISO with `Z`.
Event types: `transcript.final, risk.updated, takeover.started, takeover.active, takeover.failed,
family.alert, family.joined, wearer.reconnected, session.ended, assistant.spoke, error`.

## States
`monitoring -> protecting -> assistant_active -> family_joined -> ended`
Legal transitions:
- monitoring -> protecting | ended
- protecting -> assistant_active | ended
- assistant_active -> family_joined | ended
- family_joined -> ended
Anything else raises `IllegalTransition` (HTTP 409).
`wearer_connected` is a separate bool on the session: false from `protecting` onward until family sends `wearer_reconnect`.

## Auth
`POST /api/sessions` returns one opaque token per role: `caller, wearer, family, presenter`
(`secrets.token_urlsafe(16)`). Every other HTTP call sends header `X-Session-Token: <token>`; WS uses `?token=`.
Unknown session -> 404. Bad/missing token -> 403. A token's role is what the server trusts; the role in a
request body must match the token's role, except presenter, which may act for any role.

## HTTP + WS
| Method / path | Body | Response |
|---|---|---|
| POST /api/sessions | `{mode: "call"|"ambient", protection_enabled: true}` | `{session_id, state, tokens: {caller, wearer, family, presenter}}` |
| GET /api/sessions/{id} | – | snapshot (below) |
| POST /api/sessions/{id}/join | `{role}` | `calls.create_join_credentials(session_id, role)` result; 501 `{detail}` if calls module missing |
| POST /api/sessions/{id}/transcripts | `{utterance_id, speaker, text, timestamp}` | `{accepted: true, duplicate: bool}` |
| POST /api/sessions/{id}/takeover | `{decision_id}` | `{accepted: true}`; 409 if decision_id != latest decision or state != monitoring |
| POST /api/sessions/{id}/signals | `{signal: "wearer_audio_blocked"|"wearer_reconnect"}` | `{accepted: true}` (wearer_audio_blocked needs wearer/presenter token; wearer_reconnect needs family/presenter token and state family_joined) |
| POST /api/sessions/{id}/end | `{}` | `{accepted: true}`; then any further call on this session -> 410 |
| GET /api/health | – | `{ok: true}` |
| WS /ws/sessions/{id}?token= | – | pushes event envelopes as JSON; clients fetch snapshot first on reconnect |

Snapshot: `{session_id, mode, protection_enabled, state, wearer_connected, transcript: [utterances],
latest_decision, alert, last_sequence, takeover: {status: "idle"|"starting"|"active"|"failed", wearer_audio_blocked, assistant_ready}}`

## Transcript flow (in `app.py`)
1. Validate speaker in `caller, wearer, family, assistant, ambient`. Duplicate `utterance_id` -> `{accepted: true, duplicate: true}`, nothing else happens.
2. Store + publish `transcript.final` (payload = the utterance).
3. If protection_enabled, state is `monitoring`, and speaker is analyzable (call mode: caller|wearer; ambient mode: ambient):
   `decision = await intelligence.analyze_transcript(session_id, analyzable_utterances)`. Store as latest_decision, publish `risk.updated`.
   Analyzer exceptions -> publish `error` `{source: "intelligence", message}` and continue.
4. If `decision.risk == "high"` and `recommended_action == "takeover"` and mode == call -> `begin_takeover(decision)`.
   If `risk in (review, high)` with action `alert` (or ambient mode high) -> publish `family.alert` only (once per decision_id).

## begin_takeover(decision) (in `session.py`, idempotent)
- Only if state == monitoring, else no-op (duplicate high decisions do nothing).
- transition -> protecting, wearer_connected=False, takeover.status=starting.
- publish `takeover.started {decision_id}`, publish `family.alert {decision_id, summary, reasons, evidence}` (alert stored on session).
- app calls `await calls.start_takeover(session_id, decision)`; exception -> `fail_takeover(reason)`.
- Timeout `TAKEOVER_TIMEOUT_S` (env, default 15): if not active by then -> `fail_takeover("timeout")`.

## Hooks other modules call (import from `backend.session`)
```python
async def publish_event(session_id: str, event_type: str, payload: dict) -> dict  # returns envelope
async def mark_assistant_ready(session_id: str) -> None     # Manav's voice worker, once the AI is in the room and hears the caller
async def mark_wearer_audio_blocked(session_id: str) -> None  # also reachable via signals endpoint from wearer client
async def mark_family_joined(session_id: str, participant: dict) -> None  # Manav, on the REAL provider participant-joined event
async def fail_takeover(session_id: str, reason: str) -> None
def get_session(session_id: str) -> Session
```
- `takeover.active` is published exactly once, only when BOTH wearer_audio_blocked and assistant_ready are true while state == protecting -> transition assistant_active.
- `fail_takeover`: only while state == protecting and status == starting; status=failed, publish `takeover.failed {reason}` once. State stays `protecting` (wearer stays disconnected, alert stays visible, UI offers End call). Late ready signals after failure are ignored.
- `mark_family_joined`: from assistant_active (or protecting) -> family_joined; app then `await calls.stop_assistant(session_id)`; publish `family.joined {participant}`. Duplicates are no-ops.
- `wearer_reconnect` signal: state family_joined -> wearer_connected=True, publish `wearer.reconnected`.
- end: transition ended, `await calls.end_call(session_id)` (if available), publish `session.ended`, close WS subscribers.

## Interfaces app.py calls (other owners implement)
```python
# backend/intelligence/__init__.py   (Pratham)
async def analyze_transcript(session_id: str, utterances: list[dict]) -> dict  # risk result per contracts.json
# backend/calls/__init__.py          (Manav)
async def create_join_credentials(session_id: str, role: str) -> dict
async def start_takeover(session_id: str, decision: dict) -> dict
async def stop_assistant(session_id: str) -> None
async def end_call(session_id: str) -> None
```
`app.py` imports these lazily inside a try/except ImportError. Missing module => the dependent endpoint returns 501
(join) or publishes `error` + `takeover.failed {reason: "calls module unavailable"}` (takeover). It never fakes success.

## Demo mode
`DEMO_MODE=true` only allows the presenter to replay fixtures through the normal transcripts endpoint.
Every event published while DEMO_MODE is true carries `payload.demo_replay = true` so UIs label it "Demo replay".
