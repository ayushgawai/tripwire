/**
 * Call UI types (Manav). Aligned with Dev's frontend/app/_lib/types.ts
 * and Tripwire_Quick_Build_Plan.md session/event contracts.
 */

export type Role = "caller" | "wearer" | "family";

export type SessionState =
  | "monitoring"
  | "protecting"
  | "assistant_active"
  | "family_joined"
  | "ended";

export type CallUiStatus =
  | "connecting"
  | "connected"
  | "monitoring"
  | "protection_starting"
  | "protected"
  | "ai_assistant_active"
  | "family_alert_sent"
  | "family_joining"
  | "family_joined"
  | "reconnecting_wearer"
  | "call_ended"
  | "takeover_failed"
  | "provider_error"
  | "reconnecting"
  | "local_fixture";

export type CallEventType =
  | "transcript.final"
  | "risk.updated"
  | "takeover.started"
  | "takeover.active"
  | "takeover.failed"
  | "family.alert"
  | "family.joined"
  | "session.ended"
  | "error"
  | "routing.confirmed"
  | "participant.joined"
  | "worker.ready"
  | "wearer.reconnected";

export interface EventEnvelope<P = Record<string, unknown>> {
  event_id: string;
  session_id: string;
  sequence: number;
  type: CallEventType | string;
  timestamp: string;
  payload: P;
}

export interface ProviderCredentials {
  session_id: string;
  role: Role;
  room_name: string;
  room_url: string;
  token: string;
  expires_at: string;
  user_id: string;
  provider: string;
  fixture_mode: boolean;
}

export interface RoutingConfirmationPayload {
  session_id: string;
  caller_audio_blocked: boolean;
  wearer_microphone_paused: boolean;
  timestamp: string;
}

export interface CallParticipant {
  id: string;
  role?: Role | "assistant" | "unknown";
  user_id?: string;
  displayName: string;
  audioSubscribed: boolean;
  micPublishing: boolean;
  local: boolean;
}

export interface CallSessionView {
  sessionId: string;
  role: Role;
  state: SessionState;
  uiStatus: CallUiStatus;
  fixtureMode: boolean;
  participants: CallParticipant[];
  callerAudioBlocked: boolean;
  wearerMicrophonePaused: boolean;
  workerReady: boolean;
  familyAlertSent: boolean;
  familyJoined: boolean;
  wearerProtected: boolean;
  wearerReconnected: boolean;
  takeoverError: string | null;
  providerError: string | null;
  connected: boolean;
}

export interface CallProviderClient {
  readonly name: string;
  readonly fixtureMode: boolean;
  connect(credentials: ProviderCredentials): Promise<void>;
  disconnect(): Promise<void>;
  setMicEnabled(enabled: boolean): Promise<void>;
  /** Wearer: unsubscribe from caller's audio without muting the caller globally. */
  setRemoteAudioSubscribed(participantId: string, subscribed: boolean): Promise<void>;
  getLocalParticipantId(): string | null;
  getParticipants(): CallParticipant[];
  onParticipantJoined(handler: (p: CallParticipant) => void): () => void;
  onParticipantLeft(handler: (p: CallParticipant) => void): () => void;
  onError(handler: (message: string) => void): () => void;
  destroy(): Promise<void>;
}
