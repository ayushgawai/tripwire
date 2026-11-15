"""Gemini Decision 1 (Gemini Decisions API): a calibrated scam check on every analyzed utterance.

One forward pass scores fixed options (no text generation), so it fits inside a live conversation.
Rules still provide the verbatim evidence; this adds P(scam) and a recommended action.
"""

from __future__ import annotations

import os
import time

import httpx

URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
QUESTIONS = {
    "is_scam": {"type": "noul", "instructions": "Is the speaker pressuring the listener into a scam "
                "(gift cards, urgent payment, secrecy, fake emergency, impersonation)?"},
    "action": {"type": "choice", "instructions": "What should a protective assistant for an older adult do?",
               "criteria": {"none": "Normal conversation.", "alert": "Somewhat suspicious; alert family.",
                            "takeover": "Clear high-pressure scam; pause the conversation now."}},
}


async def decide(utterances: list[dict]) -> dict | None:
    """Return {p_scam, action, confidence, latency_ms} or None if unavailable (never raises)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not utterances:
        return None
    text = "\n".join(f"{u.get('speaker', '?')}: {u.get('text', '')}" for u in utterances[-6:])
    t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.5) as c:
            r = await c.post(URL, headers={"x-goog-api-key": key},
                             json={"model": "gemini-decision-1", "input": text, "questions": QUESTIONS})
        r.raise_for_status()
        a = r.json()["answers"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    return {"model": "gemini-decision-1", "p_scam": round(a["is_scam"]["noul"], 3),
            "action": a["action"]["choice"], "confidence": round(a["action"]["confidence"], 3),
            "latency_ms": int((time.perf_counter() - t) * 1000)}
