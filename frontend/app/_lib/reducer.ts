// Pure event reducer. No React, no network — unit tested in __tests__/reducer.test.ts.
// Rules from the plan:
//  - every event has a unique event_id and monotonically increasing sequence per session
//  - reconnecting clients fetch the snapshot first, then apply only newer events
//  - UI state is driven by backend events only; a button click never implies success
import type {
  EventEnvelope,
  Evidence,
  FamilyAlert,
  RiskDecision,
  SessionMode,
  SessionState,
  SessionView,
  Utterance,
} from "./types.ts";

const MAX_LOG = 200;

export function emptyView(session_id = "", mode: SessionMode = "call"): SessionView {
  return {
    session_id,
    mode,
    state: "monitoring",
    transcript: [],
    decisions: [],
    latestDecision: null,
    alert: null,
    takeover: "idle",
    takeoverError: null,
    familyJoined: false,
    wearerReconnected: false,
    demoReplay: false,
    errors: [],
    timeline: [],
    lastSequence: 0,
    seenEventIds: [],
    log: [],
    lastAssistantUtterance: null,
    interim: null,
  };
}

const STATES: SessionState[] = [
  "monitoring",
  "protecting",
  "assistant_active",
  "family_joined",
  "ended",
];

function isState(s: unknown): s is SessionState {
  return typeof s === "string" && (STATES as string[]).includes(s);
}

function asArray<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

export function normalizeDecision(raw: unknown): RiskDecision | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const risk = r.risk;
  if (risk !== "low" && risk !== "review" && risk !== "high") return null;
  const action = r.recommended_action;
  return {
    decision_id: str(r.decision_id, `decision_${Date.now()}`),
    risk,
    reasons: asArray<unknown>(r.reasons).filter((x): x is string => typeof x === "string"),
    evidence: asArray<Record<string, unknown>>(r.evidence)
      .filter((e) => e && typeof e.quote === "string")
      .map((e) => ({ utterance_id: str(e.utterance_id), quote: str(e.quote) })),
    summary: str(r.summary),
    recommended_action:
      action === "alert" || action === "takeover" || action === "none" ? action : "none",
  };
}

function normalizeAlert(raw: unknown, fallback: RiskDecision | null): FamilyAlert | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const evidence = asArray<Evidence>(r.evidence);
  const reasons = asArray<string>(r.reasons);
  return {
    decision_id: str(r.decision_id) || fallback?.decision_id,
    summary: str(r.summary) || fallback?.summary || "Tripwire flagged this conversation.",
    reasons: reasons.length ? reasons : (fallback?.reasons ?? []),
    evidence: evidence.length ? evidence : (fallback?.evidence ?? []),
    timestamp: str(r.timestamp) || undefined,
  };
}

function normalizeUtterance(raw: unknown, ts?: string): Utterance | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.text !== "string" || typeof r.utterance_id !== "string") return null;
  const speaker = r.speaker;
  return {
    utterance_id: r.utterance_id,
    speaker:
      speaker === "caller" ||
      speaker === "wearer" ||
      speaker === "family" ||
      speaker === "assistant" ||
      speaker === "ambient"
        ? speaker
        : "ambient",
    text: r.text,
    timestamp: str(r.timestamp) || ts,
  };
}

function withState(view: SessionView, next: SessionState, at: string): SessionView {
  if (view.state === next) return view;
  // "ended" is terminal — never resurrect a session from a late event.
  if (view.state === "ended") return view;
  return { ...view, state: next, timeline: [...view.timeline, { state: next, at }] };
}

export function applyEvent(view: SessionView, ev: EventEnvelope): SessionView {
  if (!ev || typeof ev !== "object") return view;
  if (view.session_id && ev.session_id && ev.session_id !== view.session_id) return view;
  if (view.seenEventIds.includes(ev.event_id)) return view;
  if (typeof ev.sequence === "number" && ev.sequence <= view.lastSequence) return view;

  const at = ev.timestamp || new Date().toISOString();
  const p = (ev.payload ?? {}) as Record<string, unknown>;
  let v: SessionView = {
    ...view,
    session_id: view.session_id || ev.session_id,
    lastSequence: typeof ev.sequence === "number" ? ev.sequence : view.lastSequence,
    seenEventIds: [...view.seenEventIds.slice(-499), ev.event_id],
    log: [...view.log.slice(-(MAX_LOG - 1)), ev],
    demoReplay: view.demoReplay || p.demo_replay === true,
  };

  switch (ev.type) {
    case "transcript.final": {
      const u = normalizeUtterance(p, at);
      if (u && !v.transcript.some((t) => t.utterance_id === u.utterance_id)) {
        v = { ...v, transcript: [...v.transcript, u], interim: null };
      }
      break;
    }
    case "transcript.interim": {
      const txt = str(p.text);
      v = { ...v, interim: txt ? { speaker: str(p.speaker, "caller"), text: txt } : null };
      break;
    }
    case "risk.updated": {
      const d = normalizeDecision(p.decision ?? p);
      if (d && !v.decisions.some((x) => x.decision_id === d.decision_id)) {
        v = { ...v, decisions: [...v.decisions, d], latestDecision: d };
      }
      break;
    }
    case "takeover.started":
      v = withState({ ...v, takeover: "starting", takeoverError: null }, "protecting", at);
      break;
    case "takeover.active":
      v = withState({ ...v, takeover: "active", takeoverError: null }, "assistant_active", at);
      break;
    case "takeover.failed":
      v = {
        ...v,
        takeover: "failed",
        takeoverError: str(p.reason) || str(p.message) || "Takeover could not be confirmed.",
        timeline: [...v.timeline, { state: "takeover_failed", at }],
      };
      break;
    case "family.alert":
      v = { ...v, alert: normalizeAlert(p, v.latestDecision) };
      break;
    case "family.joined":
      v = withState({ ...v, familyJoined: true }, "family_joined", at);
      break;
    case "wearer.reconnected":
      v = { ...v, wearerReconnected: true };
      break;
    case "session.ended":
      v = withState(v, "ended", at);
      break;
    case "error":
      v = {
        ...v,
        errors: [...v.errors.slice(-19), { message: str(p.message, "Unknown error"), at }],
      };
      break;
    case "assistant.spoke": {
      const uid = str(p.utterance_id);
      const txt = str(p.text);
      const audio = p.audio_url;
      if (uid && txt) {
        v = { ...v, lastAssistantUtterance: { utterance_id: uid, text: txt, audio_url: typeof audio === "string" ? audio : undefined } };
      }
      break;
    }
  }

  // If the backend includes an authoritative state on any event, trust it.
  if (isState(p.state)) v = withState(v, p.state, at);
  return v;
}

/** Build a view from GET /api/sessions/{id}. Field names are tolerant until the snapshot is frozen. */
export function viewFromSnapshot(raw: unknown): SessionView {
  const r = (raw ?? {}) as Record<string, unknown>;
  const base = emptyView(str(r.session_id), r.mode === "ambient" ? "ambient" : "call");
  const transcript = asArray<unknown>(r.transcript)
    .map((u) => normalizeUtterance(u))
    .filter((u): u is Utterance => !!u);
  const latest = normalizeDecision(r.latest_decision ?? r.decision ?? null);
  const state = isState(r.state) ? r.state : "monitoring";
  // Contract: takeover = {status, wearer_audio_blocked, assistant_ready}. Tolerate a bare string too.
  const tk = r.takeover && typeof r.takeover === "object" ? (r.takeover as Record<string, unknown>) : {};
  const takeoverRaw = str(tk.status ?? r.takeover_status ?? r.takeover);
  const takeover =
    takeoverRaw === "starting" || takeoverRaw === "active" || takeoverRaw === "failed"
      ? takeoverRaw
      : state === "protecting"
        ? "starting"
        : state === "assistant_active" || state === "family_joined"
          ? "active"
          : "idle";
  return {
    ...base,
    state,
    transcript,
    decisions: latest ? [latest] : [],
    latestDecision: latest,
    alert: normalizeAlert(r.alert, latest),
    takeover,
    takeoverError:
      takeover === "failed" ? str(tk.reason ?? r.takeover_error, "Takeover could not be confirmed.") : null,
    familyJoined: state === "family_joined" || r.family_joined === true,
    // wearer_connected goes false from protecting onward and true again only on wearer_reconnect.
    wearerReconnected: state === "family_joined" && r.wearer_connected === true,
    lastSequence: typeof r.last_sequence === "number" ? r.last_sequence : 0,
    timeline: [{ state, at: new Date().toISOString() }],
  };
}

/** Set of utterance ids that are cited as evidence by the latest decision or alert. */
export function evidenceIndex(view: SessionView): Map<string, string[]> {
  const idx = new Map<string, string[]>();
  const add = (e: Evidence) => {
    if (!e.utterance_id || !e.quote) return;
    const list = idx.get(e.utterance_id) ?? [];
    if (!list.includes(e.quote)) list.push(e.quote);
    idx.set(e.utterance_id, list);
  };
  view.latestDecision?.evidence.forEach(add);
  view.alert?.evidence.forEach(add);
  return idx;
}

/** Split text into plain/highlighted segments for each quote that actually occurs in it. */
export function highlightSegments(
  text: string,
  quotes: string[],
): { text: string; hit: boolean }[] {
  const ranges: [number, number][] = [];
  const lower = text.toLowerCase();
  for (const q of quotes) {
    const i = lower.indexOf(q.toLowerCase());
    if (q && i >= 0) ranges.push([i, i + q.length]);
  }
  if (!ranges.length) return [{ text, hit: false }];
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const out: { text: string; hit: boolean }[] = [];
  let pos = 0;
  for (const [s, e] of merged) {
    if (s > pos) out.push({ text: text.slice(pos, s), hit: false });
    out.push({ text: text.slice(s, e), hit: true });
    pos = e;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), hit: false });
  return out;
}

export function utteranceById(view: SessionView, id: string): Utterance | undefined {
  return view.transcript.find((u) => u.utterance_id === id);
}
