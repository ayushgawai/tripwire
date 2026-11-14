"use client";
// Integration slot for Manav's call components (frontend/components/call/).
// Dev does NOT rebuild call controls. When Manav's component lands, render it where marked below,
// passing { role, credentials, state }. Takeover success is confirmed by backend events, not here.
import { useState } from "react";
import type { JoinCredentials, Role, SessionState } from "@/app/_lib/types";
import { Button } from "./Button";
import { cn } from "./cn";

export function CallSurface({
  role,
  state,
  onJoin,
  replay,
  className,
  compact,
  credentials,
}: {
  role: Role;
  state: SessionState;
  onJoin: (role: Role) => Promise<JoinCredentials | null>;
  replay?: boolean;
  className?: string;
  compact?: boolean;
  /** When provided, the parent owns joining (e.g. family's main Join button); no extra join button. */
  credentials?: JoinCredentials | null;
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

  return (
    <div className={cn("rounded-2xl border border-dashed border-line bg-paper/60 p-4", className)}>
      {/* >>> Manav: replace this block with <CallPanel role={role} credentials={creds} state={state} /> */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {creds ? (replay ? "Replay call (no audio)" : "Room credentials received") : "Browser call"}
          </p>
          {!compact && (
            <p className="truncate text-xs text-ink-faint">
              {creds
                ? replay
                  ? "Demo replay does not connect audio."
                  : `Call component mounts here · ${String(creds.room_url ?? "room")}`
                : `Join as ${role}. Audio routing is handled by the call module.`}
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
