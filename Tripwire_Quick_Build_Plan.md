# Tripwire: Quick Build Plan

## Read this first

Build one convincing flow: suspicious call → detection → AI takeover → family alert → daughter joins. The demo is the product for this hackathon. Finish that flow before adding anything else.

This plan is based on the supplied Imprint Demo Idea conversation. It is an implementation proposal, not a claim that hardware capabilities or provider integrations have been tested. Naman and the module owners must confirm access and SDK behavior immediately.

Give this document to your coding agent and say: “I am [Ayush / Manav / Pratham / Naman / Dev]. Build only my assigned module. Follow the shared contracts. Tell me any integration blocker immediately.”

## Product and scope

Tripwire helps a wearer pause a suspicious conversation and bring in someone they trust. Monitoring and automatic protection are enabled explicitly before the demo. The caller, wearer, and daughter use our browser calling app. We do not claim control over normal cellular calls.

During a suspicious call, the app stops playing the caller to the wearer. An identified AI assistant speaks to the caller while the wearer receives a warning. The daughter receives an alert containing the actual concerning statements and joins to help.

Required: live browser call, live transcription, evidence based risk decision, real audio takeover, family alert, daughter joining, reset for another demo.

Optional only after the required flow works: one ambient conversation using the wearable microphone. It can trigger an alert but cannot mute a person standing nearby.

Excluded: Stripe, payments, medication management, automatic 911 calls, arbitrary cellular interception, native mobile apps, user accounts, databases, and background monitoring outside an enabled session. Do not spend time on a hardware red light; use the app warning indicator unless LED control is already proven.

## Smallest architecture

Use one repository, one Next.js frontend, and one Python FastAPI backend. Keep session state in memory. Use a backend WebSocket for updates. Daily handles the browser call; the Python voice worker uses Pipecat if the team can quickly prove that integration. Deepgram handles transcription, Gemini handles risk and short dialogue, and ElevenLabs handles speech. All of these are planned integrations requiring a working smoke test.

Use an available Gemini model through an environment variable. The earlier phrase “Gemini Decision 1” is not a verified model identifier. Do not put that string into code without checking the actual provider offering.

The voice worker may run as a separate process in the same repository. Avoid additional services unless the provider SDK requires them. First prove the browser flow with laptop microphones, then connect the wearable as an interchangeable audio input.

## Ownership

| Person | Owns | Files / folders | Finished when |
| --- | --- | --- | --- |
| Ayush | Integration, backend session coordinator, demo planning, video, final fixes | backend/app.py, backend/session.py, shared/, demo/, root configuration | Complete scenario works repeatedly and video is recorded |
| Manav | Call transport, audio routing, voice worker, takeover, daughter joining | backend/calls/, frontend/components/call/ | Caller becomes inaudible to wearer while AI and daughter can still communicate correctly |
| Pratham | Transcript normalization, risk detector, evidence and intervention text | backend/intelligence/, fixtures/ | Live finalized transcript produces valid risk decisions with quoted evidence |
| Naman | All API keys, provider access, wearable audio adapter, setup instructions | backend/audio/, docs/setup.md, .env.example | Every required credential is tested and wearable input either works or has a clearly documented fallback |
| Dev | Wearer, caller, family, and presenter pages | frontend/app/, frontend/components/ui/ | Pages render live events, clear warnings, evidence, and join status |

Manav owns the reusable call components; Dev imports them rather than rebuilding call controls. Ayush owns shared schemas and dependency files. Other owners request shared changes before editing them.

Naman's first priority is unblocking everyone with keys and tested access. Wearable work comes second. Each person implements their provider adapter and reports the exact missing permission or credential to Naman.

## Naman: first actions

1. Gather Daily, Deepgram, Gemini, and ElevenLabs credentials and confirm credits, model access, and voice availability.
2. Share secrets through a private team channel or secret manager. Commit only empty placeholders in .env.example. Never place keys in frontend bundles, screenshots, prompts, or logs.
3. Ask each module owner to run one tiny request with the supplied credentials. Record pass/fail and the responsible owner in docs/setup.md.
4. Confirm how the actual Vexo hardware exposes microphone audio with the supplied SDK. Record format, sample rate, connection procedure, and whether streaming works on the team's machine.
5. If wearable streaming blocks progress, deliver a laptop microphone adapter with the same interface, label it honestly, and keep investigating the band separately.

Environment variable names are our own configuration contract:

```dotenv
DAILY_API_KEY=
DEEPGRAM_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
DEMO_MODE=false
```

## Shared contracts: freeze before parallel coding

Ayush commits shared/contracts.json and one example event immediately. These are application contracts, not provider API endpoints. All dates use UTC ISO strings. IDs are opaque strings. Every event has a unique event_id and a monotonically increasing sequence within its session.

```json
{
  "event_id": "evt_001",
  "session_id": "demo_001",
  "sequence": 1,
  "type": "transcript.final",
  "timestamp": "2026-11-14T20:00:00Z",
  "payload": {
    "utterance_id": "utt_001",
    "speaker": "caller",
    "text": "Buy gift cards now and do not tell your daughter."
  }
}
```

Allowed speakers: caller, wearer, family, assistant, ambient. Analyze caller and wearer final transcripts in call mode. Exclude assistant speech from risk detection. In ambient mode use speaker=ambient unless speaker identity is actually known.

| Endpoint | Request | Response / behavior |
| --- | --- | --- |
| POST /api/sessions | {mode: call or ambient, protection_enabled: true} | {session_id, state: monitoring} |
| GET /api/sessions/{id} | None | Current state, transcript, latest decision, alert, last_sequence |
| POST /api/sessions/{id}/join | {role: caller, wearer, or family} | Short lived room credentials for this role |
| POST /api/sessions/{id}/transcripts | {utterance_id, speaker, text, timestamp} | {accepted: true}; duplicate IDs ignored |
| POST /api/sessions/{id}/takeover | {decision_id} | {accepted: true}; begins transition, does not imply success |
| POST /api/sessions/{id}/end | {} | Ends call and worker, invalidates further session activity |
| WS /ws/sessions/{id} | Connect | Event envelopes; reconnecting clients fetch the snapshot first |

Use an invite secret or scoped session token for session access. A role string alone must not grant access to a stranger's session. For this controlled demo, no account system is needed. Only the backend can create provider credentials, request takeover, or confirm state changes. Provider credentials remain server side except short lived client tokens.

Module interfaces:

```python
async def analyze_transcript(session_id: str, utterances: list[dict]) -> dict: ...
async def start_takeover(session_id: str, decision: dict) -> dict: ...
async def stop_assistant(session_id: str) -> None: ...
async def publish_event(session_id: str, event_type: str, payload: dict) -> None: ...
```

Risk result:

```json
{
  "decision_id": "decision_001",
  "risk": "high",
  "reasons": ["gift_card_request", "urgency", "secrecy"],
  "evidence": [
    {"utterance_id": "utt_001", "quote": "Buy gift cards now and do not tell your daughter."}
  ],
  "summary": "The caller demands gift cards urgently and discourages family verification.",
  "recommended_action": "takeover"
}
```

Allowed risk values: low, review, high. Allowed actions: none, alert, takeover. Validate JSON and verify every evidence quote occurs in its referenced utterance. A large price alone is review, not proof of a scam. High risk should require multiple supporting indicators. The threshold is a demo policy requiring evaluation, not a validated fraud classifier.

Events: transcript.final, risk.updated, takeover.started, takeover.active, takeover.failed, family.alert, family.joined, session.ended, error. Dev builds against local fixtures immediately while the live services are being connected.

## Call takeover: the critical implementation

State sequence: monitoring → protecting → assistant_active → family_joined → ended. A low or review result leaves the call in monitoring. Backend rejects illegal transitions. Duplicate high risk decisions must not start additional agents or alerts.

Manav must prove selective audio routing early using the provider's current SDK. Do not globally mute the caller, because the AI must still hear them. The wearer stops subscribing to or playing caller audio. The wearer microphone is paused toward the caller during protection. The AI hears the caller and sends its responses to the caller. The wearer gets a separate warning that does not leak into the conversation. Use headphones in testing to prevent acoustic echo.

After a high risk decision, the backend enters protecting and issues the routing command. Publish takeover.active only after the wearer client confirms caller audio is blocked and the assistant is ready. If this fails, publish takeover.failed, show the alert, and offer End call. Never show a successful takeover based only on clicking a button.

When the daughter joins, verify the actual participant join event, stop assistant speech, and bring her into the conversation. Keep the wearer protected until the daughter deliberately selects “Reconnect wearer.” A single call room with selective subscriptions is the first approach; check SDK support before committing to it.

The AI says: “I am Tripwire, an AI assistant. This conversation has been paused for family verification. Please explain your request.” Allow one short live response to the caller. It must not impersonate the wearer, reveal private details, promise payment, or negotiate a transaction. Stop immediately when family takes control.

## Build order and checkpoints

These are timeboxes, not estimates of guaranteed completion. If time is shorter, reduce polish, not the required takeover flow.

| Timebox | Everyone's checkpoint |
| --- | --- |
| First 15 minutes | Ayush creates skeleton and contracts; Naman checks access; everyone claims folders |
| Next 30 minutes | Manav proves call and selective audio; Pratham analyzes a fixture; Dev renders fixture events |
| Next 45 minutes | Connect live audio, final transcript, detector, and automatic family alert |
| Next 45 minutes | Prove real takeover and daughter join end to end; attach wearable if ready |
| Remaining time | Freeze features, fix failures, record three successful takes, edit video |

Escalate selective audio failure immediately. It is the main feasibility gate. A different color on a dashboard is not takeover. If provider access prevents completion, report the blocker explicitly rather than disguising a simulated flow as live.

Each owner sends Ayush: branch name, touched files, run command, environment variables, one successful test, and known limitations. Use one branch per person and merge small working increments. Agents may use parallel helpers only within their owner's scope and only when their environment permits it. No agent should implement another person's module without coordination.

## Demo: 90 seconds, mostly real product

Use AI generated visuals for the opening and closing only. Record the core product live. Label generated scenes “Illustration.” Do not manufacture footage that appears to prove a working integration.

| Time | Picture | Spoken line / action |
| --- | --- | --- |
| 0–8 seconds | Generated closeup of an older adult's hand beside a ringing phone | Narration: “A convincing voice. An urgent request. Someone you love, alone with the decision.” |
| 8–16 seconds | Real wearer enables protection; show band only if connected | “Tripwire brings a trusted person into the moment before a risky decision.” |
| 16–32 seconds | Live browser call and transcript | Caller: “Grandma, I am in trouble. Buy $500 in gift cards now. Please do not tell anyone.” Wearer: “Should I call your mother?” Caller: “No. There is no time.” |
| 32–46 seconds | Evidence highlighted; state changes to protecting then assistant active | Wearer warning: “This request may be unsafe. We are asking your trusted contact to help.” Caller audio disappears from wearer output. |
| 46–58 seconds | Caller hears AI; show real live reply | AI: “I am Tripwire, an AI assistant. This conversation has been paused for family verification. Please explain your request.” Caller: “It has to happen now.” AI: “A family member will verify the request before anyone acts.” |
| 58–73 seconds | Daughter's open family page gets alert; she presses Join | Daughter: “Mom, pause. I will call him on the number we already know.” Show joined status from real call event. |
| 73–84 seconds | Real dashboard shows supporting quotes and family in control | Narration: “Tripwire detects concerning patterns, pauses the call, and connects family.” |
| 84–90 seconds | Simple title card | “Tripwire. A pause when it matters.” Small caption: “Prototype. Calls through our app.” |

Optional 10 second extension only if ambient mode works: mechanic says “The oil change is $2,000. Pay now and do not call your daughter.” Show an alert with pressure and secrecy as evidence. Do not claim the price alone proves fraud or that the watch silences the mechanic.

Generated visual prompt: “Realistic cinematic closeup of an older adult's hand resting next to a smartphone on a warm kitchen table, incoming call glow, subtle concern, natural lighting, restrained documentary tone, no text, no brand logos, horizontal 16:9.” Use a short still with a slow zoom if video generation would take too long.

Ayush records the screen, wearer audio, and caller audio separately so the mute transition is audible. Use consented teammate actors and fictional details. Keep one full uncut successful recording as evidence; edit the short submission from that take.

## Checks before recording

1. Benign call: “Please call me back tomorrow.” No takeover.
2. Ambiguous charge: “The service costs $2,000.” Review at most without additional indicators.
3. Scam script: gift cards plus urgency plus secrecy triggers evidence, one takeover, and one family alert.
4. Wearer genuinely cannot hear caller after takeover; caller and AI can still hear each other.
5. Daughter receives alert and joins; AI stops speaking; wearer reconnects only on explicit action.
6. Duplicate transcripts or decisions do not repeat takeover. Refreshing the family page recovers current state.
7. Model or voice failure is visible and offers a safe end call action. Do not silently claim protection succeeded.
8. End session shuts down audio capture and worker. New session starts cleanly. Repeat the complete demo three times.

If live APIs fail during presentation, use the recorded successful run and say it is a recording. Fixture replay is acceptable for development and must be visibly labeled “Demo replay.” Never describe replayed decisions as live inference.

## Definition of done

A teammate can follow setup instructions, start the app, complete the live scam call with actual audio takeover and family joining, reset it, and repeat it. Ayush has the 90 second video, an uncut proof recording, and a short list of verified capabilities and remaining limitations. Stop adding features once these are complete.
