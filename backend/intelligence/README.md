# backend/intelligence (owner: Pratham)

Transcript normalization, risk detection with quoted evidence, and intervention text.
Scope: `backend/intelligence/` and `fixtures/` only. Depends on `httpx`. Everything else is standard library.

## Interface

```python
from backend.intelligence import (
    analyze_transcript,   # async (session_id, utterances: list[dict]) -> decision dict (contract "Risk result")
    normalize_utterance,  # (payload) -> {utterance_id, speaker, text, timestamp}; raises ValueError
    validate_decision,    # (decision, utterances) -> list[str] of contract violations
    wearer_warning,       # (decision) -> private warning text for the wearer
    family_alert,         # (decision) -> {title, message, evidence}
    ASSISTANT_OPENING,    # the fixed "I am Tripwire, an AI assistant..." line
    assistant_reply,      # async (caller_text) -> one short, guardrailed reply; never raises
    ASSISTANT_FALLBACK,   # "A family member will verify the request before anyone acts."
)
```

### Integration notes

- **Backend (Ayush):** store transcripts exactly as posted. Every evidence quote is a verbatim slice of that
  text, so the coordinator's `quote in utterance["text"]` check passes. Matching runs on a folded copy that
  ignores curly quotes and spacing. `analyze_transcript` is stateless and safe to call on every utterance. It
  filters out assistant and family speech itself, so passing either the analyzable subset or the full transcript
  works.
- Reason codes extend `shared/contracts.json`, which lists `gift_card_request, urgency, secrecy, impersonation,
  threat, financial_pressure`. The four shared codes match exactly. `financial_pressure` is split into the more
  specific `payment_request`, `credential_request`, `remote_access_request` and `large_amount`. The coordinator
  passes `reasons` through unchanged. Ayush may want to add the extra codes to the contract so Dev can label them.
- `decision_id` is derived from the decision's content. Re-analyzing an unchanged transcript returns the same ID.
  New evidence returns a new ID, so takeover and alert dedupe must key on session state (already `protecting`),
  not on `decision_id`.
- `recommended_action` is `takeover` for high risk in a call and `alert` when all evidence is ambient speech,
  because a person in the room cannot be muted. `low` and `review` both return `none`, which keeps the call in
  `monitoring`.
- **Voice worker (Manav):** speak `ASSISTANT_OPENING`, then use `await assistant_reply(caller_text)` for the single
  live reply. Any model error or unsafe output returns `ASSISTANT_FALLBACK`. Guardrails reject money, digits,
  promises, negotiation, and impersonation.
- **Frontend (Dev):** `fixtures/*.json` contain contract `transcript.final` envelopes. To get the full stream with
  `risk.updated` events, run the replay command below. Label any replayed data "Demo replay".

## How detection works

1. **Normalize.** Known speakers only, trimmed text, and duplicate `utterance_id`s keep the first copy.
   Matching uses a folded copy (NFKC, straight quotes, single spaces). Quotes always come from the original text.
2. **Rules** (`rules.py`). Regex indicators, matched per sentence, quote the exact sentence. They are deterministic,
   need no network, and take under 1 ms.
3. **Gemini** (`detector.py`). This step runs only when `GEMINI_API_KEY` and `GEMINI_MODEL` are set, and only
   when rules found at least one indicator but not high. Benign chat makes no model call. It adds paraphrased
   indicators. Each quote is checked against its utterance and unverifiable ones are dropped. Gemini can only add
   indicators, never remove them, so an instruction spoken by the caller cannot hide rule findings. Results are
   cached per transcript window. On failure the client falls back to rules and skips the model for 15 s, so an
   outage does not add a 5 s timeout to every utterance.
4. **Policy** (`detector.risk_level`). High needs three things:
   - a financial reason and a pressure reason, with at least 3 distinct reasons,
   - all of them within 4 consecutive utterances,
   - the financial ask coming from the caller or an ambient speaker, not the wearer.

   Review needs any financial reason or at least 2 reasons. Otherwise the result is low. A large price alone is
   review. This is a demo policy, not a validated fraud classifier.

Reason codes: financial: `gift_card_request payment_request credential_request remote_access_request large_amount`.
Pressure: `urgency secrecy verification_discouraged threat`. Context: `family_emergency impersonation`.

## Run

```bash
python -m pytest backend/intelligence -q
python -m backend.intelligence.replay fixtures --check
python -m backend.intelligence.replay fixtures/scam_call.json
```

The first command runs the tests (offline, no keys needed). The second checks every fixture against its
`expected` block. The third prints the JSON-lines event stream for Dev.

Env vars (from the shared `.env` contract): `GEMINI_API_KEY`, `GEMINI_MODEL`. Both are optional. Without them the
module runs on rules only.

## Known limitations

- The Gemini call is unit-tested against a mocked HTTP layer only. It still needs one live smoke test with the
  team key. Set the env vars and run the replay command to do it. It uses `v1beta/models/{model}:generateContent`
  with `responseJsonSchema`.
- Rules are English-only, with no negation handling. "I will never ask you for gift cards" still counts as a
  gift card mention. Gemini adds recall for paraphrases, not precision.
- Bare mentions of family topics, such as "I got a gift card" or "keep it a secret, it's her birthday", are
  excluded. Even so, a run of benign caller lines that each hit a keyword can still add up to high.
- The window is the last 30 analyzable utterances. Duplicate `utterance_id`s keep the first copy, per the
  contract. Send only final transcripts, never interim ones.
- Suggested contract addition, not done because `shared/` is Ayush's: an evidence-level `reasons` field so the UI
  can label each quote.
