"""Tests for backend/app.py.

Uses FastAPI TestClient. Fake modules are injected via _setup_modules()
which reimports backend.app to pick them up.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__) + "/..")


# ── Fake modules ────────────────────────────────────────────────────────

class FakeIntelligence:
    @staticmethod
    async def analyze_transcript(session_id: str, utterances: list[dict]) -> dict:
        text = " ".join(u.get("text", "") for u in utterances)
        if "gift cards" in text:
            return {
                "decision_id": f"dec_{session_id}_1",
                "risk": "high",
                "recommended_action": "takeover",
                "summary": "Scam detected",
                "reasons": ["gift card request"],
                "evidence": [
                    {"utterance_id": u["utterance_id"], "quote": "gift cards"}
                    for u in utterances if "gift cards" in u.get("text", "")
                ],
            }
        return {
            "decision_id": f"dec_{session_id}_0",
            "risk": "low",
            "recommended_action": "monitor",
            "summary": "Normal",
            "reasons": [],
            "evidence": [],
        }


class FakeCalls:
    calls: list = []

    @staticmethod
    async def create_join_credentials(session_id: str, role: str) -> dict:
        FakeCalls.calls.append(("create_join_credentials", session_id, role))
        return {"url": f"https://fake/{session_id}/{role}"}

    @staticmethod
    async def start_takeover(session_id: str, decision: dict) -> None:
        FakeCalls.calls.append(("start_takeover", session_id))

    @staticmethod
    async def stop_assistant(session_id: str) -> None:
        FakeCalls.calls.append(("stop_assistant", session_id))

    @staticmethod
    async def end_call(session_id: str) -> None:
        FakeCalls.calls.append(("end_call", session_id))


# ── Module setup ───────────────────────────────────────────────────────

def _setup_modules():
    """Patch sys.modules with fakes and reimport backend.app."""
    sys.modules["backend.intelligence"] = FakeIntelligence()
    sys.modules["backend.calls"] = FakeCalls()
    sys.modules.pop("backend.app", None)
    import backend.app  # noqa: F401
    return backend.app.app


@pytest.fixture()
def app_instance():
    FakeCalls.calls.clear()
    return _setup_modules()


@pytest.fixture()
def client(app_instance):
    return TestClient(app_instance)


@pytest.fixture()
def session_and_tokens(client):
    r = client.post("/api/sessions", json={"mode": "call", "protection_enabled": True})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["session_id"], data["tokens"]


def _h(tokens, role="caller"):
    return {"X-Session-Token": tokens[role]}


# ── Tests ───────────────────────────────────────────────────────────────


class TestCreateSession:
    def test_returns_4_tokens(self, client):
        r = client.post("/api/sessions", json={"mode": "call", "protection_enabled": True})
        assert r.status_code == 200
        data = r.json()
        assert set(data["tokens"]) == {"caller", "wearer", "family", "presenter"}
        assert data["state"] == "monitoring"

    def test_no_protection_starts_monitoring(self, client):
        r = client.post("/api/sessions", json={"mode": "call", "protection_enabled": False})
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "monitoring"


class TestAuth:
    def test_bad_token_403(self, client, session_and_tokens):
        sid, _ = session_and_tokens
        r = client.get(f"/api/sessions/{sid}", headers={"X-Session-Token": "bad"})
        assert r.status_code == 403

    def test_unknown_session_404(self, client):
        r = client.get("/api/sessions/ses_unknown", headers={"X-Session-Token": "x" * 22})
        assert r.status_code == 404


class TestTranscriptBenign:
    def test_benign_transcript_low_risk(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        r = client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "hello world", "timestamp": "2026-01-01T00:00:00Z"},
        )
        assert r.status_code == 200
        assert r.json() == {"accepted": True, "duplicate": False}
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["state"] == "monitoring"


class TestTranscriptScam:
    def test_scam_triggers_takeover(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        r = client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards now", "timestamp": "2026-01-01T00:00:00Z"},
        )
        assert r.status_code == 200
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["state"] == "protecting"
        assert snap["latest_decision"]["risk"] == "high"
        assert "start_takeover" in [c[0] for c in FakeCalls.calls]

    def test_duplicate_utterance_no_duplicate_takeover(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards now", "timestamp": "2026-01-01T00:00:00Z"},
        )
        FakeCalls.calls.clear()

        # Duplicate same id
        r = client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards now", "timestamp": "2026-01-01T00:00:01Z"},
        )
        assert r.json() == {"accepted": True, "duplicate": True}

        # Second scam line — state already protecting
        client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u2", "speaker": "caller", "text": "send more gift cards", "timestamp": "2026-01-01T00:00:02Z"},
        )
        assert "start_takeover" not in [c[0] for c in FakeCalls.calls]
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["state"] == "protecting"


class TestSignals:
    def test_wearer_audio_blocked_and_assistant_active(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards", "timestamp": "2026-01-01T00:00:00Z"},
        )
        from backend import session as sess
        asyncio.run(sess.mark_assistant_ready(sid))
        r = client.post(
            f"/api/sessions/{sid}/signals",
            headers=_h(tokens, "wearer"),
            json={"signal": "wearer_audio_blocked"},
        )
        assert r.status_code == 200
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["state"] == "assistant_active"
        assert snap["takeover"]["status"] == "active"

    def test_wearer_reconnect_with_family_token(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards", "timestamp": "2026-01-01T00:00:00Z"},
        )
        from backend import session as sess
        asyncio.run(sess.mark_assistant_ready(sid))
        asyncio.run(sess.mark_wearer_audio_blocked(sid))
        asyncio.run(sess.mark_family_joined(sid, {"name": "Daughter"}))
        r = client.post(
            f"/api/sessions/{sid}/signals",
            headers=_h(tokens, "family"),
            json={"signal": "wearer_reconnect"},
        )
        assert r.status_code == 200
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["wearer_connected"] is True


class TestFamilyJoined:
    def test_on_family_joined_calls_stop_assistant_once(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        client.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "buy gift cards", "timestamp": "2026-01-01T00:00:00Z"},
        )
        from backend import session as sess
        asyncio.run(sess.mark_assistant_ready(sid))
        asyncio.run(sess.mark_wearer_audio_blocked(sid))
        FakeCalls.calls.clear()
        from backend.app import on_family_joined
        asyncio.run(on_family_joined(sid, {"name": "Daughter"}))
        assert FakeCalls.calls.count(("stop_assistant", sid)) == 1
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert snap["state"] == "family_joined"


class TestInvalidEvidence:
    def test_invalid_evidence_quote(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)

        async def bad_analyze(session_id, utterances):
            return {
                "decision_id": "d1", "risk": "high", "recommended_action": "takeover",
                "summary": "x", "reasons": [],
                "evidence": [{"utterance_id": "nonexistent", "quote": "nope"}],
            }

        import types
        fake_bad = types.SimpleNamespace(analyze_transcript=bad_analyze)
        sys.modules["backend.intelligence"] = fake_bad
        sys.modules.pop("backend.app", None)
        import importlib
        import backend.app as app_mod
        app_mod = importlib.reload(app_mod)
        c2 = TestClient(app_mod.app)

        r = c2.post(
            f"/api/sessions/{sid}/transcripts",
            headers=h,
            json={"utterance_id": "u1", "speaker": "caller", "text": "hello", "timestamp": "2026-01-01T00:00:00Z"},
        )
        assert r.status_code == 200


class TestJoinWithoutCalls:
    def test_join_returns_501(self, client, session_and_tokens, monkeypatch):
        sid, tokens = session_and_tokens
        # Remove the module entirely
        monkeypatch.delitem(sys.modules, "backend.calls", raising=False)
        sys.modules.pop("backend.app", None)
        import importlib
        import backend.app as app_mod
        app_mod = importlib.reload(app_mod)
        c2 = TestClient(app_mod.app)
        monkeypatch.setattr(app_mod, "_load_calls", lambda: None)
        r = c2.post(
            f"/api/sessions/{sid}/join",
            headers=_h(tokens),
            json={"role": "family"},
        )
        _setup_modules()  # restore fakes for later tests
        assert r.status_code == 501


class TestEnd:
    def test_end_then_410(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        r = client.post(f"/api/sessions/{sid}/end", headers=h, json={})
        assert r.status_code == 200
        assert "end_call" in [c[0] for c in FakeCalls.calls]
        r2 = client.get(f"/api/sessions/{sid}", headers=h)
        assert r2.status_code == 410


class TestWebSocket:
    def test_ws_receives_transcript_final(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        with client.websocket_connect(f"/ws/sessions/{sid}?token={tokens['caller']}") as ws:
            client.post(
                f"/api/sessions/{sid}/transcripts",
                headers=_h(tokens),
                json={"utterance_id": "u1", "speaker": "caller", "text": "hello", "timestamp": "2026-01-01T00:00:00Z"},
            )
            msg = ws.receive_json()
            assert msg["type"] == "transcript.final"
            assert msg["payload"]["utterance_id"] == "u1"
            assert msg["sequence"] == 1


class TestDuplicates:
    def test_duplicate_utterance(self, client, session_and_tokens):
        sid, tokens = session_and_tokens
        h = _h(tokens)
        body = {"utterance_id": "u1", "speaker": "caller", "text": "hi", "timestamp": "2026-01-01T00:00:00Z"}
        r1 = client.post(f"/api/sessions/{sid}/transcripts", headers=h, json=body)
        assert r1.json() == {"accepted": True, "duplicate": False}
        r2 = client.post(f"/api/sessions/{sid}/transcripts", headers=h, json=body)
        assert r2.json() == {"accepted": True, "duplicate": True}
        snap = client.get(f"/api/sessions/{sid}", headers=h).json()
        assert len(snap["transcript"]) == 1
