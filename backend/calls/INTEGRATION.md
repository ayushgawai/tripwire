# Ayush / Dev integration points (Manav call module)

Manav owns `backend/calls/` and `frontend/components/call/`. Session HTTP/WebSocket routes remain Ayush (`backend/app.py`, `backend/session.py`). Pages remain Dev (`frontend/app/`).

## Wire CallSessionManager (Ayush)

```python
from backend.calls.session_manager import CallSessionManager
from backend.calls.models import ParticipantRole, RoutingConfirmation

calls = CallSessionManager()

# After POST /api/sessions creates session_id:
await calls.attach_session(session_id)
invites = calls.get_invite_tokens(session_id)  # hand out via secure demo links

# POST /api/sessions/{id}/join  body: {role, access_token}
return await calls.join(session_id, role=ParticipantRole(role), access_token=access_token)

# POST /api/sessions/{id}/routing-confirmation  (wearer client after selective audio)
await calls.confirm_routing(session_id, RoutingConfirmation(**body))

# After high-risk decision recommends takeover:
await calls.start_takeover(session_id, decision_id=decision_id, risk="high", recommended_action="takeover")
await calls.start_voice_worker(session_id)  # can run in parallel with waiting for routing

# POST /api/sessions/{id}/provider-join  — actual Daily/mock join
await calls.confirm_provider_join(...)

# POST /api/sessions/{id}/family-joined  — only after provider participant-joined
await calls.confirm_family_joined(...)

# POST /api/sessions/{id}/reconnect-wearer
await calls.reconnect_wearer(session_id, access_token=...)

# POST /api/sessions/{id}/end
await calls.end_session(session_id)

# Replace InMemoryEventPublisher with WebSocket fan-out that assigns event_id/sequence.
```

## Proposed routes (not owned by Manav — adapters expect these)

| Route | Purpose |
| --- | --- |
| `POST /api/sessions/{id}/routing-confirmation` | Wearer proves selective routing applied |
| `POST /api/sessions/{id}/provider-join` | Client reports provider participant id |
| `POST /api/sessions/{id}/family-joined` | Family provider-join confirmation |
| `POST /api/sessions/{id}/reconnect-wearer` | Explicit wearer audio restore |

Plan routes already covered: create/get/join/takeover/end + `WS /ws/sessions/{id}`.

## Dev import

```tsx
import { CallRoom, useCallSession } from "@/components/call";
```

Pass `accessToken` from session invite; never put `DAILY_API_KEY` in `NEXT_PUBLIC_*`.
