"use client";

import type { CallParticipant } from "./types";

import { cn } from "@/components/ui/cn";

const ROLE_COLORS: Record<string, string> = {
  wearer: "bg-watch-soft text-watch border-watch/30",
  caller: "bg-family-soft text-family border-family/30",
  family: "bg-safe-soft text-safe border-safe/30",
  assistant: "bg-ai-soft text-ai border-ai/30",
  unknown: "bg-line/60 text-ink-soft border-line",
};

function initials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export interface ParticipantListProps {
  participants: CallParticipant[];
}

export function ParticipantList({ participants }: ParticipantListProps) {
  return (
    <section aria-label="Participants" className="rounded-2xl border border-line bg-card p-4">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-faint">
        Participants ({participants.length})
      </h2>
      {participants.length === 0 ? (
        <p className="text-sm text-ink-faint italic">No participants yet.</p>
      ) : (
        <ul className="m-0 flex flex-col gap-2 p-0" style={{ listStyle: "none" }}>
          {participants.map((p) => (
            <li
              key={p.id}
              data-testid={`participant-${p.id}`}
              className="flex items-center gap-3"
            >
              {/* Avatar */}
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-bold"
                style={{
                  backgroundColor: p.role === "wearer" ? "var(--color-watch-soft)"
                    : p.role === "caller" ? "var(--color-family-soft)"
                    : p.role === "family" ? "var(--color-safe-soft)"
                    : "var(--color-line)",
                  color: p.role === "wearer" ? "var(--color-watch)"
                    : p.role === "caller" ? "var(--color-family)"
                    : p.role === "family" ? "var(--color-safe)"
                    : "var(--color-ink-soft)",
                  borderColor: p.role === "wearer" ? "var(--color-watch)"
                    : p.role === "caller" ? "var(--color-family)"
                    : p.role === "family" ? "var(--color-safe)"
                    : "var(--color-line)",
                }}
                aria-hidden="true"
              >
                {initials(p.displayName)}
              </span>

              {/* Name + status */}
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-ink">
                  {p.displayName}
                  {p.local ? " (you)" : ""}
                </span>
                {p.role ? (
                  <span
                    className={cn(
                      "ml-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide border",
                      ROLE_COLORS[p.role] || ROLE_COLORS.unknown
                    )}
                  >
                    {p.role}
                  </span>
                ) : null}
              </div>

              {/* Audio indicator */}
              <span
                aria-label="Audio status"
                className={cn(
                  "inline-flex items-center gap-1.5 text-xs font-medium",
                  p.local
                    ? p.micPublishing
                      ? "text-safe"
                      : "text-ink-faint"
                    : p.audioSubscribed
                      ? "text-safe"
                      : "text-danger"
                )}
              >
                {p.local ? (
                  p.micPublishing ? (
                    <MicOnIcon />
                  ) : (
                    <MicOffIcon />
                  )
                ) : p.audioSubscribed ? (
                  <HearingIcon />
                ) : (
                  <BlockedIcon />
                )}
                {p.local
                  ? p.micPublishing
                    ? "Mic on"
                    : "Mic paused"
                  : p.audioSubscribed
                    ? "Hearing"
                    : "Blocked"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MicOnIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </svg>
  );
}
function MicOffIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.94-.6" />
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </svg>
  );
}
function HearingIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}
function BlockedIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  );
}
