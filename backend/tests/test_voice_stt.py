import asyncio

from backend import assistant_voice, session
from backend.stt import parse_deepgram_message


def _res(text, is_final=False, speech_final=False):
    return {"type": "Results", "is_final": is_final, "speech_final": speech_final,
            "channel": {"alternatives": [{"transcript": text}]}}


def test_parse_deepgram_interim_finals_and_utterance_end():
    buf: list[str] = []
    assert parse_deepgram_message(_res("buy gift"), buf) is None and buf == []
    assert parse_deepgram_message(_res("Buy gift cards now.", is_final=True), buf) is None
    assert parse_deepgram_message(_res("Do not tell anyone.", is_final=True, speech_final=True), buf) == \
        "Buy gift cards now. Do not tell anyone."
    assert buf == []
    parse_deepgram_message(_res("Hello.", is_final=True), buf)
    assert parse_deepgram_message({"type": "UtteranceEnd"}, buf) == "Hello."


def test_takeover_active_speaks_opening_line_once(monkeypatch):
    spoken = []

    async def fake_speak(sid, text):
        spoken.append(text)

    monkeypatch.setattr(assistant_voice, "speak", fake_speak)

    async def flow():
        s = session.store.create("call", True)
        session.begin_takeover(s.session_id, {"decision_id": "d1", "risk": "high", "recommended_action": "takeover"})
        await asyncio.sleep(0.05)
        await session.mark_wearer_audio_blocked(s.session_id)
        await session.mark_assistant_ready(s.session_id)
        await asyncio.sleep(0.05)
        await session.end_session(s.session_id)

    asyncio.run(flow())
    assert len(spoken) == 1 and spoken[0]


def test_audio_route_serves_cached_audio_only():
    from fastapi.testclient import TestClient
    from backend.app import app

    c = TestClient(app)
    r = c.post("/api/sessions", json={"mode": "call", "protection_enabled": True}).json()
    sid, tok = r["session_id"], r["tokens"]["caller"]
    assistant_voice._AUDIO_CACHE["ai_test"] = b"ID3fake"
    assert c.get(f"/api/sessions/{sid}/assistant-audio/ai_test?token={tok}").content == b"ID3fake"
    assert c.get(f"/api/sessions/{sid}/assistant-audio/missing?token={tok}").status_code == 404
    assert c.get(f"/api/sessions/{sid}/assistant-audio/ai_test?token=bad").status_code == 403
