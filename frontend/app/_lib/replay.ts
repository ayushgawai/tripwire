// Fixture replay engine. Syncs every open tab (wearer / caller / family / presenter) through a
// BroadcastChannel so one click on the presenter page drives the whole multi-window demo.
// Replay output is always labeled "Demo replay" in the UI and must never be described as live.
import type { EventEnvelope } from "./types.ts";
import type { FixtureStep } from "./fixtures.ts";

type Msg =
  | { kind: "event"; envelope: EventEnvelope }
  | { kind: "reset" }
  | { kind: "hello" }
  | { kind: "history"; envelopes: EventEnvelope[] };

export class ReplayBus {
  private ch: BroadcastChannel | null;
  private timers: ReturnType<typeof setTimeout>[] = [];
  private history: EventEnvelope[] = [];
  private seq = 0;

  constructor(
    private sessionId: string,
    private onEvent: (e: EventEnvelope) => void,
    private onReset: () => void,
  ) {
    this.ch =
      typeof BroadcastChannel !== "undefined"
        ? new BroadcastChannel(`tripwire-replay:${sessionId}`)
        : null;
    if (this.ch) this.ch.onmessage = (m) => this.receive(m.data as Msg);
    // Ask any already-open tab for what has happened so far (refresh recovery).
    this.post({ kind: "hello" });
  }

  private post(m: Msg) {
    try {
      this.ch?.postMessage(m);
    } catch {
      /* channel closed */
    }
  }

  private receive(m: Msg) {
    switch (m.kind) {
      case "event":
        this.record(m.envelope);
        break;
      case "reset":
        this.clearTimers();
        this.history = [];
        this.seq = 0;
        this.onReset();
        break;
      case "hello":
        if (this.history.length) this.post({ kind: "history", envelopes: this.history });
        break;
      case "history":
        for (const e of m.envelopes) this.record(e);
        break;
    }
  }

  private record(e: EventEnvelope) {
    if (this.history.some((h) => h.event_id === e.event_id)) return;
    this.history.push(e);
    this.seq = Math.max(this.seq, e.sequence);
    this.onEvent(e);
  }

  private emit(step: FixtureStep) {
    const sequence = this.seq + 1;
    const envelope: EventEnvelope = {
      event_id: `replay_${this.sessionId}_${sequence}_${Math.random().toString(36).slice(2, 8)}`,
      session_id: this.sessionId,
      sequence,
      type: step.type,
      timestamp: new Date().toISOString(),
      payload: { ...step.payload, replay: true },
    };
    this.record(envelope);
    this.post({ kind: "event", envelope });
  }

  /** Schedule steps from this tab; every other tab receives them through the channel. */
  run(steps: FixtureStep[]) {
    let t = 0;
    for (const step of steps) {
      t += step.delay;
      this.timers.push(setTimeout(() => this.emit(step), t));
    }
  }

  reset() {
    this.post({ kind: "reset" });
    this.receive({ kind: "reset" });
  }

  get running() {
    return this.timers.length > 0;
  }

  private clearTimers() {
    this.timers.forEach(clearTimeout);
    this.timers = [];
  }

  close() {
    this.clearTimers();
    this.ch?.close();
    this.ch = null;
  }
}
