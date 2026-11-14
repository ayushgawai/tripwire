"use client";

import { cn } from "@/components/ui/cn";
import { Pulse } from "@/components/ui/Pulse";

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
  const isWearer = role === "wearer";

  return (
    <section aria-label="Takeover status" data-testid="takeover-status" className="rounded-2xl border border-line bg-card p-4">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-faint">Protection / AI status</h2>

      <dl className="m-0 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-ink-faint">Session state</dt>
        <dd className="text-right font-semibold text-ink">{state}</dd>

        {isWearer ? (
          <>
            <StatusRow label="Caller audio" value={callerAudioBlocked ? "Blocked for you" : "Playing"} status={callerAudioBlocked ? "danger" : "safe"} />
            <StatusRow label="Microphone" value={wearerMicrophonePaused ? "Paused" : "Sending"} status={wearerMicrophonePaused ? "watch" : "safe"} />
            <StatusRow label="Protected" value={wearerProtected ? "Yes" : "No"} status={wearerProtected ? "safe" : "muted"} />
          </>
        ) : (
          <>
            <dt className="text-ink-faint">AI assistant</dt>
            <dd className="text-right font-semibold text-ink">
              {state === "assistant_active" || workerReady ? "Speaking with you" : "Not active"}
            </dd>
          </>
        )}

        <dt className="text-ink-faint">AI worker</dt>
        <dd className="text-right font-semibold text-ink">
          {workerReady ? "Ready" : "Not ready"}
        </dd>
      </dl>

      {/* Wearer warning — prominent chip */}
      {showWearerWarning && wearerProtected && (
        <div
          role="alert"
          className="mt-3 flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-sm font-medium text-danger"
        >
          <Pulse tone="danger" still size={7} />
          <span>
            This request may be unsafe. We asked your trusted contact to help.
            {callerAudioBlocked && " Caller audio is blocked for you."}
          </span>
        </div>
      )}

      {takeoverError ? (
        <div
          role="alert"
          className="mt-3 flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-sm font-medium text-danger"
        >
          <span>Takeover failed: {takeoverError}. Use End Call if needed.</span>
        </div>
      ) : null}
    </section>
  );
}

function StatusRow({ label, value, status }: { label: string; value: string; status: "safe" | "danger" | "watch" | "muted" }) {
  const colorMap = {
    safe: "text-safe",
    danger: "text-danger",
    watch: "text-watch",
    muted: "text-ink-faint",
  };
  return (
    <>
      <dt className="text-ink-faint">{label}</dt>
      <dd className={cn("text-right font-semibold", colorMap[status])}>
        {value}
      </dd>
    </>
  );
}

