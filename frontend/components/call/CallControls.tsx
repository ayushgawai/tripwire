"use client";

export interface CallControlsProps {
  role: "caller" | "wearer" | "family";
  connected: boolean;
  canEnd?: boolean;
  canReconnectWearer?: boolean;
  onJoin?: () => void;
  onEndCall?: () => void;
  onReconnectWearer?: () => void;
  joining?: boolean;
}

export function CallControls({
  role,
  connected,
  canEnd = true,
  canReconnectWearer = false,
  onJoin,
  onEndCall,
  onReconnectWearer,
  joining,
}: CallControlsProps) {
  return (
    <div
      role="group"
      aria-label="Call controls"
      style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}
    >
      {!connected ? (
        <button
          type="button"
          onClick={onJoin}
          disabled={joining}
          aria-label={`Join call as ${role}`}
        >
          {joining ? "Joining…" : "Join call"}
        </button>
      ) : null}
      {canEnd ? (
        <button type="button" onClick={onEndCall} aria-label="End call">
          End Call
        </button>
      ) : null}
      {role === "wearer" && canReconnectWearer ? (
        <button
          type="button"
          onClick={onReconnectWearer}
          aria-label="Explicitly reconnect wearer audio"
        >
          Reconnect Wearer
        </button>
      ) : null}
    </div>
  );
}
