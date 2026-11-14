"use client";

import { CallControls } from "./CallControls";
import { CallStatusBanner } from "./CallStatusBanner";
import { ParticipantList } from "./ParticipantList";
import { TakeoverStatus } from "./TakeoverStatus";
import type { CallSessionView } from "./types";

export interface CallRoomProps {
  view: CallSessionView;
  evidenceQuotes?: string[];
  alertSummary?: string | null;
  joining?: boolean;
  onJoin?: () => void;
  onEndCall?: () => void;
  onReconnectWearer?: () => void;
}

export function CallRoom({
  view,
  evidenceQuotes,
  alertSummary,
  joining,
  onJoin,
  onEndCall,
  onReconnectWearer,
}: CallRoomProps) {
  const canReconnect =
    view.role === "family" &&
    view.familyJoined &&
    view.wearerProtected &&
    !view.wearerReconnected;

  return (
    <div
      data-testid="call-room"
      data-role={view.role}
      className="call-room flex w-full flex-col gap-4 p-5"
    >
      <CallStatusBanner
        status={view.uiStatus}
        fixtureMode={view.fixtureMode}
        detail={view.providerError || view.takeoverError}
      />

      <CallControls
        role={view.role}
        connected={view.connected}
        joining={joining}
        canEnd={view.state !== "ended"}
        canReconnectWearer={canReconnect}
        onJoin={onJoin}
        onEndCall={onEndCall}
        onReconnectWearer={onReconnectWearer}
      />

      <ParticipantList participants={view.participants} />

      <TakeoverStatus
        role={view.role}
        state={view.state}
        callerAudioBlocked={view.callerAudioBlocked}
        wearerMicrophonePaused={view.wearerMicrophonePaused}
        workerReady={view.workerReady}
        wearerProtected={view.wearerProtected}
        takeoverError={view.takeoverError}
        showWearerWarning={view.role === "wearer"}
      />


      {view.role === "caller" ? (
        <p className="text-xs text-ink-faint italic">
          Call status only. Wearer private warnings and evidence are not shown here.
        </p>
      ) : null}
    </div>
  );
}
