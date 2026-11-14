"use client";

import { cn } from "@/components/ui/cn";

export interface FamilyJoinPanelProps {
  alertSummary?: string | null;
  evidenceQuotes?: string[];
  joining?: boolean;
  joined?: boolean;
  familyInControl?: boolean;
  onJoin?: () => void;
}

export function FamilyJoinPanel({
  alertSummary,
  evidenceQuotes = [],
  joining,
  joined,
  familyInControl,
  onJoin,
}: FamilyJoinPanelProps) {
  return (
    <section aria-label="Family join" data-testid="family-join-panel" className="rounded-2xl border border-line bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="inline-flex h-2 w-2 rounded-full bg-safe" aria-hidden="true" />
        <h2 className="text-xs font-medium uppercase tracking-wider text-ink-faint">Family alert</h2>
      </div>

      <p className="text-sm leading-relaxed text-ink-soft">
        {alertSummary ??
          "Tripwire paused a call for family verification. Review evidence, then join."}
      </p>

      {evidenceQuotes.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wider text-ink-faint">Evidence</p>
          <ul className="mt-1.5 m-0 flex flex-col gap-1.5 p-0" style={{ listStyle: "none" }}>
            {evidenceQuotes.map((q) => (
              <li key={q} className="rounded-lg bg-line/50 px-3 py-1.5 text-sm text-ink italic">
                &ldquo;{q}&rdquo;
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-xs text-ink-faint italic">
          Evidence will appear here when the backend supplies quoted statements.
        </p>
      )}

      {/* Status chip */}
      <div className="mt-3">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
            familyInControl
              ? "bg-safe-soft text-safe"
              : joined
                ? "bg-watch-soft text-watch"
                : joining
                  ? "bg-watch-soft text-watch"
                  : "bg-line/60 text-ink-faint"
          )}
        >
          {familyInControl ? (
            <span className="h-1.5 w-1.5 rounded-full bg-safe" aria-hidden="true" />
          ) : joined ? (
            <span className="h-1.5 w-1.5 rounded-full bg-watch" aria-hidden="true" />
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-ink-faint" aria-hidden="true" />
          )}
          {familyInControl
            ? "Family in control"
            : joined
              ? "Joined — confirming control"
              : joining
                ? "Joining…"
                : "Not joined"}
        </span>
      </div>

      {/* Join button */}
      {!joined ? (
        <button
          type="button"
          onClick={onJoin}
          disabled={joining}
          className="mt-4 inline-flex min-w-[8rem] select-none items-center justify-center gap-2 rounded-xl bg-safe px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-safe/30 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {joining ? "Joining…" : "Join call"}
        </button>
      ) : (
        <p className="mt-3 text-sm text-ink-soft">
          You are in the call. AI assistant speech has stopped.
        </p>
      )}
    </section>
  );
}
