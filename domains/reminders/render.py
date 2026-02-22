from datetime import datetime, timedelta           # <-- timedelta added
from zoneinfo import ZoneInfo
from common.config import get_task_config

def render_reminder_section(items: dict, kind: str, tz: str, heading: str) -> str:
    """Return Markdown for active reminders of a given kind, soonest→farthest."""
    open_items = [it for it in items.values() if it.get("kind") == kind and it.get("active")]
    if not open_items:
        return ""

    def _to_local(dt_iso: str) -> datetime:
        dt = datetime.fromisoformat(dt_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        return dt.astimezone(ZoneInfo(tz))

    def _pretty_short(d: datetime) -> str:
        now = datetime.now(ZoneInfo(tz))
        today = now.date()
        tomorrow = today + timedelta(days=1)
        t = d.strftime("%H:%M UTC%z")  # use "%-I:%M %p %Z" (Unix) or "%#I:%M %p %Z" (Windows) for 12h
        if d.date() == today:
            return f"Today {t}"
        if d.date() == tomorrow:
            return f"Tomorrow {t}"
        return d.strftime("%a, %d %b %Y %H:%M UTC%z")

    enriched = []
    for it in open_items:
        try:
            enriched.append((_to_local(it["due"]), it))
        except Exception:
            continue

    if not enriched:
        return ""

    enriched.sort(key=lambda t: t[0])
    emoji = get_task_config(kind).get("emoji", "")

    lines = [f"{heading}"]
    for due_local, it in enriched:
        pretty = _pretty_short(due_local)
        lines.append(f"[[#{it['id']}]] {emoji} {it['label']}\nDUE: {pretty}")

    return "\n\n".join(lines)
