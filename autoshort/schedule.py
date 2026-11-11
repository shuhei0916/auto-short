"""Picks seeds and publish slots for the daily run. State lives in out/*.json."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 15:00 and 23:00 UTC = US morning and US evening.
DEFAULT_HOURS = (15, 23)
MARGIN = timedelta(hours=1)


def _metas(out_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.json"))]


def next_seed(out_dir: Path) -> int:
    return max((m["seed"] for m in _metas(out_dir)), default=0) + 1


def taken_slots(out_dir: Path) -> set[datetime]:
    out = set()
    for m in _metas(out_dir):
        when = (m.get("uploaded") or {}).get("publish_at")
        if when:
            out.add(datetime.fromisoformat(when.replace("Z", "+00:00")))
    return out


def next_slots(now: datetime, count: int, hours=DEFAULT_HOURS, taken=frozenset()) -> list[datetime]:
    slots: list[datetime] = []
    day = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    while len(slots) < count:
        for h in sorted(hours):
            slot = day + timedelta(hours=h)
            if slot >= now + MARGIN and slot not in taken and len(slots) < count:
                slots.append(slot)
        day += timedelta(days=1)
    return slots


def to_rfc3339(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
