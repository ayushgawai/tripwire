/**
 * Selective audio routing helpers (verified Daily behavior).
 *
 * GENUINE capability: wearer unsubscribes from caller audio via
 * setSubscribedTracks; wearer pauses mic via setLocalAudio(false).
 * Do NOT globally mute the caller — the AI must still hear them.
 */

import type { CallProviderClient, RoutingConfirmationPayload } from "../types";

export interface ApplyProtectionRoutingArgs {
  client: CallProviderClient;
  sessionId: string;
  callerParticipantId: string;
}

export async function applyWearerProtectionRouting(
  args: ApplyProtectionRoutingArgs
): Promise<RoutingConfirmationPayload> {
  const { client, sessionId, callerParticipantId } = args;
  if (!callerParticipantId) {
    throw new Error("callerParticipantId required for selective routing");
  }
  // Receive-side: stop hearing caller (caller still publishes for AI).
  await client.setRemoteAudioSubscribed(callerParticipantId, false);
  // Send-side: pause wearer mic toward everyone (including caller).
  await client.setMicEnabled(false);

  return {
    session_id: sessionId,
    caller_audio_blocked: true,
    wearer_microphone_paused: true,
    timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  };
}

export async function restoreWearerAudioAfterExplicitReconnect(
  client: CallProviderClient,
  callerParticipantId: string | null
): Promise<void> {
  await client.setMicEnabled(true);
  if (callerParticipantId) {
    await client.setRemoteAudioSubscribed(callerParticipantId, true);
  }
}

/** Map session state → demo-readable UI status (not color-only). */
export function deriveUiStatus(input: {
  state: string;
  connected: boolean;
  connecting?: boolean;
  fixtureMode?: boolean;
  familyAlertSent?: boolean;
  takeoverFailed?: boolean;
  providerError?: string | null;
  reconnecting?: boolean;
}): import("../types").CallUiStatus {
  if (input.providerError) return "provider_error";
  if (input.takeoverFailed) return "takeover_failed";
  if (input.reconnecting) return "reconnecting";
  if (input.connecting) return "connecting";
  if (input.state === "ended") return "call_ended";
  if (input.state === "family_joined") return "family_joined";
  if (input.familyAlertSent && input.state === "assistant_active") {
    return "family_alert_sent";
  }
  if (input.state === "assistant_active") return "ai_assistant_active";
  if (input.state === "protecting") return "protection_starting";
  if (!input.connected) return "connecting";
  if (input.fixtureMode && input.state === "monitoring") return "local_fixture";
  if (input.state === "monitoring") return "monitoring";
  return "connected";
}
