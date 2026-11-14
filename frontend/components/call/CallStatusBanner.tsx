"use client";

import type { CallUiStatus } from "./types";

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
  const tone =
    status === "takeover_failed" || status === "provider_error"
      ? "danger"
      : status === "protected" ||
          status === "ai_assistant_active" ||
          status === "family_joined"
        ? "protect"
        : status === "local_fixture"
          ? "fixture"
          : "neutral";

  return (
    <div
      role="status"
      aria-live="polite"
      data-tone={tone}
      data-testid="call-status-banner"
      style={{
        border: "2px solid currentColor",
        padding: "0.75rem 1rem",
        borderRadius: "0.25rem",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        fontWeight: 700,
        letterSpacing: "0.01em",
      }}
    >
      <div style={{ fontSize: "1.1rem" }}>{label}</div>
      {fixtureMode ? (
        <div style={{ fontWeight: 600, marginTop: "0.25rem" }}>
          Mode: Local Fixture (not live Daily)
        </div>
      ) : null}
      {detail ? (
        <div style={{ fontWeight: 500, marginTop: "0.35rem" }}>{detail}</div>
      ) : null}
    </div>
  );
}
