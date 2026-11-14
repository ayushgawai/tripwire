import type { ConnectionStatus } from "@/app/_lib/useSession";
import { cn } from "./cn";
import { Pulse } from "./Pulse";

const META: Record<ConnectionStatus, { label: string; tone: "safe" | "watch" | "danger" | "muted" | "ai" }> = {
  idle: { label: "Not connected", tone: "muted" },
  connecting: { label: "Connecting", tone: "watch" },
  live: { label: "Live", tone: "safe" },
  reconnecting: { label: "Reconnecting", tone: "watch" },
  offline: { label: "Offline", tone: "danger" },
  replay: { label: "Demo replay", tone: "ai" },
};

export function ConnectionBadge({ status, className }: { status: ConnectionStatus; className?: string }) {
  const m = META[status];
  return (
    <span
      title={status === "replay" ? "Local fixture replay — not live inference" : undefined}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 text-xs font-semibold uppercase tracking-wider text-ink-soft",
        status === "replay" && "border-ai/40 text-ai",
        className,
      )}
    >
      <Pulse tone={m.tone} still={status === "offline" || status === "idle"} size={7} />
      {m.label}
    </span>
  );
}
