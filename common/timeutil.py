# common/timeutil.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
import dateparser

from common.config import TASK_CONFIG, get_task_config, get_shopping_digest_schedule

def parse_when(text: str, tz: str):
    return dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": tz,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )

def interval_to_minutes(value: Optional[int], unit: Optional[str]) -> Optional[int]:
    if value is None or unit is None:
        return None
    u = unit.lower()
    if u in ("m", "min", "mins", "minute", "minutes"): return int(value)
    if u in ("h", "hr", "hrs", "hour", "hours"):       return int(value) * 60
    if u in ("d", "day", "days"):                       return int(value) * 1440
    raise ValueError(f"Unknown time unit: {unit}")

def get_config_snooze_minutes(kind: str) -> Optional[int]:
    cfg = get_task_config(kind)
    return interval_to_minutes(cfg.get("reminder_value"), cfg.get("reminder_unit"))

def get_config_items_with_reminders() -> set[str]:
    return {
        k for k, v in TASK_CONFIG.items()
        if interval_to_minutes(v.get("reminder_value"), v.get("reminder_unit")) is not None
    }

def next_digest_at_configured_time(tz: str):
    weekday, hour = get_shopping_digest_schedule()
    now = datetime.now(ZoneInfo(tz))
    days_ahead = (weekday - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate
