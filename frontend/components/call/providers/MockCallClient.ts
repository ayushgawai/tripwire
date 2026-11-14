/**
 * LOCAL FIXTURE call client — deterministic participants, labeled fixture_mode.
 * Never present as live Daily success.
 */

import type {
  CallParticipant,
  CallProviderClient,
  ProviderCredentials,
} from "../types";

type Handler<T> = (value: T) => void;

export class MockCallClient implements CallProviderClient {
  readonly name = "mock";
  readonly fixtureMode = true;

  private localId: string | null = null;
  private participants = new Map<string, CallParticipant>();
  private micEnabled = true;
  private joinHandlers: Handler<CallParticipant>[] = [];
  private leaveHandlers: Handler<CallParticipant>[] = [];
  private errorHandlers: Handler<string>[] = [];
  private credentials: ProviderCredentials | null = null;

  async connect(credentials: ProviderCredentials): Promise<void> {
    this.credentials = credentials;
    this.localId = `mock_local_${credentials.role}`;
    const local: CallParticipant = {
      id: this.localId,
      role: credentials.role,
      user_id: credentials.user_id,
      displayName: credentials.role,
      audioSubscribed: true,
      micPublishing: this.micEnabled,
      local: true,
    };
    this.participants.set(this.localId, local);
    // Seed remote peers for fixture demos.
    if (credentials.role !== "caller") {
      this._addRemote("mock_caller", "caller", "caller_fixture");
    }
    if (credentials.role !== "wearer") {
      this._addRemote("mock_wearer", "wearer", "wearer_fixture");
    }
    // Emit local join so family/wearer confirmation paths can run (Daily does this too).
    for (const h of this.joinHandlers) h(local);
  }

  private _addRemote(
    id: string,
    role: CallParticipant["role"],
    userId: string
  ): void {
    const p: CallParticipant = {
      id,
      role,
      user_id: userId,
      displayName: String(role),
      audioSubscribed: true,
      micPublishing: true,
      local: false,
    };
    this.participants.set(id, p);
    for (const h of this.joinHandlers) h(p);
  }

  /** Test/demo helper: simulate a remote participant joining. */
  simulateRemoteJoin(participant: CallParticipant): void {
    this.participants.set(participant.id, participant);
    for (const h of this.joinHandlers) h(participant);
  }

  async disconnect(): Promise<void> {
    this.participants.clear();
    this.localId = null;
  }

  async setMicEnabled(enabled: boolean): Promise<void> {
    this.micEnabled = enabled;
    if (this.localId) {
      const local = this.participants.get(this.localId);
      if (local) {
        local.micPublishing = enabled;
        this.participants.set(this.localId, local);
      }
    }
  }

  async setRemoteAudioSubscribed(
    participantId: string,
    subscribed: boolean
  ): Promise<void> {
    const p = this.participants.get(participantId);
    if (!p) {
      throw new Error(`Unknown participant ${participantId}`);
    }
    p.audioSubscribed = subscribed;
    this.participants.set(participantId, p);
  }

  getLocalParticipantId(): string | null {
    return this.localId;
  }

  getParticipants(): CallParticipant[] {
    return [...this.participants.values()];
  }

  onParticipantJoined(handler: Handler<CallParticipant>): () => void {
    this.joinHandlers.push(handler);
    return () => {
      this.joinHandlers = this.joinHandlers.filter((h) => h !== handler);
    };
  }

  onParticipantLeft(handler: Handler<CallParticipant>): () => void {
    this.leaveHandlers.push(handler);
    return () => {
      this.leaveHandlers = this.leaveHandlers.filter((h) => h !== handler);
    };
  }

  onError(handler: Handler<string>): () => void {
    this.errorHandlers.push(handler);
    return () => {
      this.errorHandlers = this.errorHandlers.filter((h) => h !== handler);
    };
  }

  async destroy(): Promise<void> {
    await this.disconnect();
    this.joinHandlers = [];
    this.leaveHandlers = [];
    this.errorHandlers = [];
    this.credentials = null;
  }
}

export function createCallClient(provider: string): CallProviderClient {
  if (provider === "daily") {
    // Lazy require keeps mock-only unit tests free of daily-js.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { DailyCallClient } = require("./DailyCallClient") as {
      DailyCallClient: new () => CallProviderClient;
    };
    return new DailyCallClient();
  }
  return new MockCallClient();
}
