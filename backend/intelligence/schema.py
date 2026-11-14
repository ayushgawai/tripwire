"""Constants and validation for the risk-decision contract (see Tripwire_Quick_Build_Plan.md)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

SPEAKERS = frozenset({"caller", "wearer", "family", "assistant", "ambient"})
# Assistant and family speech never feeds risk detection.
ANALYZED_SPEAKERS = frozenset({"caller", "wearer", "ambient"})

RISKS = ("low", "review", "high")
ACTIONS = ("none", "alert", "takeover")

# Reason codes, grouped by the role they play in the escalation policy.
# Asks for value, or a large amount of money. High risk always needs one of these.
FINANCIAL = ("gift_card_request", "payment_request", "credential_request", "remote_access_request", "large_amount")
# Pressure tactics. High risk always needs one of these.
PRESSURE = ("urgency", "secrecy", "verification_discouraged", "threat")
# Pretexts that add weight but never escalate on their own.
CONTEXT = ("family_emergency", "impersonation")
REASONS = FINANCIAL + PRESSURE + CONTEXT

# Minimum number of distinct reasons for a high-risk decision. This is a demo policy, not a validated classifier.
HIGH_RISK_MIN_REASONS = 3


@dataclass(frozen=True, slots=True)
class Utterance:
    utterance_id: str
    speaker: str
    text: str
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class Indicator:
    reason: str
    utterance_id: str
    quote: str


def validate_decision(decision: Mapping, utterances: Iterable[Utterance | Mapping]) -> list[str]:
    """Return a list of contract violations (empty when valid). Each evidence quote must occur in its utterance."""
    texts = {
        (u.utterance_id if isinstance(u, Utterance) else u.get("utterance_id")): (
            u.text if isinstance(u, Utterance) else u.get("text", "")
        )
        for u in utterances
    }
    errors: list[str] = []
    if not isinstance(decision.get("decision_id"), str) or not decision["decision_id"]:
        errors.append("decision_id must be a non-empty string")
    if decision.get("risk") not in RISKS:
        errors.append(f"risk must be one of {RISKS}")
    if decision.get("recommended_action") not in ACTIONS:
        errors.append(f"recommended_action must be one of {ACTIONS}")
    if not isinstance(decision.get("summary"), str):
        errors.append("summary must be a string")
    reasons = decision.get("reasons")
    if not isinstance(reasons, list) or any(r not in REASONS for r in reasons):
        errors.append("reasons must be a list of known reason codes")
    evidence = decision.get("evidence")
    if not isinstance(evidence, list):
        return [*errors, "evidence must be a list"]
    for item in evidence:
        uid, quote = item.get("utterance_id"), item.get("quote")
        if uid not in texts:
            errors.append(f"evidence references unknown utterance {uid!r}")
        elif not isinstance(quote, str) or not quote or quote not in texts[uid]:
            errors.append(f"evidence quote {quote!r} does not occur in utterance {uid!r}")
    return errors
