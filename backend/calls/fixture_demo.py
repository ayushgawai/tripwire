"""LOCAL FIXTURE end-to-end demo — visibly labeled, deterministic, repeatable.

Run: python -m backend.calls.fixture_demo
Never describes outcomes as live Daily/Pipecat success.
"""

from __future__ import annotations

import asyncio
import sys

from .adapters.session_bridge import SessionBridge
from .mock_provider import MockCallProvider
from .mock_voice_worker import MockVoiceWorker
from .models import ParticipantRole, RoutingConfirmation, utc_now_iso
from .session_manager import CallSessionManager


async def run_once(run_id: int) -> None:
    sid = f"fixture_demo_{run_id}"
    print(f"\n=== LOCAL FIXTURE / DEMO REPLAY run {run_id} session={sid} ===")
    mgr = CallSessionManager(
        provider=MockCallProvider(),
        bridge=SessionBridge(),
        worker_factory=lambda: MockVoiceWorker(),
    )
    await mgr.attach_session(sid, fixture_mode=True)
    invites = mgr.get_invite_tokens(sid)
    await mgr.join(sid, role=ParticipantRole.CALLER, access_token=invites["caller"])
    await mgr.join(sid, role=ParticipantRole.WEARER, access_token=invites["wearer"])
    print("joined caller + wearer (fixture credentials)")

    await mgr.start_takeover(
        sid, decision_id=f"decision_{run_id}", risk="high", recommended_action="takeover"
    )
    print("takeover.started → protecting")
    await mgr.start_voice_worker(sid)
    print("mock voice worker ready (NOT live Pipecat)")
    await mgr.confirm_routing(
        sid,
        RoutingConfirmation(
            session_id=sid,
            caller_audio_blocked=True,
            wearer_microphone_paused=True,
            timestamp=utc_now_iso(),
        ),
    )
    snap = mgr.snapshot(sid)
    assert snap["state"] == "assistant_active"
    print("takeover.active + family.alert")

    await mgr.join(sid, role=ParticipantRole.FAMILY, access_token=invites["family"])
    await mgr.confirm_family_joined(
        sid,
        access_token=invites["family"],
        provider_participant_id=f"fixture_family_{run_id}",
    )
    print("family.joined — AI stopped; wearer still protected")
    await mgr.reconnect_wearer(sid, access_token=invites["wearer"])
    print("explicit wearer reconnect")
    await mgr.end_session(sid)
    print("session ended; cleanup complete")
    types = [e.type for e in mgr.bridge.publisher.events_for(sid)]
    print("events:", ", ".join(types))


async def main() -> int:
    print("Tripwire call module — LOCAL FIXTURE mode (not live provider)")
    for i in range(1, 4):
        await run_once(i)
    print("\nAll 3 fixture demos completed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
