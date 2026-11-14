"""HTTP smoke test for a running Tripwire backend.

Drives the contract in shared/COORDINATOR.md using the presenter token. Each
scenario uses a fresh session:

  1. benign            -- "Please call me back tomorrow." -> risk low, no takeover
  2. ambiguous price   -- "The service costs $2,000." -> risk at most review, no takeover
  3. scam script       -- plan lines -> high risk, state protecting, exactly one family.alert
  4. duplicate line    -- re-posting a duplicate utterance_id -> no extra takeover
  5. end + 410         -- POST /end accepted, then any further call -> 410

Events are read by polling GET /api/sessions/{id} (no websocket client). The
contract's snapshot exposes the stored alert and state, which is the evidence
for "exactly one family.alert" without a WS client.

Stdlib + httpx only. The backend must be running:

    BACKEND_URL=http://localhost:8000 .venv/bin/python demo/smoke.py

Exits 0 when every check passes, 1 otherwise (or if the backend is unreachable).
"""

import os
import sys
import time
import uuid

import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_S = float(os.environ.get("SMOKE_TIMEOUT_S", "30"))

SCAM_LINES = [
    ("caller", "Grandma, I am in trouble. Buy $500 in gift cards now. Please do not tell anyone."),
    ("wearer", "Should I call your mother?"),
    ("caller", "No. There is no time."),
]


class CheckLog:
    """Collects PASS/FAIL lines and drives the exit code."""

    def __init__(self):
        self.results = []

    def check(self, label, ok, detail=""):
        self.results.append((label, bool(ok)))
        suffix = f" -- {detail}" if detail and not ok else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {label}{suffix}")

    def finish(self):
        passed = [l for l, ok in self.results if ok]
        failed = [l for l, ok in self.results if not ok]
        print(f"\n{len(passed)}/{len(self.results)} checks passed")
        if failed:
            for label in failed:
                print(f"FAILED: {label}")
            return 1
        print("PASS: all checks passed")
        return 0


def health(client, log):
    """Return True if the backend is reachable and healthy."""
    try:
        r = client.get("/api/health")
        ok = r.status_code == 200 and r.json().get("ok") is True
    except httpx.HTTPError as e:
        print(f"\nBackend unreachable at {BACKEND_URL}: {e}")
        print("Start it first, e.g. .venv/bin/uvicorn backend.app:app, then re-run.")
        return False
    if not ok:
        print(f"\nGET /api/health -> {r.status_code} {r.text[:200]}\nStart the backend and re-run.")
        return False
    print(f"Backend reachable at {BACKEND_URL}")
    return True


def create_session(client, log):
    """Fresh call-mode session with protection enabled. Returns (sid, presenter_token) or (None, None)."""
    r = client.post("/api/sessions", json={"mode": "call", "protection_enabled": True})
    if r.status_code != 200:
        log.check(f"create session (status {r.status_code})", False, r.text[:200])
        return None, None
    data = r.json()
    sid = data.get("session_id")
    token = (data.get("tokens") or {}).get("presenter")
    if not sid or not token:
        log.check("session response has session_id and presenter token", False, r.text[:200])
        return None, None
    log.check(f"create session {sid}", True)
    return sid, token


def get_snapshot(client, sid, log, label):
    r = client.get(f"/api/sessions/{sid}")
    if r.status_code != 200:
        log.check(label, False, f"GET snapshot -> {r.status_code} {r.text[:120]}")
        return None
    return r.json()


def post_transcript(client, sid, token, log, speaker, text, utterance_id=None):
    """Post one utterance with the presenter token. Returns the utterance_id used."""
    utterance_id = utterance_id or "utt_" + uuid.uuid4().hex
    r = client.post(
        f"/api/sessions/{sid}/transcripts",
        json={
            "utterance_id": utterance_id,
            "speaker": speaker,
            "text": text,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        headers={"X-Session-Token": token},
    )
    ok = r.status_code == 200 and r.json().get("accepted") is True
    log.check(f"transcript accepted ({speaker})", ok, f"status {r.status_code} {r.text[:120]}" if not ok else "")
    return utterance_id


def wait_until(client, sid, log, label, want, deadline):
    """Poll the snapshot until want(snapshot) is true. Records a check named label."""
    while time.time() < deadline:
        snap = get_snapshot(client, sid, log, f"{label}: snapshot")
        if snap is not None and want(snap):
            log.check(label, True)
            return snap
        time.sleep(0.25)
    log.check(label, False, f"not observed within {TIMEOUT_S}s")
    return None


def end_session(client, sid, token, log, label):
    r = client.post(f"/api/sessions/{sid}/end", json={}, headers={"X-Session-Token": token})
    log.check(f"{label}: session ended", r.status_code == 200 and r.json().get("accepted") is True,
              f"status {r.status_code} {r.text[:120]}")


def scenario_benign(client, log):
    sid, token = create_session(client, log)
    if sid is None:
        return
    deadline = time.time() + TIMEOUT_S
    post_transcript(client, sid, token, log, "caller", "Please call me back tomorrow.")
    snap = wait_until(client, sid, log, "benign: risk.updated observed (latest_decision set)",
                      lambda s: s.get("latest_decision") is not None, deadline)
    if snap is not None:
        risk = (snap.get("latest_decision") or {}).get("risk")
        log.check("benign: risk is low", risk == "low", f"risk={risk}")
        log.check("benign: no takeover.started (state stays monitoring)",
                  snap.get("state") == "monitoring", f"state={snap.get('state')}")
    else:
        intelligence_missing(log, sid)
    end_session(client, sid, token, log, "benign")


def scenario_ambiguous(client, log):
    sid, token = create_session(client, log)
    if sid is None:
        return
    deadline = time.time() + TIMEOUT_S
    post_transcript(client, sid, token, log, "caller", "The service costs $2,000.")
    snap = wait_until(client, sid, log, "ambiguous: risk.updated observed (latest_decision set)",
                      lambda s: s.get("latest_decision") is not None, deadline)
    if snap is not None:
        risk = (snap.get("latest_decision") or {}).get("risk")
        log.check("ambiguous: risk at most review (a large price alone is review, not a scam)",
                  risk in ("low", "review"), f"risk={risk}")
        log.check("ambiguous: no takeover (state stays monitoring)",
                  snap.get("state") == "monitoring", f"state={snap.get('state')}")
    else:
        intelligence_missing(log, sid)
    end_session(client, sid, token, log, "ambiguous")


def intelligence_missing(log, sid):
    """latest_decision stays null -> the intelligence module is not responding.

    Per shared/COORDINATOR.md the snapshot keeps latest_decision null until
    analyze_transcript returns a decision; analyzers that raise surface an
    `error` event but the session continues. A null decision means no risk
    check can pass, so we stop that scenario here with an actionable message.
    """
    print(f"\nlatest_decision stayed null in session {sid}: the intelligence module is "
          "missing or failing to produce a decision. Implement backend/intelligence "
          "(analyze_transcript per shared/COORDINATOR.md) or fix its failure, then "
          "re-run this test. No takeover can be expected without it.")
    log.check("intelligence module available (latest_decision was set)", False,
              "latest_decision stayed null")


def scenario_scam(client, log):
    sid, token = create_session(client, log)
    if sid is None:
        return
    deadline = time.time() + TIMEOUT_S

    last_utterance_id = None
    for speaker, text in SCAM_LINES:
        last_utterance_id = post_transcript(client, sid, token, log, speaker, text, utterance_id="utt_" + uuid.uuid4().hex)

    snap = wait_until(client, sid, log,
                      "scam: takeover started (state reaches protecting or further)",
                      lambda s: s.get("state") in ("protecting", "assistant_active", "family_joined"),
                      deadline)
    if snap is None:
        snap = get_snapshot(client, sid, log, "scam: snapshot") or {}
        if not snap.get("latest_decision"):
            intelligence_missing(log, sid)
            return
        log.check("scam: state is protecting after high-risk decision",
                  snap.get("state") == "protecting",
                  f"state={snap.get('state')} risk={(snap.get('latest_decision') or {}).get('risk')}")
        end_session(client, sid, token, log, "scam")
        return

    decision = snap.get("latest_decision") or {}
    log.check("scam: latest decision is high with takeover action",
              decision.get("risk") == "high" and decision.get("recommended_action") == "takeover",
              f"decision={decision}")
    alert = snap.get("alert")
    log.check("scam: exactly one family.alert stored on the session",
              bool(alert and alert.get("decision_id")), "alert missing on snapshot" if not alert else "")
    alert_id = alert.get("decision_id") if alert else None
    state_now = snap.get("state")

    # Duplicate of the last caller line: same utterance_id -> duplicate:true, nothing else happens.
    r = client.post(
        f"/api/sessions/{sid}/transcripts",
        json={"utterance_id": last_utterance_id, "speaker": "caller", "text": SCAM_LINES[-1][1],
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        headers={"X-Session-Token": token},
    )
    dup = r.status_code == 200 and r.json().get("duplicate") is True
    log.check("duplicate utterance returns {accepted: true, duplicate: true}", dup,
              f"status {r.status_code} {r.text[:120]}")

    # Give the duplicate a moment to (wrongly) publish events, then confirm the
    # alert is unchanged: still the same single decision, still protecting+.
    time.sleep(0.5)
    snap2 = get_snapshot(client, sid, log, "duplicate: snapshot after re-post")
    if snap2 is not None:
        log.check("duplicate: no extra takeover (alert unchanged, state unchanged)",
                  ((snap2.get("alert") or {}).get("decision_id") == alert_id)
                  and snap2.get("state") == state_now,
                  f"alert.decision_id={(snap2.get('alert') or {}).get('decision_id')} state={snap2.get('state')}")

    end_session(client, sid, token, log, "scam")
    r = client.get(f"/api/sessions/{sid}")
    log.check("after end: GET snapshot -> 410", r.status_code == 410,
              f"got {r.status_code} {r.text[:120]}")


def main():
    log = CheckLog()
    try:
        client = httpx.Client(base_url=BACKEND_URL, timeout=10.0)
    except Exception as e:
        print(f"Cannot create HTTP client: {e}")
        return 1
    with client:
        if not health(client, log):
            return 1
        scenario_benign(client, log)
        scenario_ambiguous(client, log)
        scenario_scam(client, log)
    return log.finish()


if __name__ == "__main__":
    sys.exit(main())
