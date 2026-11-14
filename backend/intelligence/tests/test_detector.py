import asyncio
import json
from pathlib import Path

import pytest

from backend.intelligence import analyze_transcript, normalize_utterance, validate_decision
from backend.intelligence.replay import check, replay

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def utt(uid, text, speaker="caller"):
    return {"utterance_id": uid, "speaker": speaker, "text": text}


def analyze(utterances, session_id="s1"):
    return asyncio.run(analyze_transcript(session_id, utterances))


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_fixture_outcomes_and_valid_evidence(path):
    fixture = json.loads(path.read_text(encoding="utf-8"))
    stream, decision = asyncio.run(replay(fixture))
    assert check(fixture, decision) == []
    transcript = [e["payload"] for e in fixture["events"] if e["type"] == "transcript.final"]
    assert validate_decision(decision, transcript) == []
    assert [e["sequence"] for e in stream] == list(range(1, len(stream) + 1))


def test_scam_script_goes_high_on_first_utterance():
    decision = analyze([utt("utt_001", "Grandma, I am in trouble. Buy $500 in gift cards now. Please do not tell anyone.")])
    assert decision["risk"] == "high"
    assert decision["recommended_action"] == "takeover"
    assert {"gift_card_request", "urgency", "secrecy"} <= set(decision["reasons"])
    assert decision["summary"].startswith("The caller's statements include")
    assert {"utterance_id": "utt_001", "quote": "Please do not tell anyone."} in decision["evidence"]


def test_single_indicator_is_not_high():
    assert analyze([utt("u1", "Could you pick up a gift card for Sam's birthday?")])["risk"] == "review"
    assert analyze([utt("u1", "I need it right now.")])["risk"] == "low"


def test_indicators_accumulate_across_utterances():
    decision = analyze([utt("u1", "I need gift cards."), utt("u2", "Hurry."), utt("u3", "Keep it secret.")])
    assert decision["risk"] == "high"
    assert [e["utterance_id"] for e in decision["evidence"]] == ["u1", "u2", "u3"]


@pytest.mark.parametrize(
    "text",
    [
        "This is Microsoft support. Your computer is infected. Please let me connect to your PC and give me your "
        "credit card to pay.",
        "Your bank account has been compromised. Move your savings to a secure account now. Do not talk to the bank staff.",
        "Your computer has a virus. Go to this website and download the fix. Hurry.",
        "Pay the back taxes with iTunes cards or face arrest. It must be done today.",
        "This is Officer Davis. Your grandson was arrested and needs bail. Wire 2000 dollars, and please don't tell "
        "his parents.",
    ],
)
def test_common_scam_scripts_are_high(text):
    assert analyze([utt("u1", text)])["risk"] == "high"


def test_high_needs_indicators_close_together():
    filler = [utt(f"f{n}", "The garden looks lovely this year.") for n in range(5)]
    spread = [utt("u1", "I need gift cards."), *filler, utt("u2", "Hurry."), *filler, utt("u3", "Keep it secret.")]
    assert analyze(spread)["risk"] == "review"


def test_wearer_cannot_supply_the_financial_ask():
    lines = [("I will buy the gift cards right now.", "wearer"), ("Don't tell your daughter.", "caller")]
    assert analyze([utt(f"u{n}", text, speaker) for n, (text, speaker) in enumerate(lines)])["risk"] == "review"
    assert analyze([utt(f"u{n}", text) for n, (text, _) in enumerate(lines)])["risk"] == "high"


def test_assistant_and_family_speech_ignored():
    decision = analyze(
        [utt("u1", "Buy gift cards now and keep it secret.", "assistant"), utt("u2", "Pay now, don't tell anyone.", "family")]
    )
    assert decision == {**decision, "risk": "low", "reasons": [], "evidence": [], "recommended_action": "none"}


def test_decision_id_is_stable_and_session_scoped():
    transcript = [utt("u1", "Buy gift cards now and do not tell your daughter.")]
    assert analyze(transcript)["decision_id"] == analyze(transcript + transcript)["decision_id"]
    assert analyze(transcript, "s1")["decision_id"] != analyze(transcript, "s2")["decision_id"]


def test_quotes_are_verbatim_substrings_of_raw_text():
    # Curly quotes, odd spacing and line breaks are matched, but quotes keep the original characters, so they
    # pass the coordinator's check against the text exactly as it was posted.
    raw = "  Buy  gift cards\nnow. Don’t   tell your daughter.  "
    decision = analyze([utt("u1", raw)])
    assert decision["risk"] == "high"
    assert all(e["quote"] in raw for e in decision["evidence"])
    assert {"utterance_id": "u1", "quote": "Don’t   tell your daughter."} in decision["evidence"]


def test_normalization_and_invalid_input():
    assert normalize_utterance({"utterance_id": " u1 ", "speaker": "Caller", "text": "  Don’t tell anyone. "}) == {
        "utterance_id": "u1",
        "speaker": "caller",
        "text": "Don’t tell anyone.",
        "timestamp": None,
    }
    with pytest.raises(ValueError):
        normalize_utterance(utt("u1", "hi", speaker="robot"))
    # Invalid entries are skipped instead of failing the whole analysis.
    junk = [utt("u1", "hi", speaker="robot"), {"speaker": "caller", "text": "x"}, utt("u2", ""), None, "text"]
    assert analyze(junk)["risk"] == "low"


def test_validate_decision_rejects_fabricated_quote():
    decision = analyze([utt("u1", "Buy gift cards now and do not tell your daughter.")])
    forged = {**decision, "evidence": [{"utterance_id": "u1", "quote": "Send bitcoin."}]}
    assert validate_decision(forged, [utt("u1", "Buy gift cards now and do not tell your daughter.")])


# --- Gemini layer -----------------------------------------------------------------------------------------------

PARAPHRASED = [
    utt("u1", "Go to the store and pick up some Apple cards for me."),
    utt("u2", "Hurry."),
    utt("u3", "Mom can't find out about this."),
]


def test_gemini_adds_only_verified_indicators(fake_gemini):
    requests = fake_gemini(
        {
            "indicators": [
                {"reason": "gift_card_request", "utterance_id": "u1", "quote": "pick up some apple cards"},
                {"reason": "secrecy", "utterance_id": "u3", "quote": "Mom can’t find  out about this."},
                {"reason": "payment_request", "utterance_id": "u2", "quote": "Send bitcoin."},  # not in text
                {"reason": "made_up", "utterance_id": "u1", "quote": "Go to the store"},  # unknown reason
                {"reason": "threat", "utterance_id": "missing", "quote": "Hurry."},  # unknown utterance
            ]
        }
    )
    decision = analyze(PARAPHRASED)
    assert decision["risk"] == "high"
    assert decision["reasons"] == ["gift_card_request", "urgency", "secrecy"]
    # Casing is restored from the transcript, so the quote is an exact substring.
    assert {"utterance_id": "u1", "quote": "pick up some Apple cards"} in decision["evidence"]
    assert validate_decision(decision, PARAPHRASED) == []

    (request,) = requests
    assert request.url.path == "/v1beta/models/test-model:generateContent"
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "test-key" not in str(request.url)
    body = json.loads(request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in body["generationConfig"]


def test_gemini_failure_falls_back_to_rules_and_backs_off(fake_gemini):
    requests = fake_gemini(500)
    assert analyze(PARAPHRASED)["reasons"] == ["urgency"]
    assert analyze(PARAPHRASED[:2])["reasons"] == ["urgency"]
    assert len(requests) == 1  # the second analysis skipped the model instead of waiting on it again


def test_gemini_not_called_for_benign_chat(fake_gemini):
    requests = fake_gemini({"indicators": []})
    analyze([utt("u1", "Please call me back tomorrow.")])
    assert requests == []


def test_gemini_invalid_json_falls_back_to_rules(fake_gemini):
    fake_gemini("not json")
    assert analyze(PARAPHRASED)["risk"] == "low"


def test_gemini_skipped_when_rules_already_high(fake_gemini):
    requests = fake_gemini({"indicators": []})
    analyze([utt("u1", "Buy gift cards now and do not tell your daughter.")])
    assert requests == []


def test_gemini_cannot_lower_rule_findings_and_is_cached(fake_gemini):
    requests = fake_gemini({"indicators": []})
    transcript = [utt("u1", "The service costs $2,000.")]
    assert analyze(transcript)["risk"] == "review"
    assert analyze(transcript)["risk"] == "review"
    assert len(requests) == 1
