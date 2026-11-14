// Frontend mirror of the shared application contracts (see Tripwire_Quick_Build_Plan.md,
// "Shared contracts"). Ayush owns shared/contracts.json — when it lands, keep these in sync.

export type Speaker = "caller" | "wearer" | "family" | "assistant" | "ambient";
export type Role = "caller" | "wearer" | "family";
export type SessionMode = "call" | "ambient";
export type SessionState =
  | "monitoring"
  | "protecting"
  | "assistant_active"
  | "family_joined"
  | "ended";
export type RiskLevel = "low" | "review" | "high";
export type RecommendedAction = "none" | "alert" | "takeover";

export type EventType =
  | "transcript.final"
  | "risk.updated"
  | "takeover.started"
  | "takeover.active"
  | "takeover.failed"
  | "family.alert"
  | "family.joined"
  | "session.ended"
  | "error"
  // Proposed (not yet in shared contracts): daughter deliberately hands audio back to the wearer.
  | "wearer.reconnected";

export interface EventEnvelope<P = Record<string, unknown>> {
  event_id: string;
  session_id: string;
  sequence: number;
  type: EventType;
  timestamp: string;
  payload: P;
}

export interface Utterance {
  utterance_id: string;
  speaker: Speaker;
  text: string;
  timestamp?: string;
}

export interface Evidence {
  utterance_id: string;
  quote: string;
}

export interface RiskDecision {
  decision_id: string;
  risk: RiskLevel;
  reasons: string[];
  evidence: Evidence[];
  summary: string;
  recommended_action: RecommendedAction;
}

export interface FamilyAlert {
  decision_id?: string;
  summary: string;
  reasons: string[];
  evidence: Evidence[];
  timestamp?: string;
}

export type TakeoverStatus = "idle" | "starting" | "active" | "failed";

export interface TimelineEntry {
  state: SessionState | "takeover_failed";
  at: string;
}

/** Everything a page needs to render. Built from a snapshot + event stream. */
export interface SessionView {
  session_id: string;
  mode: SessionMode;
  state: SessionState;
  transcript: Utterance[];
  decisions: RiskDecision[];
  latestDecision: RiskDecision | null;
  alert: FamilyAlert | null;
  takeover: TakeoverStatus;
  takeoverError: string | null;
  familyJoined: boolean;
  wearerReconnected: boolean;
  errors: { message: string; at: string }[];
  timeline: TimelineEntry[];
  lastSequence: number;
  seenEventIds: string[];
  log: EventEnvelope[];
}

export interface JoinCredentials {
  room_url?: string;
  token?: string;
  expires_at?: string;
  [key: string]: unknown;
}
