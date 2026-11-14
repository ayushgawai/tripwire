"""Run all provider checks and print a summary table.

    python -m backend.audio.provider_checks.run_all [--markdown]

Exit: 0 all PASS, 1 any FAIL, else 2 (some BLOCKED).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from . import daily, deepgram, elevenlabs, gemini
from .common import BLOCKED, FAIL, PASS, Result, exception_result, scrub

CHECKS = [
    (daily, daily.PROVIDER, daily.OWNER),
    (deepgram, deepgram.PROVIDER, deepgram.OWNER),
    (gemini, gemini.PROVIDER, gemini.OWNER),
    (elevenlabs, elevenlabs.PROVIDER, elevenlabs.OWNER),
]
HEADERS = ["Provider", "Owner", "Status", "HTTP", "Notes"]


def run() -> list[Result]:
    results = []
    for mod, provider, owner in CHECKS:
        try:
            results.append(mod.check())
        except Exception as exc:  # noqa: BLE001
            results.append(exception_result(provider, owner, exc))
    return results


def rows(results: list[Result]) -> list[list[str]]:
    return [[r.provider, r.owner, r.status, r.http_status, r.detail] for r in results]


def text_table(results: list[Result]) -> str:
    data = [HEADERS] + rows(results)
    widths = [max(len(row[i]) for row in data) for i in range(len(HEADERS) - 1)]
    lines = []
    for idx, row in enumerate(data):
        cells = [row[i].ljust(widths[i]) for i in range(len(widths))] + [row[-1]]
        lines.append(" | ".join(cells))
        if idx == 0:
            lines.append("-+-".join("-" * w for w in widths) + "-+-" + "-" * 5)
    return "\n".join(lines)


def markdown_table(results: list[Result]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hdr = ["Date (UTC)"] + HEADERS
    lines = ["| " + " | ".join(hdr) + " |", "|" + "|".join("---" for _ in hdr) + "|"]
    for row in rows(results):
        cells = [today] + [c.replace("|", "\\|") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def exit_code(results: list[Result]) -> int:
    if all(r.status == PASS for r in results):
        return 0
    if any(r.status == FAIL for r in results):
        return 1
    return 2


def main() -> None:
    results = run()
    out = markdown_table(results) if "--markdown" in sys.argv[1:] else text_table(results)
    print(scrub(out))
    sys.exit(exit_code(results))


if __name__ == "__main__":
    main()
