export type Tone = "safe" | "watch" | "danger" | "family" | "muted" | "ai";

export const TONE_TEXT: Record<Tone, string> = {
  safe: "text-safe",
  watch: "text-watch",
  danger: "text-danger",
  family: "text-family",
  muted: "text-ink-faint",
  ai: "text-ai",
};
export const TONE_BG: Record<Tone, string> = {
  safe: "bg-safe",
  watch: "bg-watch",
  danger: "bg-danger",
  family: "bg-family",
  muted: "bg-ink-faint",
  ai: "bg-ai",
};
export const TONE_SOFT: Record<Tone, string> = {
  safe: "bg-safe-soft",
  watch: "bg-watch-soft",
  danger: "bg-danger-soft",
  family: "bg-family-soft",
  muted: "bg-line/50",
  ai: "bg-ai-soft",
};
