"use client";

import type { CallUiStatus } from "./types";
import { Pulse } from "@/components/ui/Pulse";
import { cn } from "@/components/ui/cn";

const LABELS: Record<CallUiStatus, string> = {
  connecting: "Connecting…",
  connected: "Connected",
  monitoring: "Monitoring",
  protection_starting: "Protection starting",
  protected: "Protected",
  ai_assistant_active: "AI assistant active",
  family_alert_sent: "Family alert sent",
  family_joining: "Family joining…",
  family_joined: "Family joined — in control",
  reconnecting_wearer: "Reconnecting wearer…",
  call_ended: "Call ended",
  takeover_failed: "Takeover failed — End Call available",
  provider_error: "Provider error",
  reconnecting: "Reconnecting…",
  local_fixture: "Local Fixture / Demo Replay",
};

const STATUS_TONE: Record<CallUiStatus, "safe" | "watch" | "danger" | "family" | "ai" | "muted"> = {
  connecting: "watch",
  connected: "safe",
  monitoring: "muted",
  protection_starting: "watch",
  protected: "safe",
  ai_assistant_active: "ai",
  family_alert_sent: "family",
  family_joining: "watch",
  family_joined: "family",
  reconnecting_wearer: "watch",
  call_ended: "muted",
  takeover_failed: "danger",
  provider_error: "danger",
  reconnecting: "watch",
  local_fixture: "muted",
};

export interface CallStatusBannerProps {
  status: CallUiStatus;
  fixtureMode?: boolean;
  detail?: string | null;
}

export function CallStatusBanner({
  status,
  fixtureMode,
  detail,
}: CallStatusBannerProps) {
  const label = LABELS[status];
  const tone = STATUS_TONE[status];

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="call-status-banner"
      className={cn(
        "flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold transition-colors",
        tone === "danger" && "border-danger/30 bg-danger-soft text-danger",
        tone === "safe" && "border-safe/30 bg-safe-soft text-safe",
        tone === "watch" && "border-watch/30 bg-watch-soft text-watch",
        tone === "family" && "border-family/30 bg-family-soft text-family",
        tone === "ai" && "border-ai/30 bg-ai-soft text-ai",
        tone === "muted" && "border-line bg-card text-ink-soft"
      )}
    >
      <Pulse tone={tone === "danger" ? "danger" : tone === "safe" ? "safe" : tone === "watch" ? "watch" : tone === "family" ? "family" : tone === "ai" ? "ai" : "muted"} size={8} />
      <span className="flex-1 truncate">{label}</span>

      {fixtureMode && (
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border"
          style={{
            backgroundColor: "var(--color-watch-soft)",
            color: "var(--color-watch)",
            borderColor: "var(--color-watch)",
          }}
        >
          Fixture
        </span>
      )}
    </div>
  );
}
