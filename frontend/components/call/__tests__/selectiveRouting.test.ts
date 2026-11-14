import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyWearerProtectionRouting,
  deriveUiStatus,
} from "../audio/selectiveRouting.ts";
import { MockCallClient } from "../providers/MockCallClient.ts";

describe("selectiveRouting", () => {
  it("blocks caller audio for wearer without muting caller globally", async () => {
    const client = new MockCallClient();
    await client.connect({
      session_id: "s1",
      role: "wearer",
      room_name: "r",
      room_url: "https://fixture.local/r",
      token: "fixture.token",
      expires_at: "2099-01-01T00:00:00Z",
      user_id: "wearer_s1",
      provider: "mock",
      fixture_mode: true,
    });
    const caller = client.getParticipants().find((p) => p.role === "caller");
    assert.ok(caller);
    const confirmation = await applyWearerProtectionRouting({
      client,
      sessionId: "s1",
      callerParticipantId: caller.id,
    });
    assert.equal(confirmation.caller_audio_blocked, true);
    assert.equal(confirmation.wearer_microphone_paused, true);
    const after = client.getParticipants().find((p) => p.id === caller.id);
    assert.equal(after?.audioSubscribed, false);
    const local = client.getParticipants().find((p) => p.local);
    assert.equal(local?.micPublishing, false);
  });

  it("derives takeover_failed and local_fixture statuses with text labels", () => {
    assert.equal(
      deriveUiStatus({
        state: "protecting",
        connected: true,
        takeoverFailed: true,
      }),
      "takeover_failed"
    );
    assert.equal(
      deriveUiStatus({
        state: "monitoring",
        connected: true,
        fixtureMode: true,
      }),
      "local_fixture"
    );
  });
});
