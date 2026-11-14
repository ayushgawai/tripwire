import asyncio

import pytest

from backend.intelligence import ASSISTANT_FALLBACK, assistant_reply, family_alert, wearer_warning
from backend.intelligence.intervention import is_safe_reply, summarize


def test_summary_wording():
    assert summarize([], set()) == "No concerning patterns detected."
    assert summarize(["urgency"], {"caller"}) == "The caller's statements include pressure to act immediately."
    assert summarize(["gift_card_request", "urgency", "secrecy"], {"caller", "wearer"}) == (
        "The conversation includes a request for gift cards, pressure to act immediately, and a request to keep it secret."
    )
    assert summarize(["large_amount", "secrecy"], {"ambient"}).startswith("A nearby speaker's statements include")


def test_family_alert_and_wearer_warning():
    decision = {
        "summary": "The caller's statements include a request for gift cards.",
        "evidence": [{"utterance_id": "u1", "quote": "Buy gift cards."}],
        "recommended_action": "takeover",
    }
    alert = family_alert(decision)
    assert alert["title"] == "Tripwire paused a suspicious call"
    assert alert["message"].startswith(decision["summary"])
    assert alert["evidence"] == decision["evidence"]
    assert wearer_warning(decision) == "This request may be unsafe. We are asking your trusted contact to help."
    ambient = {**decision, "recommended_action": "alert"}
    assert family_alert(ambient)["title"] == "Tripwire flagged a suspicious conversation"
    assert "alerted" in wearer_warning(ambient)


@pytest.mark.parametrize(
    ("reply", "safe"),
    [
        ("A family member will verify the request before anyone acts.", True),
        ("I understand. A family member will review this before anything happens.", True),
        ("Okay, I will send the gift cards shortly.", False),
        ("We can pay you half today.", False),
        ("It's Grandma, dear, don't worry.", False),
        ("Please call 555 0100.", False),
        ("x" * 300, False),
        ("", False),
    ],
)
def test_reply_guardrail(reply, safe):
    assert is_safe_reply(reply) is safe


def test_assistant_reply_without_gemini_uses_fallback():
    assert asyncio.run(assistant_reply("It has to happen now.")) == ASSISTANT_FALLBACK


def test_assistant_reply_uses_safe_model_text(fake_gemini):
    fake_gemini('"I understand it feels urgent. A family member will verify this before anyone acts."')
    assert asyncio.run(assistant_reply("It has to happen now.")) == (
        "I understand it feels urgent. A family member will verify this before anyone acts."
    )


@pytest.mark.parametrize("reply", ["Sure, I will buy $500 in gift cards now.", 503])
def test_assistant_reply_rejects_unsafe_or_failed_output(fake_gemini, reply):
    fake_gemini(reply)
    assert asyncio.run(assistant_reply("Just do it.")) == ASSISTANT_FALLBACK
