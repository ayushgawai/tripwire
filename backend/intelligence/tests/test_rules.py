import pytest

from backend.intelligence.normalize import normalize_transcript
from backend.intelligence.rules import detect, split_sentences


def reasons_for(text: str) -> set[str]:
    return {i.reason for i in detect(normalize_transcript([{"utterance_id": "u", "speaker": "caller", "text": text}]))}


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Buy $500 in gift cards now.", "gift_card_request"),
        ("Read me the numbers on the back.", "gift_card_request"),
        ("Send the money through Western Union.", "payment_request"),
        ("Pay now and do not call your daughter.", "payment_request"),
        ("What's your social security number?", "credential_request"),
        ("Read me the verification code we sent.", "credential_request"),
        ("Install AnyDesk so I can fix it.", "remote_access_request"),
        ("The service costs $2,000.", "large_amount"),
        ("It's two grand.", "large_amount"),
        ("I need 1.5k dollars.", "large_amount"),
        ("It has to happen now.", "urgency"),
        ("There is no time.", "urgency"),
        ("Please do not tell anyone.", "secrecy"),
        ("Don’t tell your daughter.", "secrecy"),
        ("Keep this between us.", "secrecy"),
        ("Don't hang up.", "verification_discouraged"),
        ("You will be arrested today.", "threat"),
        ("Your account will be frozen.", "threat"),
        ("Grandma, I am in trouble.", "family_emergency"),
        ("This is the IRS.", "impersonation"),
        ("This is Officer Davis.", "impersonation"),
        ("Pay the back taxes with iTunes cards or face arrest.", "threat"),
        ("It must be done today.", "urgency"),
        ("Wire 2000 dollars.", "payment_request"),
        ("Your grandson needs bail.", "payment_request"),
        ("Put the cash in an envelope and a courier will come get it.", "payment_request"),
        ("Move your savings to a secure account now.", "payment_request"),
        ("Do not talk to the bank staff.", "secrecy"),
        ("Please don't tell his parents.", "secrecy"),
        ("Your computer has a virus.", "threat"),
        ("Please let me connect to your PC.", "remote_access_request"),
        ("Give me your credit card to pay.", "credential_request"),
    ],
)
def test_detects_reason(text, reason):
    assert reason in reasons_for(text)


@pytest.mark.parametrize(
    "text",
    [
        "Please call me back tomorrow.",
        "Should I call your mother?",
        "It costs $40.",
        "No hurry, call me whenever.",
        "It's not urgent.",
        "Can you send me the photos?",
        "Don't call me after nine.",
        "Hello, this is the auto shop calling about your car.",
        "You can use your gift card at Target.",
        "I got a gift card from my daughter for Christmas.",
        "Bitcoin went up, crypto is crazy.",
        "Tell me the password for the wifi.",
        "Mom, what's the pin number for the garage?",
        "I need to give the pharmacy my insurance card number.",
        "I'll download the app so we can video chat.",
        "Let's install the new program on your computer, grandpa.",
        "Let's keep it a secret, it's her birthday gift.",
        "Please don't tell mom, I'm planning her surprise.",
    ],
)
def test_benign_sentences_have_no_indicators(text):
    assert reasons_for(text) == set()


def test_sentences_are_exact_substrings():
    text = "No. There is no time! It costs $2,000.50 today?"
    sentences = split_sentences(text)
    assert sentences == ["No.", "There is no time!", "It costs $2,000.50 today?"]
    assert all(s in text for s in sentences)
