"""Demo replay: run fixture transcripts through the detector and print the resulting event stream.

    python -m backend.intelligence.replay fixtures/scam_call.json          # JSON lines on stdout
    python -m backend.intelligence.replay fixtures --check                 # PASS/FAIL against "expected"

Uses Gemini when GEMINI_API_KEY and GEMINI_MODEL are set; otherwise rules only. Output is a replay, not live
inference, and must be labeled "Demo replay" wherever it is shown.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import gemini
from .detector import analyze_transcript


async def replay(fixture: dict) -> tuple[list[dict], dict]:
    """Return (event stream with risk.updated events interleaved, final decision)."""
    session_id = fixture["session_id"]
    stream, utterances, decision = [], [], {}
    for event in fixture["events"]:
        stream.append(event)
        if event["type"] != "transcript.final":
            continue
        utterances.append({**event["payload"], "timestamp": event["timestamp"]})
        previous_id = decision.get("decision_id")
        decision = await analyze_transcript(session_id, utterances)
        if decision["decision_id"] != previous_id:
            stream.append({"type": "risk.updated", "timestamp": event["timestamp"], "payload": decision})
    # Renumber so event_id and sequence stay unique and monotonic after interleaving.
    numbered = [
        {**event, "event_id": f"evt_{n:03d}", "session_id": session_id, "sequence": n}
        for n, event in enumerate(stream, start=1)
    ]
    return numbered, decision


def check(fixture: dict, decision: dict) -> list[str]:
    expected = fixture.get("expected", {})
    problems = [
        f"{field}: expected {expected[field]!r}, got {decision.get(field)!r}"
        for field in ("risk", "recommended_action")
        if field in expected and decision.get(field) != expected[field]
    ]
    missing = set(expected.get("reasons_include", ())) - set(decision.get("reasons", ()))
    if missing:
        problems.append(f"missing reasons: {sorted(missing)}")
    return problems


async def _main(paths: list[Path], check_only: bool) -> int:
    failures = 0
    try:
        for path in paths:
            fixture = json.loads(path.read_text(encoding="utf-8"))
            stream, decision = await replay(fixture)
            problems = check(fixture, decision)
            failures += bool(problems)
            if check_only:
                outcome = f"{decision['risk']}/{decision['recommended_action']}"
                print(f"FAIL {path.name}: {outcome} {'; '.join(problems)}" if problems else f"PASS {path.name}: {outcome}")
            else:
                print("\n".join(json.dumps(event) for event in stream))
                for problem in problems:
                    print(f"{path.name}: {problem}", file=sys.stderr)
    finally:
        if client := gemini.get_client():
            await client.aclose()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fixtures", nargs="+", type=Path, help="fixture files or directories of them")
    parser.add_argument("--check", action="store_true", help="print PASS/FAIL per fixture instead of the stream")
    args = parser.parse_args()
    paths = [p for arg in args.fixtures for p in (sorted(arg.glob("*.json")) if arg.is_dir() else [arg])]
    sys.exit(asyncio.run(_main(paths, args.check)))


if __name__ == "__main__":
    main()
