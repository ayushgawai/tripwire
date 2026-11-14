import { reasonLabel } from "@/app/_lib/labels";
import type { RiskDecision, RiskLevel } from "@/app/_lib/types";
import { cn } from "./cn";

const LEVELS: { id: RiskLevel; label: string; tone: string; soft: string }[] = [
  { id: "low", label: "Low", tone: "bg-safe", soft: "text-safe" },
  { id: "review", label: "Review", tone: "bg-watch", soft: "text-watch" },
  { id: "high", label: "High", tone: "bg-danger", soft: "text-danger" },
];

const ACTION_LABEL = { none: "No action", alert: "Alert family", takeover: "Take over call" } as const;

export function RiskMeter({ risk }: { risk: RiskLevel | null }) {
  const idx = risk ? LEVELS.findIndex((l) => l.id === risk) : -1;
  return (
    <div className="grid grid-cols-3 gap-1.5" role="meter" aria-valuetext={risk ?? "none"}>
      {LEVELS.map((l, i) => (
        <div key={l.id} className="flex flex-col gap-1.5">
          <div
            className={cn(
              "h-2.5 rounded-full transition-all duration-500",
              i <= idx ? l.tone : "bg-line",
              i === idx && risk === "high" && "shadow-[0_0_18px_var(--color-danger)]",
            )}
          />
          <span className={cn("text-[11px] font-semibold uppercase tracking-wider", i === idx ? l.soft : "text-ink-faint")}>
            {l.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ReasonChips({ reasons, className }: { reasons: string[]; className?: string }) {
  if (!reasons.length) return null;
  return (
    <ul className={cn("flex flex-wrap gap-1.5", className)}>
      {reasons.map((r) => (
        <li key={r} className="rounded-full border border-danger/25 bg-danger-soft px-2.5 py-1 text-xs font-semibold text-danger">
          {reasonLabel(r)}
        </li>
      ))}
    </ul>
  );
}

export function RiskPanel({ decision, history }: { decision: RiskDecision | null; history?: RiskDecision[] }) {
  if (!decision) {
    return (
      <div className="space-y-4">
        <RiskMeter risk={null} />
        <p className="text-sm text-ink-faint">No decision yet. Caller and wearer final transcripts are analyzed as they arrive.</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <RiskMeter risk={decision.risk} />
      <p className="text-[15px] leading-relaxed text-ink">{decision.summary || "—"}</p>
      <ReasonChips reasons={decision.reasons} />
      <div className="flex items-center justify-between border-t border-line pt-3 text-xs text-ink-faint">
        <span>
          Recommended: <b className="text-ink-soft">{ACTION_LABEL[decision.recommended_action]}</b>
        </span>
        <span className="font-mono">{decision.decision_id}</span>
      </div>
      {history && history.length > 1 && (
        <ol className="flex flex-wrap gap-1.5 text-[11px] text-ink-faint">
          {history.map((d) => (
            <li key={d.decision_id} className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 py-0.5 font-mono">
              <span className={cn("h-1.5 w-1.5 rounded-full", d.risk === "high" ? "bg-danger" : d.risk === "review" ? "bg-watch" : "bg-safe")} />
              {d.risk}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
