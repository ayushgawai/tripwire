import { cn } from "./cn";
import { TONE_BG, type Tone } from "./tones";

/** A status dot with an expanding ring. `still` disables the ring. */
export function Pulse({ tone, still, size = 10 }: { tone: Tone; still?: boolean; size?: number }) {
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      {!still && (
        <span className={cn("absolute inset-0 rounded-full animate-pulse-ring", TONE_BG[tone])} />
      )}
      <span className={cn("relative inline-flex h-full w-full rounded-full", TONE_BG[tone])} />
    </span>
  );
}
