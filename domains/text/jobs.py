# domains/text/jobs.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram.ext import ContextTypes

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    uid = job.data["user_id"]
    gid = job.data["gid"]

    # Recover user’s task
    ud = context.application.user_data.get(uid, {})
    t = ud.get("items", {}).get(gid)
    if not t or not t.get("active"):
        return

    # Send reminder
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ {t['label']}\nReply /done {t['id']} to stop.",
    )

    # Reschedule for snooze interval
    snooze = t.get("snooze_min", 60)
    tz = t.get("tz")
    if not tz:
        return
    next_time = (datetime.now(ZoneInfo(tz)) + timedelta(minutes=snooze))
    context.job_queue.run_once(
        reminder_job,
        when=next_time.astimezone(ZoneInfo("UTC")),
        name=job.name,
        chat_id=job.chat_id,
        data=job.data,
    )
