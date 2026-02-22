from datetime import datetime
from zoneinfo import ZoneInfo

def jobname_text(user_id: int, gid: str) -> str:
    return f"text:{user_id}:{gid}"

def jobname_shopping(user_id: int) -> str:
    return f"shopping:{user_id}:weekly"

def run_once(app_or_ctx, callback, when_local: datetime, name: str, chat_id: int, data: dict):
    """Schedule one job, converting local time to UTC."""
    when_utc = when_local.astimezone(ZoneInfo("UTC"))
    jq = app_or_ctx.job_queue
    jq.run_once(callback=callback, when=when_utc, name=name, chat_id=chat_id, data=data)
