import { STATE_META } from "@/app/_lib/labels";
import type { SessionState, TakeoverStatus } from "@/app/_lib/types";
import { cn } from "./cn";
import { Pulse } from "./Pulse";
import { TONE_SOFT, TONE_TEXT } from "./tones";

export function StatePill({
  state,
  takeover,
  className,
}: {
  state: SessionState;
  takeover?: TakeoverStatus;
  className?: string;
}) {
  const failed = takeover === "failed" && state !== "ended" && state !== "family_joined";
  const meta = STATE_META[state];
  const tone = failed ? "danger" : meta.tone;
  const label = failed ? "Takeover failed" : meta.label;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-current/15 px-3 py-1.5 text-sm font-medium",
        TONE_SOFT[tone],
        TONE_TEXT[tone],
        className,
      )}
    >
      <Pulse tone={tone} still={state === "ended"} size={8} />
      {label}
    </span>
  );
}
