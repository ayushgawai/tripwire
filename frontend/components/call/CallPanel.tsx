"use client";

/**
 * Mount point for Dev's CallSurface — wraps CallRoom + useCallSession.
 * Pass Ayush role session token as accessToken; optional pre-fetched join credentials.
 */

import { CallRoom } from "./CallRoom";
import { useCallSession } from "./hooks/useCallSession";
import type { ProviderCredentials, Role, SessionState } from "./types";

export interface CallPanelProps {
  role: Role;
  sessionId: string;
  accessToken: string;
  backendUrl?: string;
  credentials?: ProviderCredentials | null;
  state?: SessionState;
  evidenceQuotes?: string[];
  alertSummary?: string | null;
  forceFixture?: boolean;
}

export function CallPanel({
  role,
  sessionId,
  accessToken,
  backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  credentials = null,
  evidenceQuotes,
  alertSummary,
  forceFixture,
}: CallPanelProps) {
  const { view, join, endCall, reconnectWearer, connecting } = useCallSession({
    sessionId,
    role,
    accessToken,
    backendUrl: backendUrl.replace(/\/$/, ""),
    initialCredentials: credentials,
    forceFixture,
  });

  return (
    <CallRoom
      view={view}
      evidenceQuotes={evidenceQuotes}
      alertSummary={alertSummary}
      joining={Boolean(connecting)}
      onJoin={() => {
        void join();
      }}
      onEndCall={() => {
        void endCall();
      }}
      onReconnectWearer={() => {
        void reconnectWearer();
      }}
    />
  );
}
