"use client";
import { useEffect, useRef, useState } from "react";
import { SPEAKER_LABEL, timeOf } from "@/app/_lib/labels";
import { highlightSegments } from "@/app/_lib/reducer";
import type { Speaker, Utterance } from "@/app/_lib/types";
import { cn } from "./cn";

const SPEAKER_STYLE: Record<Speaker, { dot: string; name: string; bubble: string }> = {
  caller: { dot: "bg-caller", name: "text-caller", bubble: "bg-card border-line" },
  wearer: { dot: "bg-safe", name: "text-safe", bubble: "bg-card border-line" },
  family: { dot: "bg-violet", name: "text-violet", bubble: "bg-violet-soft/50 border-violet/20" },
  assistant: { dot: "bg-cyan", name: "text-cyan", bubble: "bg-cyan-soft/50 border-cyan/20" },
  ambient: { dot: "bg-ink-faint", name: "text-ink-soft", bubble: "bg-card border-line" },
};

/** Live level meter — animated bars next to the active speaker */
function LevelMeter({ speaker, active }: { speaker: Speaker; active: boolean }) {
  const bars = 4;
  return (
    <span className="inline-flex items-end gap-[2px] h-3.5 shrink-0" aria-hidden="true">
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "w-[3px] rounded-full bg-ink-faint transition-all duration-150",
            active && "animate-meter",
            active && SPEAKER_STYLE[speaker].dot.replace("bg-", "bg-"),
          )}
          style={{
            height: `${6 + i * 2}px`,
            animationDelay: active ? `${i * 80}ms` : undefined,
          }}
        />
      ))}
    </span>
  );
}

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
  const prevLenRef = useRef(0);
  const [lastSpeaker, setLastSpeaker] = useState<Speaker | null>(null);
  const [liveKey, setLiveKey] = useState(0);

  useEffect(() => {
    if (utterances.length > prevLenRef.current) {
      setLastSpeaker(utterances[utterances.length - 1]?.speaker ?? null);
      setLiveKey((k) => k + 1);
    }
    prevLenRef.current = utterances.length;
  }, [utterances]);

  useEffect(() => {
    // Scroll only the transcript list; scrollIntoView would also scroll the page.
    const box = endRef.current?.parentElement;
    box?.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
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
    <ol className={cn("flex flex-col gap-2.5 overflow-y-auto pr-1", className)}>
      {utterances.map((u, idx) => {
        const s = SPEAKER_STYLE[u.speaker];
        const quotes = evidence?.get(u.utterance_id) ?? [];
        const flagged = quotes.length > 0;
        const isLast = idx === utterances.length - 1;
        const seq = utterances.slice(0, idx + 1).filter((x) => x.speaker === u.speaker).length;

        return (
          <li
            key={u.utterance_id}
            className={cn(isLast && "animate-scan-in")}
            style={isLast ? { animationDelay: "0ms" } : undefined}
          >
            <div className="mb-1 flex items-center gap-2 text-xs tabular-nums">
              {isLast ? (
                <LevelMeter speaker={u.speaker} active={lastSpeaker === u.speaker} />
              ) : (
                <span className="h-3.5 w-[3px] shrink-0" />
              )}
              <span className={cn("h-2 w-2 rounded-full shrink-0", s.dot)} />
              <span className={cn("font-semibold", s.name)}>
                {SPEAKER_LABEL[u.speaker]}
                {u.speaker === "assistant" && (
                  <span className="ml-1.5 text-[9px] font-semibold uppercase tracking-wider opacity-70">AI</span>
                )}
              </span>
              <span className="font-mono text-[10px] text-ink-faint ml-0.5">#{String(seq).padStart(2, "0")}</span>
              {flagged && (
                <span className="rounded-full bg-danger/10 px-2 py-px text-[9px] font-semibold uppercase tracking-wider text-danger">
                  Evidence
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-ink-faint">{timeOf(u.timestamp)}</span>
            </div>
            <p
              className={cn(
                "rounded-xl border px-3.5 py-2.5 leading-relaxed",
                large ? "text-base" : "text-[13px]",
                s.bubble,
                flagged && "border-danger/30",
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
