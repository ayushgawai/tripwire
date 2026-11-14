import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/..")

from backend.session import (
    IllegalTransition,
    SessionGone,
    SessionState,
    begin_takeover,
    end_session,
    fail_takeover,
    get_session,
    mark_assistant_ready,
    mark_family_joined,
    mark_wearer_audio_blocked,
    publish_event,
    record_decision,
    store,
    wearer_reconnect,
)


def _new_session(mode="call", protection=True):
    return store.create(mode, protection)


def _drain_events(session):
    """Drain all queued events from subscriber queues and return them."""
    events = []
    for q in list(session.subscribers):
        session.subscribers.remove(q)
        while not q.empty():
            ev = q.get_nowait()
            if ev is not None:
                events.append(ev)
    return events


# ── State transitions ────────────────────────────────────────────────

def test_legal_monitoring_to_protecting():
    s = _new_session("call", protection=False)
    store.transition(s.session_id, SessionState.protecting)
    assert get_session(s.session_id).state == SessionState.protecting


def test_legal_monitoring_to_ended():
    s = _new_session("call", protection=False)
    store.transition(s.session_id, SessionState.ended)
    assert get_session(s.session_id).state == SessionState.ended


def test_legal_protecting_to_active():
    s = _new_session("call", protection=True)
    # starts in protecting
    store.transition(s.session_id, SessionState.assistant_active)
    assert get_session(s.session_id).state == SessionState.assistant_active


def test_legal_protecting_to_ended():
    s = _new_session("call", protection=True)
    store.transition(s.session_id, SessionState.ended)
    assert get_session(s.session_id).state == SessionState.ended


def test_legal_active_to_family_joined():
    s = _new_session("call", protection=True)
    store.transition(s.session_id, SessionState.assistant_active)
    store.transition(s.session_id, SessionState.family_joined)
    assert get_session(s.session_id).state == SessionState.family_joined


def test_legal_active_to_ended():
    s = _new_session("call", protection=True)
    store.transition(s.session_id, SessionState.assistant_active)
    store.transition(s.session_id, SessionState.ended)
    assert get_session(s.session_id).state == SessionState.ended


def test_illegal_monitoring_to_active():
    s = _new_session("call", protection=False)
    try:
        store.transition(s.session_id, SessionState.assistant_active)
    except IllegalTransition:
        pass
    else:
        raise AssertionError("expected IllegalTransition")


def test_illegal_protecting_to_family_joined():
    s = _new_session("call", protection=True)
    try:
        store.transition(s.session_id, SessionState.family_joined)
    except IllegalTransition:
        pass
    else:
        raise AssertionError("expected IllegalTransition")


def test_illegal_family_joined_to_active():
    s = _new_session("call", protection=True)
    # starts in protecting
    store.transition(s.session_id, SessionState.assistant_active)
    store.transition(s.session_id, SessionState.family_joined)
    try:
        store.transition(s.session_id, SessionState.assistant_active)
    except IllegalTransition:
        pass
    else:
        raise AssertionError("expected IllegalTransition")


def test_ended_session_rejects_transition():
    s = _new_session("call", protection=False)
    store.transition(s.session_id, SessionState.ended)
    try:
        store.transition(s.session_id, SessionState.monitoring)
    except IllegalTransition:
        pass
    else:
        raise AssertionError("expected IllegalTransition")


# ── Sequence monotonic from 1 ────────────────────────────────────────

def test_first_event_is_sequence_1():
    s = _new_session()
    env = asyncio.run(store.publish(s.session_id, "test", {"x": 1}))
    assert env["sequence"] == 1


def test_sequence_increments():
    s = _new_session()
    e1 = asyncio.run(store.publish(s.session_id, "test", {}))
    e2 = asyncio.run(store.publish(s.session_id, "test", {}))
    assert e1["sequence"] == 1
    assert e2["sequence"] == 2


# ── Duplicate utterance ──────────────────────────────────────────────

def test_first_utterance_accepted():
    s = _new_session()
    ok = store.add_utterance(s.session_id, {"utterance_id": "u1", "text": "hi"})
    assert ok is True


def test_duplicate_utterance_returns_false():
    s = _new_session()
    store.add_utterance(s.session_id, {"utterance_id": "u1", "text": "hi"})
    ok = store.add_utterance(s.session_id, {"utterance_id": "u1", "text": "hi again"})
    assert ok is False


def test_duplicate_not_added_to_transcript():
    s = _new_session()
    store.add_utterance(s.session_id, {"utterance_id": "u1", "text": "hi"})
    store.add_utterance(s.session_id, {"utterance_id": "u1", "text": "hi again"})
    assert len(get_session(s.session_id).transcript) == 1


# ── Token auth ───────────────────────────────────────────────────────

def test_role_for_valid_token():
    s = _new_session()
    role = store.role_for_token(s.session_id, s.tokens["caller"])
    assert role == "caller"


def test_role_for_invalid_token():
    s = _new_session()
    role = store.role_for_token(s.session_id, "bad-token")
    assert role is None


def test_role_for_unknown_session():
    s = _new_session()
    role = store.role_for_token("ses_unknown", s.tokens["caller"])
    assert role is None


# ── Takeover (async flow — needs a running loop) ─────────────────────

def test_begin_takeover_twice_same_decision_id():
    """Second call with same decision_id is a no-op (idempotent)."""
    decision = {
        "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
        "summary": "s1", "reasons": ["r1"], "evidence": [],
    }

    async def flow():
        s = _new_session("call", protection=False)
        q = asyncio.Queue()
        store.subscribe(s.session_id, q)
        try:
            begin_takeover(s.session_id, decision)
            await asyncio.sleep(0.15)
            # second call — same decision_id, should be no-op
            begin_takeover(s.session_id, decision)
            await asyncio.sleep(0.2)

            events = []
            while not q.empty():
                events.append(q.get_nowait())
            types = [e["type"] for e in events]
            assert types.count("takeover.started") == 1, f"got {types.count('takeover.started')} started"
            assert types.count("family.alert") == 1, f"got {types.count('family.alert')} alerts"
            assert get_session(s.session_id).state == SessionState.protecting
        finally:
            store.unsubscribe(s.session_id, q)

    asyncio.run(flow())


def test_begin_takeover_transitions_to_protecting():
    decision = {
        "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
        "summary": "", "reasons": [], "evidence": [],
    }

    async def flow():
        s = _new_session("call", protection=False)
        begin_takeover(s.session_id, decision)
        await asyncio.sleep(0.1)
        assert get_session(s.session_id).state == SessionState.protecting

    asyncio.run(flow())


def test_takeover_active_only_after_both_signals():
    decision = {
        "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
        "summary": "", "reasons": [], "evidence": [],
    }

    async def flow():
        s = _new_session("call", protection=False)
        begin_takeover(s.session_id, decision)
        await asyncio.sleep(0.1)
        # only assistant_ready — should NOT be active yet
        await mark_assistant_ready(s.session_id)
        await asyncio.sleep(0.05)
        assert get_session(s.session_id).state == SessionState.protecting
        # now both signals — should go active
        await mark_wearer_audio_blocked(s.session_id)
        await asyncio.sleep(0.05)
        assert get_session(s.session_id).state == SessionState.assistant_active

    asyncio.run(flow())


def test_timeout_calls_fail_takeover():
    os.environ["TAKEOVER_TIMEOUT_S"] = "1"
    try:
        decision = {
            "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
            "summary": "", "reasons": [], "evidence": [],
        }

        async def flow():
            s = _new_session("call", protection=False)
            begin_takeover(s.session_id, decision)
            await asyncio.sleep(1.3)
            assert get_session(s.session_id).takeover["status"] == "failed"

        asyncio.run(flow())
    finally:
        os.environ.pop("TAKEOVER_TIMEOUT_S", None)


def test_late_signals_ignored_after_timeout():
    os.environ["TAKEOVER_TIMEOUT_S"] = "1"
    try:
        decision = {
            "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
            "summary": "", "reasons": [], "evidence": [],
        }

        async def flow():
            s = _new_session("call", protection=False)
            begin_takeover(s.session_id, decision)
            await asyncio.sleep(1.3)
            # late signals should be ignored
            await mark_assistant_ready(s.session_id)
            await mark_wearer_audio_blocked(s.session_id)
            await asyncio.sleep(0.1)
            assert get_session(s.session_id).state == SessionState.protecting
            assert get_session(s.session_id).takeover["status"] == "failed"

        asyncio.run(flow())
    finally:
        os.environ.pop("TAKEOVER_TIMEOUT_S", None)


# ── Family join ──────────────────────────────────────────────────────

def test_mark_family_joined_returns_true():
    s = _new_session("call", protection=True)
    # starts in protecting
    store.transition(s.session_id, SessionState.assistant_active)

    async def flow():
        result = await mark_family_joined(s.session_id, {"name": "Daughter"})
        assert result is True
        await asyncio.sleep(0.05)
        assert get_session(s.session_id).state == SessionState.family_joined

    asyncio.run(flow())


def test_family_join_duplicate_is_noop():
    s = _new_session("call", protection=True)
    # starts in protecting
    store.transition(s.session_id, SessionState.assistant_active)

    async def flow():
        await mark_family_joined(s.session_id, {"name": "Daughter"})
        await asyncio.sleep(0.05)
        # second call should be a no-op (state is now family_joined)
        result = await mark_family_joined(s.session_id, {"name": "Daughter"})
        assert result is False

    asyncio.run(flow())


# ── End then publish ─────────────────────────────────────────────────

def test_end_then_publish_raises_session_gone():
    s = _new_session()

    async def flow():
        await end_session(s.session_id)
        try:
            await publish_event(s.session_id, "test", {})
        except SessionGone:
            pass
        else:
            raise AssertionError("expected SessionGone")

    asyncio.run(flow())


# ── Record decision ──────────────────────────────────────────────────

def test_record_decision_stores_latest():
    s = _new_session()
    record_decision(s.session_id, {"decision_id": "d1", "risk": "high"})
    snap = get_session(s.session_id).snapshot()
    assert snap["latest_decision"]["decision_id"] == "d1"
    assert snap["latest_decision"]["risk"] == "high"
