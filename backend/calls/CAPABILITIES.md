# Call transport — verified provider capabilities

Owner: Manav (`backend/calls/`, `frontend/components/call/`).
Verified against official Daily docs and package indexes on 2026-11-14.
Do not treat tutorial blogs as source of truth.

## Package versions (verified)

| Package | Version checked | Role |
| --- | --- | --- |
| `@daily-co/daily-js` | `0.95.0` (npm latest) | Browser call object |
| `@daily-co/daily-react` | `0.26.1` (npm latest) | Optional React helpers (UI may stay provider-neutral) |
| `pipecat-ai` | `1.16.0` (PyPI latest) | Voice worker pipeline |
| `daily-python` | `0.38.0` (PyPI latest) | Server-side Daily room participation for bots |

## Selective audio routing — GENUINELY SUPPORTED

Daily supports **receive-side selective subscription** without globally muting the caller:

1. Create the call with `subscribeToTracksAutomatically: false`.
2. Wearer applies `call.updateParticipant(callerSessionId, { setSubscribedTracks: { audio: false } })`.
3. Caller continues publishing audio. Other participants (AI bot) can still subscribe to caller audio.
4. Do **not** use `updateReceiveSettings` for audio — that API is video/simulcast layers only.

Wearer microphone toward the caller during protection:

- Primary (client-confirmed): wearer calls `setLocalAudio(false)` so the mic track stops sending.
- This also stops the AI from hearing the wearer. That matches the product: during takeover the AI hears the **caller** and speaks to the caller; the wearer is protected, not conversing.
- Do **not** remotely mute the caller (`updateParticipant(..., { setAudio: false })`) — that would silence the caller for everyone, including the AI.

Optional hardening (admin permissions): `canReceive.byUserId` / `byParticipantId` can deny wearer receive of caller audio. Prefer client unsubscribe + confirmation event first; permissions are a belt-and-suspenders option when an admin token is available.

## Takeover confirmation contract (client → backend)

After the wearer applies routing, the wearer client MUST POST/send a confirmation with:

```json
{
  "session_id": "...",
  "caller_audio_blocked": true,
  "wearer_microphone_paused": true,
  "timestamp": "2026-11-14T20:00:00Z"
}
```

Backend waits for this confirmation **and** voice-worker readiness before publishing `takeover.active`. Visual mute indicators alone are not proof.

## Meeting tokens

- Always set `room_name` and `exp` (unix seconds). Tokens without `room_name` work on every room — forbidden.
- Scope with `user_id` encoding role + session (validated server-side; never trust role alone).
- Keep `DAILY_API_KEY` server-side only. Clients receive short-lived meeting tokens only.

## Participant join (family)

Confirm family with Daily `participant-joined` where `participant.user_id` matches the scoped family credential for **this** session. Token issuance alone must never publish `family.joined`.

## Voice worker

- Real path: Pipecat `DailyTransport` joins the same room with a bot token, hears caller, speaks assistant line.
- If `DAILY_API_KEY` / TTS / LLM credentials are missing: use **MockVoiceWorker** (clearly labeled). Never claim live AI success in mock mode.

## Plan vs verified behavior

| Plan wording | Verified behavior |
| --- | --- |
| “pause wearer microphone toward the caller” | Daily has no per-destination send graph in the browser SDK. Pausing local mic (`setLocalAudio(false)`) is the verified approach; AI does not need wearer audio during takeover. |
| “do not globally mute the caller” | Correct — use wearer unsubscribe, not caller mute. |
| “single call room with selective subscriptions” | Supported via `setSubscribedTracks` when auto-subscribe is off (SFU). |

## Fixture / demo mode

When live Daily credentials are unavailable, `MockCallProvider` + `MockVoiceWorker` drive the same state machine and events. UI must show **Local Fixture** / **Demo Replay**. Never silently present fixture success as live provider success.
