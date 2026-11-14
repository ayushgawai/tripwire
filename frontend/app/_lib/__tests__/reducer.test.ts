// Run: npm test   (Node's built-in runner with native TypeScript type stripping)
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyEvent, emptyView, evidenceIndex, highlightSegments, viewFromSnapshot } from "../reducer.ts";
import { SCENARIOS } from "../fixtures.ts";
import type { EventEnvelope, SessionView } from "../types.ts";

function envelopes(id: string): EventEnvelope[] {
  const sc = SCENARIOS.find((s) => s.id === id)!;
  return sc.steps.map((st, i) => ({
    event_id: `e${i + 1}`,
    session_id: "s1",
    sequence: i + 1,
    type: st.type,
    timestamp: new Date(2026, 10, 14, 20, 0, i).toISOString(),
    payload: st.payload,
  }));
}
const run = (evs: EventEnvelope[], v: SessionView = emptyView("s1")) => evs.reduce(applyEvent, v);

test("scam script ends in assistant_active with one alert and verified evidence", () => {
  const v = run(envelopes("scam"));
  assert.equal(v.state, "assistant_active");
  assert.equal(v.takeover, "active");
  assert.equal(v.latestDecision?.risk, "high");
  assert.ok(v.alert);
  for (const e of v.latestDecision!.evidence) {
    const u = v.transcript.find((t) => t.utterance_id === e.utterance_id);
    assert.ok(u && u.text.includes(e.quote), `quote "${e.quote}" must occur in ${e.utterance_id}`);
  }
  assert.deepEqual(v.timeline.map((t) => t.state), ["protecting", "assistant_active"]);
});

test("benign and ambiguous scenarios never leave monitoring", () => {
  for (const id of ["benign", "ambiguous"]) {
    const v = run(envelopes(id));
    assert.equal(v.state, "monitoring", id);
    assert.equal(v.takeover, "idle", id);
    assert.equal(v.alert, null, id);
    assert.notEqual(v.latestDecision?.risk, "high", id);
  }
});

test("duplicate event ids and stale sequences are ignored", () => {
  const evs = envelopes("scam");
  const once = run(evs);
  const twice = run([...evs, ...evs]);
  assert.equal(twice.transcript.length, once.transcript.length);
  assert.equal(twice.decisions.length, once.decisions.length);
  assert.equal(twice.timeline.length, once.timeline.length);
  const stale = applyEvent(once, { ...evs[0], event_id: "new_id", sequence: 1 });
  assert.equal(stale, once);
});

test("family.joined then wearer.reconnected; ended is terminal", () => {
  let v = run(envelopes("scam"));
  const next = (type: EventEnvelope["type"], seq: number): EventEnvelope => ({
    event_id: `x${seq}`, session_id: "s1", sequence: seq, type, timestamp: new Date().toISOString(), payload: {},
  });
  v = applyEvent(v, next("family.joined", 100));
  assert.equal(v.state, "family_joined");
  assert.equal(v.wearerReconnected, false, "wearer stays protected until explicit reconnect");
  v = applyEvent(v, next("wearer.reconnected", 101));
  assert.equal(v.wearerReconnected, true);
  v = applyEvent(v, next("session.ended", 102));
  v = applyEvent(v, next("takeover.active", 103));
  assert.equal(v.state, "ended");
});

test("takeover.failed is surfaced, not shown as success", () => {
  let v = run(envelopes("scam").slice(0, 6)); // through takeover.started
  assert.equal(v.state, "protecting");
  v = applyEvent(v, { event_id: "f", session_id: "s1", sequence: 50, type: "takeover.failed", timestamp: "", payload: { reason: "Wearer client did not confirm" } });
  assert.equal(v.takeover, "failed");
  assert.equal(v.takeoverError, "Wearer client did not confirm");
  assert.notEqual(v.state, "assistant_active");
});

test("events from another session are ignored", () => {
  const v = applyEvent(emptyView("s1"), { event_id: "o", session_id: "other", sequence: 1, type: "session.ended", timestamp: "", payload: {} });
  assert.equal(v.state, "monitoring");
});

test("snapshot restores state for refreshed clients", () => {
  const v = viewFromSnapshot({
    session_id: "s1", state: "assistant_active", last_sequence: 9,
    transcript: [{ utterance_id: "u1", speaker: "caller", text: "Buy gift cards now" }],
    latest_decision: { decision_id: "d1", risk: "high", reasons: ["urgency"], evidence: [{ utterance_id: "u1", quote: "gift cards" }], summary: "x", recommended_action: "takeover" },
    alert: { summary: "x" },
    wearer_connected: false,
    takeover: { status: "active", wearer_audio_blocked: true, assistant_ready: true },
  });
  assert.equal(v.state, "assistant_active");
  assert.equal(v.takeover, "active");
  assert.equal(v.lastSequence, 9);
  assert.deepEqual(v.alert?.evidence, [{ utterance_id: "u1", quote: "gift cards" }]);
  assert.deepEqual(evidenceIndex(v).get("u1"), ["gift cards"]);
});

test("highlightSegments marks only quotes present in the text", () => {
  const segs = highlightSegments("Buy gift cards now. Do not tell.", ["gift cards", "not in text", "Do not tell"]);
  assert.deepEqual(segs.filter((s) => s.hit).map((s) => s.text), ["gift cards", "Do not tell"]);
  assert.equal(segs.map((s) => s.text).join(""), "Buy gift cards now. Do not tell.");
});

test("contract snapshot: takeover object, failed status, wearer_connected", () => {
  const failed = viewFromSnapshot({ session_id: "s1", state: "protecting", takeover: { status: "failed", wearer_audio_blocked: false, assistant_ready: false } });
  assert.equal(failed.takeover, "failed");
  assert.equal(failed.state, "protecting", "failed takeover keeps state protecting");
  const rec = viewFromSnapshot({ session_id: "s1", state: "family_joined", wearer_connected: true, takeover: { status: "active" } });
  assert.equal(rec.wearerReconnected, true);
  const notRec = viewFromSnapshot({ session_id: "s1", state: "family_joined", wearer_connected: false });
  assert.equal(notRec.wearerReconnected, false);
  const fresh = viewFromSnapshot({ session_id: "s1", state: "monitoring", wearer_connected: true });
  assert.equal(fresh.wearerReconnected, false, "monitoring wearer is connected but was never 'reconnected'");
});

test("payload.demo_replay marks the view as demo replay", () => {
  const live = applyEvent(emptyView("s1"), { event_id: "a", session_id: "s1", sequence: 1, type: "transcript.final", timestamp: "", payload: { utterance_id: "u", speaker: "caller", text: "hi" } });
  assert.equal(live.demoReplay, false);
  const demo = applyEvent(live, { event_id: "b", session_id: "s1", sequence: 2, type: "transcript.final", timestamp: "", payload: { utterance_id: "u2", speaker: "caller", text: "hi", demo_replay: true } });
  assert.equal(demo.demoReplay, true);
});
