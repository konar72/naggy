# domains/reminders/jobs.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram.ext import ContextTypes

from common.config import get_task_config
from common.motivators import pick_motivator_by_category

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    uid = job.data["user_id"]
    gid = job.data["gid"]

    ud = context.application.user_data.get(uid) or {}
    it = (ud.get("items") or {}).get(gid)
    if not it or not it.get("active"):
        return

    kind = it.get("kind")
    cfg = get_task_config(kind)
    emoji = it.get("emoji", cfg.get("emoji", ""))

    # Pull motivator settings from config.json
    motivation_type = cfg.get("motivation_type")     # e.g. "text", "task", or None
    tone_weights = cfg.get("tone_weights") or {}

    motiv = pick_motivator_by_category(motivation_type, tone_weights)

    base = f"{emoji} {it.get('label','')}".strip()
    body = f"{base}\n{motiv}\n" if motiv else base

    await context.bot.send_message(chat_id=job.chat_id, text=body + f"\nStop: /done {gid}")

    # Reschedule
    tz = it.get("tz"); snooze = it.get("snooze_min")
    if tz and snooze:
        next_local = datetime.now(ZoneInfo(tz)) + timedelta(minutes=int(snooze))
        context.job_queue.run_once(
            reminder_job,
            when=next_local.astimezone(ZoneInfo("UTC")),
            name=job.name,
            chat_id=job.chat_id,
            data=job.data,
        )
