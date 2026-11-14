"""Transcript normalization: validate speakers, drop duplicates, and fold text for matching.

Utterance text keeps its original characters, trimmed only. Evidence quotes are slices of it, so they are exact
substrings of the text the backend stored. Matching runs on fold(text) instead.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import asdict

from .schema import ANALYZED_SPEAKERS, SPEAKERS, Utterance

log = logging.getLogger(__name__)

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_WHITESPACE = re.compile(r"\s+")


def fold(text: str) -> str:
    """Matching form: NFKC, straight quotes, single spaces. Never used for quotes."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", text).translate(_QUOTES)).strip()


def normalize_utterance(raw: Mapping) -> dict:
    """Validate one transcript payload. Raises ValueError if it is unusable."""
    return asdict(_parse(raw))


def _parse(raw: Mapping) -> Utterance:
    if not isinstance(raw, Mapping):
        raise ValueError("utterance must be an object")
    utterance_id = str(raw.get("utterance_id") or "").strip()
    if not utterance_id:
        raise ValueError("utterance_id is required")
    speaker = str(raw.get("speaker") or "").strip().lower()
    if speaker not in SPEAKERS:
        raise ValueError(f"unknown speaker {speaker!r}; expected one of {sorted(SPEAKERS)}")
    text = raw.get("text")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    return Utterance(utterance_id, speaker, text.strip(), raw.get("timestamp"))


def normalize_transcript(utterances: Iterable[Mapping | Utterance]) -> list[Utterance]:
    """Normalize in arrival order. Invalid or empty entries are skipped; repeated utterance_ids keep the first copy."""
    seen: set[str] = set()
    result: list[Utterance] = []
    for raw in utterances:
        try:
            utterance = raw if isinstance(raw, Utterance) else _parse(raw)
        except ValueError as exc:
            log.warning("Skipping invalid utterance: %s", exc)
            continue
        if utterance.text and utterance.utterance_id not in seen:
            seen.add(utterance.utterance_id)
            result.append(utterance)
    return result


def analyzable(utterances: Iterable[Utterance]) -> list[Utterance]:
    """Utterances that feed risk detection (caller, wearer, ambient). Excludes assistant and family speech."""
    return [u for u in utterances if u.speaker in ANALYZED_SPEAKERS]
