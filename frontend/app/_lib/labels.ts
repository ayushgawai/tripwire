import type { SessionState, Speaker } from "./types.ts";

const REASONS: Record<string, string> = {
  gift_card_request: "Gift card request",
  urgency: "Urgency pressure",
  secrecy: "Asks for secrecy",
  discourages_verification: "Blocks family check",
  large_amount: "Large amount",
  payment_request: "Payment request",
  impersonation: "Possible impersonation",
  wire_transfer: "Wire transfer",
  crypto_request: "Crypto request",
  personal_info_request: "Asks for personal info",
  threat: "Threat or fear",
};

export function reasonLabel(code: string): string {
  return REASONS[code] ?? code.replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export const SPEAKER_LABEL: Record<Speaker, string> = {
  caller: "Caller",
  wearer: "Wearer",
  family: "Family",
  assistant: "Tripwire AI",
  ambient: "Nearby",
};

export const STATE_META: Record<
  SessionState,
  { label: string; tone: "safe" | "watch" | "danger" | "family" | "muted"; blurb: string }
> = {
  monitoring: { label: "Monitoring", tone: "safe", blurb: "Protection on. Listening for risky patterns." },
  protecting: { label: "Protecting", tone: "watch", blurb: "Pausing the caller and starting the assistant." },
  assistant_active: { label: "Assistant active", tone: "danger", blurb: "Caller is talking to Tripwire. Wearer is protected." },
  family_joined: { label: "Family joined", tone: "family", blurb: "A trusted contact is on the call." },
  ended: { label: "Ended", tone: "muted", blurb: "Session closed. Audio capture stopped." },
};

export function timeOf(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}
