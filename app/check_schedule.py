from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CHECK_SCHEDULE_JSON = DATA_DIR / "check_schedule.json"

NORMAL_INTERVAL_SECONDS = 3600
DOWN_INTERVAL_SECONDS = 1800


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_utc_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def load_schedule_state() -> dict:
    if not CHECK_SCHEDULE_JSON.exists():
        return {}

    try:
        return json.loads(CHECK_SCHEDULE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_schedule_state(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    tmp = CHECK_SCHEDULE_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CHECK_SCHEDULE_JSON)


def make_endpoint_key(site_id: int, endpoint_id: int) -> str:
    return f"{site_id}:{endpoint_id}"


def interval_for_state(state: str) -> int:
    state = str(state or "").strip().upper()
    if state == "DOWN":
        return DOWN_INTERVAL_SECONDS
    return NORMAL_INTERVAL_SECONDS


def is_due(entry: dict | None, now_utc: datetime | None = None) -> bool:
    if not entry:
        return True

    next_due_at = parse_utc_iso(entry.get("next_due_at_utc"))
    if next_due_at is None:
        return True

    if now_utc is None:
        now_utc = utc_now()

    return now_utc >= next_due_at


def build_next_entry(
    *,
    current_state: str,
    checked_at_utc: str,
) -> dict:
    checked_at = parse_utc_iso(checked_at_utc)
    if checked_at is None:
        checked_at = utc_now()

    state = str(current_state or "").strip().upper()
    interval_seconds = interval_for_state(state)
    next_due_at = checked_at + timedelta(seconds=interval_seconds)

    return {
        "last_checked_at_utc": checked_at.isoformat(timespec="seconds"),
        "last_known_state": state,
        "current_interval_seconds": interval_seconds,
        "next_due_at_utc": next_due_at.isoformat(timespec="seconds"),
    }


def get_entry(
    schedule_state: dict,
    *,
    site_id: int,
    endpoint_id: int,
) -> dict:
    return schedule_state.get(make_endpoint_key(site_id, endpoint_id), {})


def set_entry(
    schedule_state: dict,
    *,
    site_id: int,
    endpoint_id: int,
    entry: dict,
) -> None:
    schedule_state[make_endpoint_key(site_id, endpoint_id)] = entry