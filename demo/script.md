# Tripwire demo — 90-second recording run-of-show

Source of truth: `Tripwire_Quick_Build_Plan.md` ("Demo: 90 seconds, mostly real product") and
`shared/COORDINATOR.md` (state machine, event names, demo-mode labelling). Everything in this
document must still be true after the final build; if a beat can't be shown live, apply the
labelling rules in §5 — never manufacture footage that looks like a working integration.

## 1. Crew, laptops, pages

| Role | Person | Laptop | Browser page | Notes |
| --- | --- | --- | --- | --- |
| Presenter / director | Ayush | P | Presenter dashboard (state machine, live event feed, evidence quotes, End call, replay control) | Also runs `demo/checklist.md` and `demo/smoke.py` before each take; keeps the family-page view on a second window |
| Wearer ("Grandma") | consented teammate | W | Wearer call page | Wears the band only if the live input is proven; otherwise laptop mic with on-screen "Audio input: laptop mic" badge |
| Caller | consented teammate | C | Caller call page | Plays the family-scammer; fictional details only, no real names/numbers |
| Daughter | consented teammate | D | Family page (alert banner + Join button) | Jaws the Join beat |

Headphones: **all four machines use wired headphones**, no speakers — the mute transition is
audible only through the wearer's headphones, and speaker audio would echo into mics and break
the AI turn. The caller's voice must be inaudible on W the moment the takeover engages.

## 2. Audio: three separate tracks (+ narration VO in post)

Record each laptop locally (OBS or screen recorder) and sync in post on a shared clap/clap at
second 0 of every take.

| Track | Source | What it must contain |
| --- | --- | --- |
| T1 — screen | Laptop P screen capture (+ P system audio for UI event pings, if any) | Presenter dashboard throughout; event feed visible at beats 4–7 |
| T2 — wearer audio | Laptop W **output** (what the headphones play) | Caller's voice up to takeover, then **caller goes silent** (the T-mute moment, ~36–40 s), then AI voice; wearer's own lines via W mic. This is the proof track for the mute |
| T3 — caller audio | Laptop C output/mic | Caller's lines, AI replies live, daughter's voice when she joins |
| T4 — narration VO | recorded separately in post | The two narration beats (§4, B2 and B7) and the open |

## 3. Pre-roll (before every take)

1. `demo/checklist.md` all green; `demo/smoke.py` PASS against the running backend.
2. End the previous session (`POST /end` → `session.ended`); start a **fresh** session with
   `protection_enabled: true`, state `monitoring`.
3. `DEMO_MODE=false` for live takes (events without `demo_replay`). Fixture replay is only for
   development and must be labelled "Demo replay" (see §5).
4. Everyone on headphones; confirm on T2 that the caller's voice is audible on the wearer side
   before the take starts.
5. **Three-take rule:** record **three successful takes** before cutting. Keep **one full uncut
   successful recording as the proof take** (no edits); cut the 90-second submission from that
   take.

## 4. Shot list (90 s)

T = track. "Lines" are exact — do not improvise the scam/AI/daughter dialogue.

| # | Time | Picture / page | UI state that must be visible | Exact lines | Audio notes |
| --- | --- | --- | --- | --- | --- |
| B1 | 0–8 s | **[Illustration]** generated closeup, slow zoom | — (no product UI) | Narration VO: "A convincing voice. An urgent request. Someone you love, alone with the decision." | T4 only |
| B2 | 8–16 s | Wearer page (W), presenter feed (P) | Wearer enables protection; session state `monitoring`, `wearer_connected=true` | Narration VO: "Tripwire brings a trusted person into the moment before a risky decision." | T1, T4 |
| B3 | 16–32 s | Live browser call, transcript streaming (C + W + P event feed) | State `monitoring`; `transcript.final` events appearing | Caller: "Grandma, I am in trouble. Buy $500 in gift cards now. Please do not tell anyone." / Wearer: "Should I call your mother?" / Caller: "No. There is no time." | T2+T3: caller and wearer audible to each other |
| B4 | 32–46 s | Wearer page + presenter dashboard | Evidence highlighted with quotes; state `monitoring → protecting` (`takeover.started`), then `assistant_active` (`takeover.active`); wearer warning card | Wearer UI warning (on screen, not spoken): "This request may be unsafe. We are asking your trusted contact to help." | **T-mute on T2**: caller audio disappears from wearer output; AI voice arrives |
| B5 | 46–58 s | Caller page + presenter feed | State `assistant_active`; assistant transcript visible | AI: "I am Tripwire, an AI assistant. This conversation has been paused for family verification. Please explain your request." / Caller: "It has to happen now." / AI: "A family member will verify the request before anyone acts." | T3: AI live reply audible on caller side |
| B6 | 58–73 s | Daughter's family page (D) | `family.alert` banner with the quoted evidence; Join button pressed → `family.joined`, state `family_joined`, "Joined" status from the real call event | Daughter: "Mom, pause. I will call him on the number we already know." | T3: daughter joins; AI stops speaking |
| B7 | 73–84 s | Presenter dashboard (P) | State `family_joined`; supporting quotes; family in control | Narration VO: "Tripwire detects concerning patterns, pauses the call, and connects family." | T1, T4 |
| B8 | 84–90 s | **[Illustration]** title card | "Tripwire. A pause when it matters." + small caption "Prototype. Calls through our app." | — | T4 |

Optional 10 s extension only if ambient mode actually works: mechanic says "The oil change is
$2,000. Pay now and do not call your daughter." Show an alert naming pressure and secrecy as
evidence. Do not claim the price alone proves fraud or that the watch silences the mechanic.

## 5. Labelling rules (non-negotiable)

- **Illustration**: any AI-generated visual (B1, B8) carries an on-screen "Illustration" badge.
- **Demo replay**: any fixture replay (`DEMO_MODE=true`) carries an on-screen "Demo replay"
  badge — the backend stamps `payload.demo_replay = true` on every event in demo mode, and the
  presenter UI labels from that flag.
- Never describe a replayed decision as live inference.
- If live APIs fail mid-presentation: play the recorded successful run and say out loud that
  it is a recording.
- No footage that appears to prove an integration that was not actually working.

## 6. Generated-visual prompt

> "Realistic cinematic closeup of an older adult's hand resting next to a smartphone on a warm
> kitchen table, incoming call glow, subtle concern, natural lighting, restrained documentary
> tone, no text, no brand logos, horizontal 16:9."

Use a short still with a slow zoom if video generation would take too long. Same prompt family
for the closing title card background (badge "Illustration").

## 7. If a beat breaks during the recording

- `takeover.failed` → state stays `protecting`; UI offers End call. Do not fake success — end
  the session and restart a fresh take.
- `error` event from intelligence/voice → same: end, note it, restart.
- Repeat the full demo three times (checklist item 8) after any fix before re-recording takes.
