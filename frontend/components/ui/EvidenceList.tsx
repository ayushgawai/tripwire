import { SPEAKER_LABEL, timeOf } from "@/app/_lib/labels";
import type { Evidence, Utterance } from "@/app/_lib/types";
import { cn } from "./cn";

/**
 * Quoted evidence with speaker attribution. A quote is only shown as verified when it actually
 * occurs in the referenced utterance (contract: "verify every evidence quote occurs").
 */
export function EvidenceList({
  evidence,
  transcript,
  large,
  className,
}: {
  evidence: Evidence[];
  transcript: Utterance[];
  large?: boolean;
  className?: string;
}) {
  if (!evidence.length) return <p className="text-sm text-ink-faint">No quoted evidence.</p>;
  return (
    <ul className={cn("space-y-3", className)}>
      {evidence.map((e, i) => {
        const u = transcript.find((t) => t.utterance_id === e.utterance_id);
        const verified = !!u && u.text.toLowerCase().includes(e.quote.toLowerCase());
        return (
          <li key={`${e.utterance_id}-${i}`} className="animate-rise" style={{ animationDelay: `${i * 90}ms` }}>
            <blockquote
              className={cn(
                "relative rounded-r-2xl border-l border-danger bg-danger-soft/70 py-3 pl-4 pr-4 font-display text-ink",
                large ? "text-2xl leading-snug" : "text-2xl leading-snug",
              )}
            >
              “{e.quote}”
            </blockquote>
            <div className="mt-1.5 flex items-center gap-2 pl-1 text-xs text-ink-faint">
              <span className="font-semibold text-ink-soft">{u ? SPEAKER_LABEL[u.speaker] : "Unknown speaker"}</span>
              {u?.timestamp && <span>· {timeOf(u.timestamp)}</span>}
              <span
                className={cn("ml-auto rounded-full px-2 py-px text-[10px] font-semibold uppercase tracking-wider",
                  verified ? "bg-safe-soft text-safe" : "bg-watch-soft text-watch")}
                title={verified ? "Quote found verbatim in the transcript" : "Quote not found in the local transcript yet"}
              >
                {verified ? "Verbatim" : "Unverified"}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
