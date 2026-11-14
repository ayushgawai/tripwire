# Tripwire frontend (Dev)

Next.js 15 App Router. Owner: **Dev** — `frontend/app/`, `frontend/components/ui/`.

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm test               # reducer unit tests (node --test, no extra deps)
npm run build          # production build + typecheck
```

`NEXT_PUBLIC_BACKEND_URL` (default `http://localhost:8000`) points at the FastAPI backend.

## Pages

| Route | Who | Shows |
| --- | --- | --- |
| `/` | Operator | Start a live session (POST `/api/sessions`) or open Demo replay; role links + "open all four" |
| `/presenter` | Big screen / video | State timeline, live transcript with highlighted evidence, risk meter + reasons, audio routing diagram, family status, verbatim quotes, raw event stream |
| `/wearer` | Protected person | Large plain-language scenes per state. Never shows the caller's words during protection. Takeover failure → "Please hang up" + End call |
| `/caller` | Caller actor | Ordinary call screen; discloses "You are speaking with an AI assistant" when the assistant is active |
| `/family` | Daughter | Alert with summary, reason chips, exact quotes (verified verbatim against transcript), Join → waits for the real `family.joined` event, then "Reconnect wearer" |

Every role page takes `?session=<id>&token=<invite secret>`. Optional: `family=<name>` on wearer, `wearer=<name>` on family, `callee=<name>` on caller.

## Demo replay (fixtures)

`/presenter?replay=1` → pick a scenario → **Run replay**. Every other tab opened with `?replay=1` follows along (BroadcastChannel). `/presenter?replay=scam&autoplay=1` starts automatically.
Scenarios: `scam`, `benign`, `ambiguous` (`app/_lib/fixtures.ts`), matching "Checks before recording".
Every replay page shows a **Demo replay · fixture events · not live inference** ribbon. Never present replay as live.

## How state works

- `app/_lib/reducer.ts` — pure reducer from the contract event envelopes. Dedupes by `event_id`, drops stale `sequence`, ignores other sessions, `ended` is terminal. UI state changes **only** from backend events; buttons never imply success.
- `app/_lib/useSession.ts` — live mode: GET snapshot → WS `/ws/sessions/{id}?token=` → on drop, re-fetch snapshot first, then reconnect with backoff. 401/403/404 → Offline (no retry storm).
- `app/_lib/api.ts` — REST client. Sends token as `Authorization: Bearer` and `X-Session-Token`.

## Integration notes for teammates

- **Ayush (contracts / backend):** `app/_lib/types.ts` mirrors the plan's contracts. Snapshot parsing is tolerant; it reads `state, transcript, latest_decision, alert, last_sequence`, plus optional `mode, takeover_status, takeover_error, family_joined, wearer_reconnected`. `POST /api/sessions` may return `token` (or `invite`) — the launcher puts it in the role links.
  - **Proposed additions (not in the frozen contract yet):** `POST /api/sessions/{id}/reconnect-wearer` and event `wearer.reconnected` for the daughter's explicit "Reconnect wearer". Until it exists, the button shows the backend error.
  - `risk.updated` payload may be the decision itself or `{decision: {...}}`. `family.alert` payload: `{decision_id, summary, reasons, evidence}`. `takeover.failed`: `{reason}`. `error`: `{message}`. Any event payload may include an authoritative `state`.
- **Manav (call components):** `components/ui/CallSurface.tsx` is the mount point. Replace the marked block with your `<CallPanel role credentials state />` from `frontend/components/call/`. Credentials come from `POST /join` via `actions.join(role)`. The wearer's "caller audio paused" indicator only turns on after `takeover.active`.
- **Pratham:** reason codes get friendly labels in `app/_lib/labels.ts` (unknown codes are prettified automatically). Evidence quotes are rendered as "Verbatim" only if found in the referenced utterance.
- Assistant utterances (`speaker: "assistant"`) are labeled "AI · excluded from detection".
