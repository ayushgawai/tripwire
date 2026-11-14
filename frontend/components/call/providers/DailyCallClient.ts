/**
 * Daily browser adapter (@daily-co/daily-js ^0.95).
 *
 * Verified methods:
 * - Daily.createCallObject({ subscribeToTracksAutomatically: false })
 * - join({ url, token })
 * - updateParticipant(id, { setSubscribedTracks: { audio } })
 * - setLocalAudio(enabled)
 * - events: participant-joined, participant-left, error
 *
 * Never log meeting tokens.
 */

import type {
  CallParticipant,
  CallProviderClient,
  ProviderCredentials,
  Role,
} from "../types";

type DailyFactory = {
  createCallObject: (opts?: Record<string, unknown>) => DailyCallLike;
};

type DailyCallLike = {
  join: (opts: { url: string; token: string; userName?: string }) => Promise<unknown>;
  leave: () => Promise<unknown>;
  destroy: () => Promise<unknown>;
  setLocalAudio: (enabled: boolean) => unknown;
  updateParticipant: (
    id: string,
    updates: { setSubscribedTracks?: { audio?: boolean } }
  ) => unknown;
  participants: () => Record<string, DailyParticipantLike>;
  on: (event: string, handler: (...args: unknown[]) => void) => DailyCallLike;
  off: (event: string, handler: (...args: unknown[]) => void) => DailyCallLike;
};

type DailyParticipantLike = {
  session_id: string;
  user_id?: string;
  user_name?: string;
  local: boolean;
  tracks?: { audio?: { subscribed?: boolean; state?: string } };
};

function mapRole(userId?: string, userName?: string): CallParticipant["role"] {
  const blob = `${userId ?? ""} ${userName ?? ""}`.toLowerCase();
  if (blob.includes("caller")) return "caller";
  if (blob.includes("wearer")) return "wearer";
  if (blob.includes("family")) return "family";
  if (blob.includes("asst") || blob.includes("assistant")) return "assistant";
  return "unknown";
}

export class DailyCallClient implements CallProviderClient {
  readonly name = "daily";
  readonly fixtureMode = false;

  private call: DailyCallLike | null = null;
  private joinHandlers: Array<(p: CallParticipant) => void> = [];
  private leaveHandlers: Array<(p: CallParticipant) => void> = [];
  private errorHandlers: Array<(m: string) => void> = [];
  private boundJoined: ((ev: unknown) => void) | null = null;
  private boundLeft: ((ev: unknown) => void) | null = null;
  private boundError: ((ev: unknown) => void) | null = null;

  private async loadDaily(): Promise<DailyFactory> {
    const mod = await import("@daily-co/daily-js");
    return (mod.default ?? mod) as DailyFactory;
  }

  async connect(credentials: ProviderCredentials): Promise<void> {
    if (credentials.provider === "mock" || credentials.fixture_mode) {
      throw new Error(
        "DailyCallClient refused mock/fixture credentials — use MockCallClient"
      );
    }
    const Daily = await this.loadDaily();
    this.call = Daily.createCallObject({
      subscribeToTracksAutomatically: false,
      audioSource: true,
      videoSource: false,
    });

    this.boundJoined = (ev: unknown) => {
      const participant = (ev as { participant?: DailyParticipantLike }).participant;
      if (!participant) return;
      for (const h of this.joinHandlers) h(this.toParticipant(participant));
    };
    this.boundLeft = (ev: unknown) => {
      const participant = (ev as { participant?: DailyParticipantLike }).participant;
      if (!participant) return;
      for (const h of this.leaveHandlers) h(this.toParticipant(participant));
    };
    this.boundError = (ev: unknown) => {
      const msg =
        (ev as { errorMsg?: string }).errorMsg ?? "Daily provider error";
      for (const h of this.errorHandlers) h(msg);
    };
    this.call.on("participant-joined", this.boundJoined);
    this.call.on("participant-left", this.boundLeft);
    this.call.on("error", this.boundError);

    await this.call.join({
      url: credentials.room_url,
      token: credentials.token,
      userName: credentials.role,
    });

    // After join, subscribe to remote audio by default (wearer will opt out on takeover).
    const parts = this.call.participants();
    for (const p of Object.values(parts)) {
      if (!p.local) {
        this.call.updateParticipant(p.session_id, {
          setSubscribedTracks: { audio: true },
        });
      }
    }
  }

  private toParticipant(p: DailyParticipantLike): CallParticipant {
    const subscribed = p.tracks?.audio?.subscribed === true;
    const micPublishing = p.tracks?.audio?.state === "playable" || p.local;
    return {
      id: p.session_id,
      role: mapRole(p.user_id, p.user_name),
      user_id: p.user_id,
      displayName: p.user_name || p.user_id || p.session_id,
      audioSubscribed: subscribed,
      micPublishing: Boolean(micPublishing),
      local: p.local,
    };
  }

  async disconnect(): Promise<void> {
    if (!this.call) return;
    await this.call.leave();
  }

  async setMicEnabled(enabled: boolean): Promise<void> {
    if (!this.call) throw new Error("Not connected");
    this.call.setLocalAudio(enabled);
  }

  async setRemoteAudioSubscribed(
    participantId: string,
    subscribed: boolean
  ): Promise<void> {
    if (!this.call) throw new Error("Not connected");
    this.call.updateParticipant(participantId, {
      setSubscribedTracks: { audio: subscribed },
    });
  }

  getLocalParticipantId(): string | null {
    if (!this.call) return null;
    const local = Object.values(this.call.participants()).find((p) => p.local);
    return local?.session_id ?? null;
  }

  getParticipants(): CallParticipant[] {
    if (!this.call) return [];
    return Object.values(this.call.participants()).map((p) =>
      this.toParticipant(p)
    );
  }

  onParticipantJoined(handler: (p: CallParticipant) => void): () => void {
    this.joinHandlers.push(handler);
    return () => {
      this.joinHandlers = this.joinHandlers.filter((h) => h !== handler);
    };
  }

  onParticipantLeft(handler: (p: CallParticipant) => void): () => void {
    this.leaveHandlers.push(handler);
    return () => {
      this.leaveHandlers = this.leaveHandlers.filter((h) => h !== handler);
    };
  }

  onError(handler: (message: string) => void): () => void {
    this.errorHandlers.push(handler);
    return () => {
      this.errorHandlers = this.errorHandlers.filter((h) => h !== handler);
    };
  }

  async destroy(): Promise<void> {
    if (this.call) {
      if (this.boundJoined) this.call.off("participant-joined", this.boundJoined);
      if (this.boundLeft) this.call.off("participant-left", this.boundLeft);
      if (this.boundError) this.call.off("error", this.boundError);
      try {
        await this.call.leave();
      } catch {
        /* ignore */
      }
      await this.call.destroy();
    }
    this.call = null;
    this.joinHandlers = [];
    this.leaveHandlers = [];
    this.errorHandlers = [];
  }
}

export type { Role };
