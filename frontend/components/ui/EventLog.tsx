"use client";
import { timeOf } from "@/app/_lib/labels";
import type { EventEnvelope } from "@/app/_lib/types";
import { cn } from "./cn";

const TYPE_TONE: Record<string, string> = {
  "transcript.final": "text-ink-soft",
  "risk.updated": "text-watch",
  "takeover.started": "text-watch",
  "takeover.active": "text-danger",
  "takeover.failed": "text-danger",
  "family.alert": "text-family",
  "family.joined": "text-family",
  "session.ended": "text-ink-faint",
  error: "text-danger",
};

export function EventLog({ events, className }: { events: EventEnvelope[]; className?: string }) {
  return (
    <ol className={cn("space-y-1 overflow-y-auto font-mono text-[11px]", className)}>
      {events.length === 0 && <li className="text-ink-faint">No events yet.</li>}
      {[...events].reverse().map((e) => (
        <li key={e.event_id} className="flex gap-2 whitespace-nowrap">
          <span className="w-7 shrink-0 text-right text-ink-faint">#{e.sequence}</span>
          <span className="w-16 shrink-0 text-ink-faint">{timeOf(e.timestamp)}</span>
          <span className={cn("font-semibold", TYPE_TONE[e.type] ?? "text-ink")}>{e.type}</span>
          <span className="truncate text-ink-faint">{summarize(e)}</span>
        </li>
      ))}
    </ol>
  );
}

function summarize(e: EventEnvelope): string {
  const p = e.payload as Record<string, unknown>;
  if (e.type === "transcript.final") return `${p.speaker}: ${p.text}`;
  if (e.type === "risk.updated") return `${p.risk} → ${p.recommended_action}`;
  if (e.type === "takeover.failed") return String(p.reason ?? p.message ?? "");
  if (e.type === "error") return String(p.message ?? "");
  return "";
}
