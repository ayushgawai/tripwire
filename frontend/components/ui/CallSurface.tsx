"use client";
// Integration slot for Manav's call components (frontend/components/call/).
// Dev does NOT rebuild call controls. Manav mounts CallPanel below.
import { useState } from "react";
import type { JoinCredentials, Role, SessionState } from "@/app/_lib/types";
import { CallPanel } from "@/components/call/CallPanel";
import type { ProviderCredentials } from "@/components/call/types";
import { Button } from "./Button";
import { cn } from "./cn";

function toProviderCredentials(
  role: Role,
  sessionId: string,
  creds: JoinCredentials
): ProviderCredentials {
  return {
    session_id: sessionId,
    role,
    room_name: String(creds.room_name ?? ""),
    room_url: String(creds.room_url ?? ""),
    token: String(creds.token ?? ""),
    expires_at: String(creds.expires_at ?? ""),
    user_id: String(creds.user_id ?? `${role}_user`),
    provider: String(creds.provider ?? (creds.fixture_mode ? "mock" : "daily")),
    fixture_mode: Boolean(creds.fixture_mode),
  };
}

export function CallSurface({
  role,
  state,
  onJoin,
  replay,
  className,
  compact,
  credentials,
  sessionId,
  accessToken,
}: {
  role: Role;
  state: SessionState;
  onJoin: (role: Role) => Promise<JoinCredentials | null>;
  replay?: boolean;
  className?: string;
  compact?: boolean;
  /** When provided, the parent owns joining (e.g. family's main Join button); no extra join button. */
  credentials?: JoinCredentials | null;
  /** Required to mount live CallPanel once session tokens exist. */
  sessionId?: string;
  accessToken?: string | null;
}) {
  const [ownCreds, setCreds] = useState<JoinCredentials | null>(null);
  const controlled = credentials !== undefined;
  const creds = controlled ? credentials : ownCreds;
  const [joining, setJoining] = useState(false);
  const ended = state === "ended";

  const join = async () => {
    setJoining(true);
    const c = await onJoin(role);
    setJoining(false);
    if (c) setCreds(c);
  };

  // Full call panel when we have session identity + credentials (or can join).
  if (sessionId && accessToken && !replay) {
    return (
      <div className={cn("rounded-2xl border border-line bg-paper/60 p-4", className)}>
        <CallPanel
          role={role}
          sessionId={sessionId}
          accessToken={accessToken}
          credentials={
            creds ? toProviderCredentials(role, sessionId, creds) : null
          }
          state={state}
          forceFixture={Boolean(creds?.fixture_mode)}
        />
      </div>
    );
  }

  return (
    <div className={cn("rounded-2xl border border-dashed border-line bg-paper/60 p-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {creds
              ? replay
                ? "Replay call (no audio)"
                : "Room credentials received"
              : "Browser call"}
          </p>
          {!compact && (
            <p className="truncate text-xs text-ink-faint">
              {creds
                ? replay
                  ? "Demo replay does not connect audio."
                  : `Call component mounts here · ${String(creds.room_url ?? "room")}`
                : `Join as ${role}. Pass sessionId + accessToken to mount CallPanel.`}
            </p>
          )}
        </div>
        {!creds && !ended && !controlled && (
          <Button variant="outline" onClick={join} loading={joining}>
            Join as {role}
          </Button>
        )}
        {creds && (
          <span className="inline-flex items-center gap-2 rounded-full bg-safe-soft px-3 py-1 text-xs font-semibold text-safe">
            <span className="h-1.5 w-1.5 rounded-full bg-safe" /> Credentials ready
          </span>
        )}
      </div>
    </div>
  );
}
