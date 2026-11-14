import { STATE_META, timeOf } from "@/app/_lib/labels";
import type { SessionState, TimelineEntry } from "@/app/_lib/types";
import { cn } from "./cn";
import { Pulse } from "./Pulse";

const ORDER: SessionState[] = ["monitoring", "protecting", "assistant_active", "family_joined", "ended"];

export function StateTimeline({
  state,
  timeline,
  failed,
}: {
  state: SessionState;
  timeline: TimelineEntry[];
  failed?: boolean;
}) {
  const current = ORDER.indexOf(state);
  const at = (s: SessionState) => [...timeline].reverse().find((t) => t.state === s)?.at;

  return (
    <ol className="relative grid grid-cols-5 gap-2" aria-label="Session state timeline">
      {/* Track */}
      <div className="absolute left-[10%] right-[10%] top-[11px] h-px bg-line" aria-hidden />
      <div
        className="absolute left-[10%] top-[11px] h-px bg-champagne/60 transition-all duration-700"
        style={{ width: `${(Math.max(0, current) / (ORDER.length - 1)) * 80}%` }}
        aria-hidden
      />
      {ORDER.map((s, i) => {
        const done = i < current;
        const now = i === current;
        const meta = STATE_META[s];
        const isFail = failed && s === "assistant_active" && current < i + 1;
        return (
          <li key={s} className="relative flex flex-col items-center gap-2 text-center">
            <span
              className={cn(
                "relative z-10 flex h-6 w-6 items-center justify-center rounded-full border bg-card transition",
                done && "border-champagne bg-champagne",
                now && "border-champagne shadow-lg shadow-champagne/10",
                !done && !now && "border-line",
                isFail && "border-danger",
              )}
            >
              {done && (
                <svg viewBox="0 0 16 16" className="h-3 w-3 stroke-action-ink" fill="none" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M3.5 8.5l3 3 6-7" />
                </svg>
              )}
              {now && <Pulse tone={meta.tone} still={s === "ended"} size={8} />}
              {isFail && !now && <span className="text-[11px] font-bold text-danger">!</span>}
            </span>
            <span className={cn("text-[11px] font-medium leading-tight tabular-nums", now ? "text-ink" : done ? "text-ink-soft" : "text-ink-faint", isFail && "text-danger")}>
              {isFail ? "Takeover failed" : meta.label}
            </span>
            <span className="font-mono text-[10px] text-ink-faint tabular-nums">{done || now ? timeOf(at(s)) : ""}</span>
          </li>
        );
      })}
    </ol>
  );
}
