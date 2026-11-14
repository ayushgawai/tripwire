// Visualizes audio routing as *reported by backend state*. It is a picture of state, not proof of
// routing — the plan is explicit that "a different color on a dashboard is not takeover".
import type { SessionView } from "@/app/_lib/types";
import { cn } from "./cn";

type Link = { from: [number, number]; to: [number, number]; on: boolean; tone: string; dashed?: boolean };

export function RoutingDiagram({ view }: { view: SessionView }) {
  const s = view.state;
  const confirmed = view.takeover === "active";
  const protectedWearer = confirmed && (s === "assistant_active" || (s === "family_joined" && !view.wearerReconnected));
  const ai = s === "assistant_active";
  const fam = s === "family_joined";
  const ended = s === "ended";

  const N = { caller: [60, 90], wearer: [300, 40], ai: [300, 140], family: [180, 168] } as Record<string, [number, number]>;
  const links: Link[] = [
    { from: N.caller, to: N.wearer, on: !ended && !protectedWearer, tone: "stroke-safe" },
    { from: N.caller, to: N.ai, on: !ended && ai, tone: "stroke-ai" },
    { from: N.caller, to: N.family, on: !ended && fam, tone: "stroke-family" },
    { from: N.family, to: N.wearer, on: !ended && fam && view.wearerReconnected, tone: "stroke-family" },
  ];

  return (
    <div className="relative">
      <svg viewBox="0 0 360 232" className="w-full">
        {links.map((l, i) => (
          <line
            key={i}
            x1={l.from[0]} y1={l.from[1]} x2={l.to[0]} y2={l.to[1]}
            strokeWidth={l.on ? 3 : 2}
            strokeLinecap="round"
            strokeDasharray={l.on ? "6 6" : "2 7"}
            className={cn(l.on ? l.tone : "stroke-line", "transition-all duration-500")}
            style={l.on ? { animation: "dash 0.9s linear infinite" } : undefined}
          />
        ))}
        {protectedWearer && (
          <g transform={`translate(${(N.caller[0] + N.wearer[0]) / 2}, ${(N.caller[1] + N.wearer[1]) / 2})`}>
            <circle r="13" className="fill-danger" />
            <path d="M-5 -5 L5 5 M5 -5 L-5 5" className="stroke-white" strokeWidth="2.5" strokeLinecap="round" />
          </g>
        )}
        <Node at={N.caller} label="Caller" tone="fill-watch" active={!ended} />
        <Node at={N.wearer} label="Wearer" tone="fill-safe" active={!ended} muted={protectedWearer} />
        <Node at={N.ai} label="Tripwire AI" tone="fill-ai" active={ai} />
        <Node at={N.family} label="Family" tone="fill-family" active={fam} />
        <style>{`@keyframes dash { to { stroke-dashoffset: -12; } }`}</style>
      </svg>
      <p className="mt-1 text-[11px] text-ink-faint">
        {view.takeover === "starting"
          ? "Takeover requested — waiting for wearer client to confirm caller audio is blocked."
          : view.takeover === "failed"
            ? "Takeover failed — routing unchanged. Offer End call."
            : protectedWearer
              ? "Confirmed by backend: caller audio blocked for wearer."
              : "Routing as reported by backend events."}
      </p>
    </div>
  );
}

function Node({ at, label, tone, active, muted }: { at: [number, number]; label: string; tone: string; active: boolean; muted?: boolean }) {
  return (
    <g transform={`translate(${at[0]}, ${at[1]})`} className="transition-opacity duration-500" opacity={active ? 1 : 0.35}>
      <circle r="20" className={cn(tone)} opacity="0.18" />
      <circle r="11" className={tone} />
      <text y="36" textAnchor="middle" className="fill-ink text-[12px] font-semibold">{label}</text>
      {muted && <text y="50" textAnchor="middle" className="fill-danger text-[10px] font-bold uppercase">protected</text>}
    </g>
  );
}
