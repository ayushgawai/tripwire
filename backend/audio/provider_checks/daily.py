"""Daily check: create a short-lived room, then delete it.

Docs: https://docs.daily.co/reference/rest-api/rooms/create-room
      https://docs.daily.co/reference/rest-api/rooms/delete-room
"""
from __future__ import annotations

import time
import uuid
from urllib.parse import urlparse

import httpx

from .common import BLOCKED, FAIL, PASS, TIMEOUT, Result, env, explain_status, main_for, require

PROVIDER, OWNER = "Daily", "Manav"
API = "https://api.daily.co/v1"


def check() -> Result:
    ok, vars_ = require("DAILY_API_KEY")
    if not ok:
        return Result(PROVIDER, OWNER, BLOCKED, "-", vars_)
    headers = {"Authorization": f"Bearer {env('DAILY_API_KEY')}"}
    name = f"tripwire-check-{uuid.uuid4().hex[:8]}"
    body = {"name": name, "privacy": "private", "properties": {"exp": int(time.time()) + 300}}
    with httpx.Client(timeout=TIMEOUT, headers=headers) as c:
        r = c.post(f"{API}/rooms", json=body)
        if r.status_code != 200:
            return Result(PROVIDER, OWNER, FAIL, str(r.status_code),
                          f"create room: {explain_status(r.status_code)}")
        data = r.json()
        room_name = data.get("name", name)
        host = urlparse(data.get("url") or "").hostname or ""
        domain = host.split(".")[0] if host.endswith(".daily.co") else ""
        d = c.delete(f"{API}/rooms/{room_name}")
    notes = [f"create {r.status_code}", f"delete {d.status_code}"]
    if domain:
        notes.append(f"domain={domain}")
    if d.status_code != 200:
        notes.append(f"delete: {explain_status(d.status_code)} (room auto-expires in 5 min)")
        return Result(PROVIDER, OWNER, FAIL, f"{r.status_code}/{d.status_code}", "; ".join(notes))
    return Result(PROVIDER, OWNER, PASS, f"{r.status_code}/{d.status_code}", "; ".join(notes))


if __name__ == "__main__":
    main_for(check, PROVIDER, OWNER)
