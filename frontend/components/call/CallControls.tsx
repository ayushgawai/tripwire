"use client";

import { Button } from "@/components/ui/Button";

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
      className="flex flex-wrap items-center gap-3"
    >
      {!connected ? (
        <Button
          variant="primary"
          size="xl"
          onClick={onJoin}
          disabled={joining}
          aria-label={`Join call as ${role}`}
          className="min-w-[10rem]"
        >
          {joining ? "Joining…" : "Join call"}
        </Button>
      ) : null}
      {canEnd ? (
        <Button
          variant="outline"
          size="lg"
          onClick={onEndCall}
          aria-label="End call"
        >
          End Call
        </Button>
      ) : null}
      {canReconnectWearer ? (
        <Button
          variant="ghost"
          size="md"
          onClick={onReconnectWearer}
          aria-label="Explicitly reconnect wearer audio"
        >
          Reconnect Wearer
        </Button>
      ) : null}
    </div>
  );
}
