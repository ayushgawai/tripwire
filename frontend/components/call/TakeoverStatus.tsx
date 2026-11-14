"use client";

export interface TakeoverStatusProps {
  role: "caller" | "wearer" | "family";
  state: string;
  callerAudioBlocked: boolean;
  wearerMicrophonePaused: boolean;
  workerReady: boolean;
  wearerProtected: boolean;
  takeoverError: string | null;
  /** Wearer-only private warning; never shown to caller. */
  showWearerWarning?: boolean;
}

export function TakeoverStatus({
  role,
  state,
  callerAudioBlocked,
  wearerMicrophonePaused,
  workerReady,
  wearerProtected,
  takeoverError,
  showWearerWarning = role === "wearer",
}: TakeoverStatusProps) {
  return (
    <section aria-label="Takeover status" data-testid="takeover-status">
      <h2 style={{ fontSize: "1rem" }}>Protection / AI status</h2>
      <dl style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem" }}>
        <dt>Session state</dt>
        <dd>{state}</dd>
        {role !== "caller" ? (
          <>
            <dt>Caller audio to wearer</dt>
            <dd>{callerAudioBlocked ? "Blocked" : "Playing"}</dd>
            <dt>Wearer microphone</dt>
            <dd>{wearerMicrophonePaused ? "Paused" : "Sending"}</dd>
            <dt>Wearer protected</dt>
            <dd>{wearerProtected ? "Yes" : "No"}</dd>
          </>
        ) : (
          <>
            <dt>AI assistant</dt>
            <dd>
              {state === "assistant_active" || workerReady
                ? "Speaking with you"
                : "Not active"}
            </dd>
          </>
        )}
        <dt>AI worker</dt>
        <dd>{workerReady ? "Ready" : "Not ready"}</dd>
      </dl>
      {showWearerWarning && wearerProtected ? (
        <p role="alert" style={{ fontWeight: 700, marginTop: "0.75rem" }}>
          Warning: This request may be unsafe. We are asking your trusted contact
          to help. Caller audio is blocked for you.
        </p>
      ) : null}
      {takeoverError ? (
        <p role="alert" style={{ fontWeight: 700 }}>
          Takeover failed: {takeoverError}. Use End Call if needed.
        </p>
      ) : null}
    </section>
  );
}
