# Tripwire build status

Live checklist for every owner and their coding agents.

**Agents: read this first.**
1. `git pull --rebase` before you edit anything.
2. Edit only your own section. Tick `[x]` only when the item is verified, and put the proof next to it: the command you ran and its result.
3. Commit this file on its own with the message `status: <name> <what>`, then push.
4. Contract to build against: `shared/COORDINATOR.md` (plain-language spec) and `shared/contracts.json` (machine-readable). If you need a contract change, ask Ayush; don't edit those files yourself.
5. Blocked? Add a line under **Blockers**: who, what is missing, and since when.

Required flow: suspicious call → detection → AI takeover → family alert → daughter joins → reset.

## Blockers
- 2026-11-14 · **All provider keys missing.** Naman has no `.env` yet, so Daily, Deepgram, Gemini and ElevenLabs are all BLOCKED (`docs/setup.md` §6). Owner: Naman.

## Ayush: coordinator, shared contracts, demo, integration
- [x] `.gitignore` (keeps `.env` out of git)
- [x] `shared/COORDINATOR.md`, `shared/contracts.json`, `shared/example_event.json`, `shared/example_risk.json`
- [x] `backend/session.py`: state machine, event sequence, role tokens, idempotent takeover hooks. Proof: `.venv/bin/pytest -q backend/tests/test_session.py` → 27 passed
- [x] `backend/requirements.txt`, `Makefile`, `README.md`
- [x] `demo/script.md`, `demo/checklist.md`, `demo/smoke.py` (syntax-checked only so far)
- [ ] `backend/app.py`: HTTP and WebSocket routes, transcript → analyzer → takeover wiring. In progress.
- [ ] `make smoke` passes against a live backend (needs Pratham's analyzer)
- [ ] Merge all modules; full scenario works 3 times in a row
- [ ] 90 s video plus one uncut proof recording

## Manav: calls, audio routing, voice worker
Implement in `backend/calls/__init__.py`. The coordinator imports these:
```python
async def create_join_credentials(session_id: str, role: str) -> dict
async def start_takeover(session_id: str, decision: dict) -> dict
async def stop_assistant(session_id: str) -> None
async def end_call(session_id: str) -> None
```
Call back into the coordinator with:
- `backend.session.mark_assistant_ready(session_id)` once the AI is in the room and can hear the caller
- `backend.app.on_family_joined(session_id, participant)` on the **real** Daily participant-joined event
- `backend.session.fail_takeover(session_id, reason)` on any failure

The wearer client sends `POST /api/sessions/{id}/signals {"signal": "wearer_audio_blocked"}` only after it has actually stopped playing caller audio.
- [ ] Daily room plus join credentials per role
- [ ] Selective routing proven: wearer can't hear caller; caller and AI still hear each other (**main feasibility gate**)
- [ ] Voice worker speaks the Tripwire line plus one short reply
- [ ] Daughter join stops the assistant
- [ ] `frontend/components/call/` reusable call components for Dev

## Pratham: intelligence
Implement in `backend/intelligence/__init__.py`:
```python
async def analyze_transcript(session_id: str, utterances: list[dict]) -> dict  # risk_result in shared/contracts.json
```
The coordinator rejects any decision where an evidence quote is not a substring of the utterance it references.
- [x] Analyzer returns valid `risk_result` (low/review/high; none/alert/takeover). Every quote is a verbatim substring of the posted text. Proof: `python -m pytest backend/intelligence -q` → 93 passed (branch `pratham/intelligence`)
- [x] `fixtures/`: benign, ambiguous $2,000, gift-card scam, plus ambient mechanic, fake bank, duplicates, and assistant/family excluded
- [x] Benign → low; price alone → review at most; scam → high + takeover with quotes. Proof: `python -m backend.intelligence.replay fixtures --check` → 7/7 PASS
- [ ] Gemini layer verified live. It is mocked in tests and falls back to rules-only when keys are missing. Blocked on Naman's `GEMINI_API_KEY` and `GEMINI_MODEL`.
- Handoff notes for Ayush (reason codes extend the contract list; dedupe on state, not `decision_id`): `backend/intelligence/README.md`

## Naman: keys, providers, wearable
- [x] `.env.example`, `docs/setup.md`, provider check scripts, audio adapter with laptop-mic fallback (38 tests pass)
- [ ] Real keys for Daily, Deepgram, Gemini (plus a model id), ElevenLabs (plus a voice id), shared privately
- [ ] `python -m backend.audio.provider_checks.run_all` all PASS
- [ ] Wearable streaming works, or the fallback is documented

## Dev: frontend pages
Run: `cd frontend && npm install && npm run dev` (http://localhost:3000). Env: `NEXT_PUBLIC_BACKEND_URL`. Details: `frontend/README.md`.
- [x] Next.js app in `frontend/`: wearer, caller, family, presenter pages + launcher. Proof: `npm run build` → compiled, 7 routes; `npm test` → 10 passed
- [x] Render events from fixtures before the backend is live. Proof: `/presenter?replay=scam&autoplay=1` drives all open tabs (headless Chrome, no page errors)
- [x] Use `GET /api/sessions/{id}` snapshot, then `WS /ws/sessions/{id}?token=`. Proof: against a contract mock: per-role tokens, `X-Session-Token`, 403 → Offline, WS drop → snapshot + reconnect, 410/`session.ended` → closed, `takeover.failed` shown honestly
- [x] Show the "Demo replay" label when `payload.demo_replay` is true. Proof: reducer test "payload.demo_replay marks the view as demo replay"
- [ ] Not yet verified against the real `backend/app.py` (not on main yet)
- [ ] Mount Manav's `CallRoom` in `components/ui/CallSurface.tsx` once his branch merges. Trial merge of `manav/call-transport-takeover` builds; `@daily-co/daily-js@0.95.0` already added to `frontend/package.json`. Note: that branch conflicts with main on root `.gitignore`
