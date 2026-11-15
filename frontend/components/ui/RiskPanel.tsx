import { reasonLabel } from "@/app/_lib/labels";
import type { RiskDecision, RiskLevel } from "@/app/_lib/types";
import { cn } from "./cn";

const LEVELS: { id: RiskLevel; label: string; tone: string }[] = [
  { id: "low", label: "Low", tone: "bg-safe" },
  { id: "review", label: "Review", tone: "bg-watch" },
  { id: "high", label: "High", tone: "bg-danger" },
];

const ACTION_LABEL = { none: "No action", alert: "Alert family", takeover: "Take over call" } as const;

/** Horizontal threat gauge that animates on mount (keyed by decision ID for re-animation). */
export function ThreatGauge({ risk }: { risk: RiskLevel | null }) {
  const idx = risk ? LEVELS.findIndex((l) => l.id === risk) : -1;
  return (
    <div className="relative h-3 w-full rounded-full bg-line overflow-hidden" role="meter" aria-valuetext={risk ?? "none"}>
      {/* Background segments */}
      <div className="absolute inset-0 flex">
        {LEVELS.map((l, i) => (
          <div key={l.id} className={cn("flex-1 border-r border-paper/20 last:border-r-0", l.tone, "opacity-15")} />
        ))}
      </div>
      {/* Animated fill */}
      <div
        className="absolute inset-y-0 left-0 rounded-full animate-gauge-fill"
        style={{
          width: risk ? `${((idx + 1) / LEVELS.length) * 100}%` : "0%",
          backgroundColor:
            risk === "high"
              ? "var(--color-danger)"
              : risk === "review"
                ? "var(--color-watch)"
                : risk === "low"
                  ? "var(--color-safe)"
                  : "transparent",
          boxShadow: risk === "high" ? "0 0 18px var(--color-danger)" : "none",
        }}
      />
      {/* Tick marks */}
      <div className="absolute inset-0 flex px-px">
        {LEVELS.map((l, i) => (
          <div key={l.id} className="flex-1 border-r border-paper/30 last:border-r-0" />
        ))}
      </div>
      {/* Level label overlay */}
      {risk && (
        <span
          className={cn(
            "absolute inset-y-0 flex items-center justify-end pr-2 text-[10px] font-bold uppercase tracking-wider",
            risk === "high" ? "text-danger" : risk === "review" ? "text-watch" : "text-safe",
          )}
        >
          {LEVELS[idx].label}
        </span>
      )}
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
        <ThreatGauge risk={null} />
        <p className="text-sm text-ink-faint">No decision yet. Caller and wearer final transcripts are analyzed as they arrive.</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {/* Key forces re-mount so the gauge animates on each new decision */}
      <ThreatGauge key={decision.decision_id} risk={decision.risk} />
      <p className="text-[15px] leading-relaxed text-ink">{decision.summary || "—"}</p>
      <ReasonChips reasons={decision.reasons} />
      <GeminiDecisionLine gd={(decision as { gemini_decision?: GeminiDecision }).gemini_decision} />
      <div className="flex items-center justify-between border-t border-line pt-3 text-xs text-ink-faint tabular-nums">
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

type GeminiDecision = { p_scam: number; action: string; confidence: number; latency_ms: number };

/** Calibrated scam probability from Gemini Decision 1 (Gemini Decisions API), shown next to the rules. */
function GeminiDecisionLine({ gd }: { gd?: GeminiDecision }) {
  if (!gd) return null;
  const pct = Math.round(gd.p_scam * 100);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line px-3 py-2 text-xs text-ink-soft tabular-nums">
      <span className="font-semibold text-ink">Gemini Decision 1</span>
      <span className={cn("font-semibold", pct >= 90 ? "text-danger" : pct >= 50 ? "text-watch" : "text-safe")}>{pct}% scam</span>
      <span>suggests {gd.action}</span>
      <span className="font-mono text-ink-faint">{gd.latency_ms} ms</span>
    </div>
  );
}
