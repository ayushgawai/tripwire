"use client";
import { useEffect, useRef } from "react";
import { SPEAKER_LABEL, timeOf } from "@/app/_lib/labels";
import { highlightSegments } from "@/app/_lib/reducer";
import type { Speaker, Utterance } from "@/app/_lib/types";
import { cn } from "./cn";

const SPEAKER_STYLE: Record<Speaker, { dot: string; name: string; bubble: string }> = {
  caller: { dot: "bg-watch", name: "text-watch", bubble: "bg-card border-line" },
  wearer: { dot: "bg-safe", name: "text-safe", bubble: "bg-card border-line" },
  family: { dot: "bg-family", name: "text-family", bubble: "bg-family-soft border-family/20" },
  assistant: { dot: "bg-ai", name: "text-ai", bubble: "bg-ai-soft border-ai/20" },
  ambient: { dot: "bg-ink-faint", name: "text-ink-soft", bubble: "bg-card border-line" },
};

export function Transcript({
  utterances,
  evidence,
  emptyHint = "Waiting for the first finalized line…",
  className,
  large,
}: {
  utterances: Utterance[];
  evidence?: Map<string, string[]>;
  emptyHint?: string;
  className?: string;
  large?: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [utterances.length]);

  if (!utterances.length) {
    return (
      <div className={cn("flex h-full min-h-40 items-center justify-center text-sm text-ink-faint", className)}>
        <span className="inline-flex items-center gap-2">
          <span className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-faint" style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </span>
          {emptyHint}
        </span>
      </div>
    );
  }

  return (
    <ol className={cn("flex flex-col gap-3 overflow-y-auto pr-1", className)}>
      {utterances.map((u) => {
        const s = SPEAKER_STYLE[u.speaker];
        const quotes = evidence?.get(u.utterance_id) ?? [];
        const flagged = quotes.length > 0;
        return (
          <li key={u.utterance_id} className="animate-rise">
            <div className="mb-1 flex items-center gap-2 text-xs">
              <span className={cn("h-2 w-2 rounded-full", s.dot)} />
              <span className={cn("font-semibold", s.name)}>{SPEAKER_LABEL[u.speaker]}</span>
              {u.speaker === "assistant" && (
                <span className="rounded-full bg-ai/10 px-2 py-px text-[10px] font-semibold uppercase tracking-wider text-ai">
                  AI · excluded from detection
                </span>
              )}
              {flagged && (
                <span className="rounded-full bg-danger/10 px-2 py-px text-[10px] font-semibold uppercase tracking-wider text-danger">
                  Evidence
                </span>
              )}
              <span className="ml-auto font-mono text-[11px] text-ink-faint">{timeOf(u.timestamp)}</span>
            </div>
            <p
              className={cn(
                "rounded-2xl border px-4 py-3 leading-relaxed",
                large ? "text-lg" : "text-[15px]",
                s.bubble,
                flagged && "border-danger/40",
              )}
            >
              {highlightSegments(u.text, quotes).map((seg, i) =>
                seg.hit ? (
                  <mark key={i} className="evidence">
                    {seg.text}
                  </mark>
                ) : (
                  <span key={i}>{seg.text}</span>
                ),
              )}
            </p>
          </li>
        );
      })}
      <div ref={endRef} />
    </ol>
  );
}
