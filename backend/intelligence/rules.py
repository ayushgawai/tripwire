"""Deterministic indicator rules. Each match quotes the exact sentence it came from.

Patterns favor asks and imperatives ("buy gift cards") over bare mentions ("I got a gift card"), so ordinary
family talk stays low. Paraphrases the rules miss are left to the optional Gemini layer.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache

from .normalize import fold
from .schema import REASONS, Indicator, Utterance

LARGE_AMOUNT_USD = 500

_NOT = r"(?:do not|don'?t|dont|never)"
_ASK = r"(?:give|tell|read|send|share|confirm|verify|need|what'?s|what is|provide|enter)"
_PEOPLE = (
    r"(?:anyone|anybody|no ?one|mom|dad|(?:the |your |his |her )?(?:bank(?: teller| staff)?|teller|police|cops|staff"
    r"|family|parents|daughter|son|kids|children|mom|mother|dad|father|husband|wife|grandchildren|grandkids|grandson"
    r"|granddaughter|sister|brother|lawyer|neighbors?|friends?|pastor|doctor))"
)


def _rx(*patterns: str) -> Callable[[str], bool]:
    return re.compile("|".join(patterns), re.IGNORECASE).search


_MONEY = re.compile(
    r"\$\s?(?P<a>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<am>k\b|thousand|grand|million)?"
    r"|\b(?P<b>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<bm>k|thousand|grand|million)?\s*(?:dollars?|bucks|usd)\b",
    re.IGNORECASE,
)
_MONEY_WORDS = _rx(
    r"\b(?:thousands?|millions?)\s+(?:dollars|bucks)\b",
    r"\b(?:a|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+grand\b",
    r"\b(?:five|six|seven|eight|nine)\s+hundred\s+(?:dollars|bucks)\b",
)
_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "grand": 1e3, "million": 1e6}


def _large_amount(sentence: str) -> bool:
    if _MONEY_WORDS(sentence):
        return True
    for m in _MONEY.finditer(sentence):
        amount = float((m["a"] or m["b"]).replace(",", ""))
        if amount * _MULTIPLIER.get((m["am"] or m["bm"] or "").lower(), 1) >= LARGE_AMOUNT_USD:
            return True
    return False


_SECRECY = _rx(
    rf"\b{_NOT}\s+(?:tell|call|text|contact|talk to|speak to|mention (?:this|it|that) to|let)\s+[^.?!]{{0,25}}?\b{_PEOPLE}\b",
    r"\bkeep (?:this|it|that) (?:a )?(?:secret|quiet|confidential|private|to yourself|between us)\b",
    r"\bbetween you and me\b|\bstays? between us\b",
    r"\b(?:nobody|no one) (?:can|should|needs to|must|has to) know\b",
)
_HAPPY_SECRET = _rx(r"\b(?:surprise|birthday|party|anniversary|present)\b")

_MATCHERS: dict[str, Callable[[str], bool]] = {
    "gift_card_request": _rx(
        r"\b(?:buy|get|purchase|pick up|grab|load|send|read|scratch|need|want|pay (?:with|in|using))\b[^.?!]{0,30}"
        r"\bgift ?cards?\b",
        r"\bin (?:\w+ )?gift ?cards\b",
        r"\bgift ?cards?\b[^.?!]{0,20}\b(?:numbers?|codes?|pins?)\b",
        r"\b(?:itunes|google ?play|steam|ebay|razer gold|vanilla)\s+(?:gift\s+)?cards?\b",
        r"\b(?:numbers?|codes?|pins?)\s+(?:on|from)\s+the\s+back\b",
        r"\bscratch (?:off )?the (?:back|silver|strip)\b",
    ),
    "payment_request": _rx(
        r"\bwire (?:transfer|the money|money|funds|it|me|us|\$?\d)",
        r"\b(?:western union|moneygram)\b|\b(?:bitcoin|crypto) (?:atm|machine|kiosk|wallet)\b",
        r"\b(?:send|pay|transfer|deposit|put|load)\b[^.?!]{0,30}\b(?:zelle|venmo|cash ?app|bitcoin|btc|crypto(?:currency)?)\b",
        r"\b(?:zelle|venmo|cash ?app)\s+(?:me|us|him|her|them|it)\b",
        r"\bsend (?:me |us |him |her |them )?(?:the |some )?(?:money|cash|payment|funds)\b",
        r"\b(?:transfer|move) (?:the |your |some |all (?:of )?(?:your |the )?)?(?:money|funds|savings)\b",
        r"\bwithdraw (?:the |some |your )?(?:cash|money|savings)\b",
        r"\bpay (?:me|us|him|her|them|now|immediately|right (?:now|away)|today|upfront|up front|in cash|with cash"
        r"|(?:the|a|this|my) (?:fee|fine|deposit|bail))\b",
        r"\b(?:cash|money) in(?:to)? an envelope\b",
        r"\b(?:courier|driver|agent)\b[^.?!]{0,25}\b(?:pick (?:it )?up|collect|come (?:and )?get)\b",
        r"\bcome (?:and )?(?:get|collect|pick up) (?:the )?(?:cash|money|envelope|package)\b",
        r"\bbail (?:money|bond)\b|\b(?:needs?|post|pay) (?:the |his |her |my )?bail\b",
    ),
    "credential_request": _rx(
        rf"\b{_ASK}\b[^.?!]{{0,40}}?\b(?:social security(?: number)?|ssn|routing number|verification code|security code"
        r"|one[- ]time (?:pass)?code|otp|cvv|(?:credit|debit|bank) card(?: number)?)\b",
        rf"\b{_ASK}\b[^.?!]{{0,30}}?\byour (?:\w+ )?(?:pin|password|passcode|account number|login)\b",
        r"\bread (?:me )?(?:the |that )?(?:code|numbers|digits)\b",
    ),
    "remote_access_request": _rx(
        r"\b(?:anydesk|teamviewer|ultraviewer|logmein|rustdesk)\b",
        r"\bremote (?:access|desktop|control)\b",
        r"\bshare (?:your|the) screen\b",
        r"\b(?:let|allow) me (?:connect|access|log ?in|get in)\b",
        r"\b(?:download|install)\b[^.?!]{0,30}\b(?:so|and) (?:i|we) can (?:access|see|fix|connect|control)\b",
        r"\bdownload (?:the|this) (?:fix|patch|security)\b",
    ),
    "large_amount": _large_amount,
    "urgency": _rx(
        r"\bright (?:now|away)\b|\bimmediately\b|\basap\b|\bas soon as possible\b",
        r"(?<!not )\burgent(?:ly)?\b|(?<!no )\bhurry\b|\bno time\b|\bcan'?t wait\b|\bcannot wait\b",
        r"\bbefore it'?s too late\b|\blast chance\b|\btoday only\b",
        r"\bwithin (?:the |an |one |a few |\d+ )?(?:hours?|minutes?)\b",
        r"\bby (?:tonight|(?:the )?end of (?:the )?day)\b",
        r"\b(?:has to|have to|needs? to|must)\s+(?:happen|be done|be paid|be sent|go out)\s+(?:now|today|tonight)\b",
        r"\b(?:buy|send|pay|wire|transfer|move|withdraw|go|get|do it|act)\b[^.?!]{0,30}\bnow\b",
    ),
    "secrecy": lambda s: bool(_SECRECY(s)) and not _HAPPY_SECRET(s),
    "verification_discouraged": _rx(
        rf"\b{_NOT}\s+hang\s+up\b|\bstay on the (?:line|phone)\b",
        r"\bno need to (?:call|check|verify|confirm)\b",
        rf"\b{_NOT}\s+(?:call|contact)\b[^.?!]{{0,15}}\bback\b",
        rf"\b{_NOT}\s+(?:verify|check with)\b",
    ),
    "threat": _rx(
        r"\byou(?:'ll| will| could| are going to| can)\s+(?:be\s+)?(?:arrested|deported|jailed|sued|charged|fined"
        r"|prosecuted|go to (?:jail|prison))\b",
        r"\bwarrant (?:out )?for your arrest\b|\barrest warrant\b|\blegal action\b",
        r"\bface (?:arrest|charges|jail|prison|prosecution)\b",
        r"\byour (?:bank )?(?:accounts?|social security(?: number)?|benefits?|license|computer|pc|device)\s+(?:will be"
        r"|is being|has been|is|was)\s+(?:frozen|closed|suspended|locked|cancell?ed|compromised|hacked|seized|infected)\b",
        r"\byour (?:computer|pc|device|phone) has (?:a )?(?:virus|malware)\b",
    ),
    "family_emergency": _rx(
        r"\bi(?:'m| am) in (?:trouble|jail|prison|the hospital|custody)\b",
        r"\bi(?:'ve| have) been (?:arrested|detained|kidnapped|in an accident|in a (?:car )?accident)\b",
        r"\bi got (?:arrested|detained|in an accident)\b|\bcar accident\b",
        r"\b(?:grandma|grandpa|granny|nana|grandmother|grandfather)\b[^.?!]{0,40}"
        r"\b(?:trouble|help me|accident|arrested|hospital|jail)\b",
    ),
    "impersonation": _rx(
        r"\b(?:this is|calling from|i'?m with|i am with|i'?m from|i am from|we are|we're)\s+(?:the |your )?"
        r"(?:irs|internal revenue service|social security(?: administration)?|medicare|fbi|police|sheriff|dea"
        r"|customs|treasury|bank|fraud (?:department|team)|microsoft|apple support|amazon|tech support|geek squad)\b",
        r"\b(?:this is|i'?m|i am) (?:an? |the )?(?:officer|agent|detective|sergeant|deputy|lawyer|attorney)\b",
    ),
}
assert set(_MATCHERS) == set(REASONS), "every reason code needs a matcher"

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"'”’)])\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences that are exact substrings of it."""
    return [s for s in _SENTENCE_BREAK.split(text) if s]


@lru_cache(maxsize=4096)
def _matches_in(text: str) -> tuple[tuple[str, str], ...]:
    # Match on the folded sentence, quote the original one. Cached because every utterance re-analyzes the window.
    return tuple(
        (reason, sentence)
        for sentence in split_sentences(text)
        for folded in (fold(sentence),)
        for reason, matches in _MATCHERS.items()
        if matches(folded)
    )


def detect(utterances: Iterable[Utterance]) -> list[Indicator]:
    """Return one indicator per (sentence, reason) match, in transcript order."""
    return [Indicator(reason, u.utterance_id, sentence) for u in utterances for reason, sentence in _matches_in(u.text)]
