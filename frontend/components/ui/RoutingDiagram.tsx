// Visualizes audio routing as *reported by backend state*. It is a picture of state, not proof of
// routing — the plan is explicit that "a different color on a dashboard is not takeover".
import type { SessionView } from "@/app/_lib/types";
import { cn } from "./cn";

type Link = {
  from: [number, number];
  to: [number, number];
  on: boolean;
  tone: string;
  dashed?: boolean;
  severed?: boolean;
};

export function RoutingDiagram({ view }: { view: SessionView }) {
  const s = view.state;
  const confirmed = view.takeover === "active";
  const protectedWearer = confirmed && (s === "assistant_active" || (s === "family_joined" && !view.wearerReconnected));
  const ai = s === "assistant_active";
  const fam = s === "family_joined";
  const ended = s === "ended";
  const takeoverStarting = view.takeover === "starting";

  // Node positions — wide layout for hero presence
  const N = {
    caller: [55, 100],
    wearer: [280, 40],
    ai: [280, 150],
    family: [175, 190],
  } as Record<string, [number, number]>;

  const links: Link[] = [
    {
      from: N.caller,
      to: N.wearer,
      on: !ended && !protectedWearer,
      tone: "var(--color-caller)",
      severed: protectedWearer || takeoverStarting,
    },
    {
      from: N.caller,
      to: N.ai,
      on: !ended && ai,
      tone: "var(--color-cyan)",
    },
    {
      from: N.caller,
      to: N.family,
      on: !ended && fam,
      tone: "var(--color-violet)",
    },
    {
      from: N.family,
      to: N.wearer,
      on: !ended && fam && view.wearerReconnected,
      tone: "var(--color-violet)",
    },
  ];

  const mid = (a: [number, number], b: [number, number]) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] as [number, number];

  return (
    <div className="relative">
      <svg viewBox="0 0 340 236" className="w-full" aria-label="Audio routing diagram">
        <defs>
          {/* Glow filter for active links */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Traveling pulse marker */}
          <marker id="pulse-dot" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="6" markerHeight="6">
            <circle cx="3" cy="3" r="2.5" fill="currentColor" opacity="0.9" />
          </marker>
        </defs>

        {/* Links */}
        {links.map((l, i) => {
          if (l.severed) {
            // Severed link: red break with glitch flicker
            const [mx, my] = mid(l.from, l.to);
            return (
              <g key={i}>
                {/* Dim ghost of original link */}
                <line
                  x1={l.from[0]} y1={l.from[1]} x2={l.to[0]} y2={l.to[1]}
                  stroke="var(--color-line)"
                  strokeWidth="1.5"
                  strokeDasharray="3 5"
                  opacity="0.5"
                />
                {/* Left half */}
                <line
                  x1={l.from[0]} y1={l.from[1]} x2={mx - 4} y2={my}
                  stroke="var(--color-danger)"
                  strokeWidth="1.25"
                  strokeLinecap="round"
                  opacity="0.5"
                />
                {/* Right half */}
                <line
                  x1={mx + 4} y1={my} x2={l.to[0]} y2={l.to[1]}
                  stroke="var(--color-danger)"
                  strokeWidth="1.25"
                  strokeLinecap="round"
                  opacity="0.5"
                />
                {/* Glitch X at break point */}
                <g transform={`translate(${mx}, ${my})`} className="routing-cut">
                  <circle r="11" fill="var(--color-danger-soft)" stroke="var(--color-danger)" strokeWidth="0.75" />
                  <line x1="-6" y1="-6" x2="6" y2="6" stroke="var(--color-danger)" strokeWidth="1.25" strokeLinecap="round" />
                  <line x1="6" y1="-6" x2="-6" y2="6" stroke="var(--color-danger)" strokeWidth="1.25" strokeLinecap="round" />
                </g>
              </g>
            );
          }

          if (!l.on) {
            // Inactive link — faint hairline
            return (
              <line
                key={i}
                x1={l.from[0]} y1={l.from[1]} x2={l.to[0]} y2={l.to[1]}
                stroke="var(--color-line)"
                strokeWidth="1"
                strokeDasharray="2 8"
              />
            );
          }

          // Active link with traveling pulse
          return (
            <g key={i}>
              <line
                x1={l.from[0]} y1={l.from[1]} x2={l.to[0]} y2={l.to[1]}
                stroke={l.tone}
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeDasharray="8 12"
                className="animate-pulse-travel"
                opacity="0.35"
              />
              <line
                x1={l.from[0]} y1={l.from[1]} x2={l.to[0]} y2={l.to[1]}
                stroke={l.tone}
                strokeWidth="1.25"
                strokeLinecap="round"
                filter="url(#glow)"
                opacity="0.9"
              />
            </g>
          );
        })}

        {/* Nodes */}
        <Node at={N.caller} label="Caller" tone="var(--color-caller)" active={!ended} icon="call" />
        <Node at={N.wearer} label="Wearer" tone="var(--color-safe)" active={!ended} muted={protectedWearer} />
        <Node at={N.ai} label="Tripwire AI" tone="var(--color-cyan)" active={ai} />
        <Node at={N.family} label="Family" tone="var(--color-violet)" active={fam} />
      </svg>

      <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
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

function Node({
  at,
  label,
  tone,
  active,
  muted,
  icon,
}: {
  at: [number, number];
  label: string;
  tone: string;
  active: boolean;
  muted?: boolean;
  icon?: string;
}) {
  return (
    <g transform={`translate(${at[0]}, ${at[1]})`} opacity={active ? 1 : 0.3}>
      {/* Outer ring */}
      <circle r="25" fill={tone} opacity="0.10" filter="url(#glow)" />
      <circle r="20" fill="none" stroke={tone} strokeWidth="0.6" opacity="0.35" />
      {/* Inner fill */}
      <circle r="13" fill={tone} opacity={muted ? "0.5" : "0.9"} />
      {icon === "call" && (
        <path
          d="M-4 -2 Q0 -6 4 -2 Q7 1 4 5 Q0 9 -4 5 Q-7 1 -4 -2"
          fill="none"
          stroke="var(--color-paper)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      )}
      {icon === "ai" && (
        <text
          y="1"
          textAnchor="middle"
          fill="var(--color-paper)"
          fontSize="9"
          fontFamily="var(--font-mono)"
          fontWeight="700"
        >
          AI
        </text>
      )}
      {icon === "family" && (
        <text
          y="1"
          textAnchor="middle"
          fill="var(--color-paper)"
          fontSize="8"
          fontFamily="var(--font-mono)"
          fontWeight="700"
        >
          F
        </text>
      )}
      {icon === "wearer" && (
        <text
          y="1"
          textAnchor="middle"
          fill="var(--color-paper)"
          fontSize="9"
          fontFamily="var(--font-mono)"
          fontWeight="700"
        >
          W
        </text>
      )}
      {/* Label */}
      <text
        y="36"
        textAnchor="middle"
        className="fill-ink text-[11px] font-semibold"
        fontFamily="var(--font-sans)"
      >
        {label}
      </text>
      {muted && (
        <text
          y="50"
          textAnchor="middle"
          className="fill-danger text-[9px] font-bold"
          fontFamily="var(--font-mono)"
        >
          protected
        </text>
      )}
    </g>
  );
}
