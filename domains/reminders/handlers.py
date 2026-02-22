from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes

from common.state import ensure_user_bucket, alloc_gid
from common.timeutil import parse_when
from common.scheduling import jobname_text as jobname_reminder, run_once
from common.config import get_task_config, get_config_emoji
from common.timeutil import get_config_snooze_minutes
from domains.timezone.handlers import check_timezone
from .jobs import reminder_job  # the unified job above


def make_reminder_handler(kind: str, label_format: str):
    """
    Factory that returns a PTB handler function for reminder-like kinds.
    label_format: e.g. 'Text {name}' or 'Todo {task}'
    """
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        ensure_user_bucket(context.user_data)

        tz = await check_timezone(update, context)
        if not tz:
            return

        if not context.args:
            return await update.message.reply_text(f"Usage: /{kind} <what> @ <time>")

        raw = " ".join(context.args)
        parts = [p.strip() for p in raw.split("@")]
        if len(parts) < 2:
            return await update.message.reply_text("Need text and time separated by '@'")

        what, date_str = parts[0], parts[1]

        # Bare hour support (e.g., "@ 9")
        if date_str.isdigit():
            hr = int(date_str)
            if 0 <= hr <= 23:
                now_local = datetime.now(ZoneInfo(tz))
                if hr > now_local.hour:
                    date_str = f"{hr}:00 today"
                if hr < now_local.hour:
                    hr += 12
                    date_str = f"{hr % 24}:00 tomorrow" if hr > 24 else f"{hr}:00 today"
            else:
                return await update.message.reply_text(f"Couldn't parse '{date_str}'.")
        
        if "tonight" in date_str:
            date_str.replace("tonight", "today")

        dt = parse_when(date_str, tz)
        if not dt:
            return await update.message.reply_text(f"Couldn't parse '{date_str}'.")

        snooze_min = get_config_snooze_minutes(kind)
        if snooze_min is None:
            return await update.message.reply_text(f"Config error: '{kind}' reminder interval not set.")

        gid = alloc_gid(context.user_data)
        label = label_format.format(name=what, task=what, what=what)  # flexible
        emoji = get_config_emoji(kind)

        # Store everything needed by the generic job
        context.user_data["items"][gid] = {
            "id": gid,
            "kind": kind,
            "label": label,
            "emoji": emoji,
            "due": dt.isoformat(),
            "active": True,
            "snooze_min": snooze_min,
            "chat_id": update.effective_chat.id,
            "tz": tz,
        }

        # Schedule first run (jobname function can remain reused)
        run_once(
            context,
            reminder_job,
            when_local=dt,
            name=jobname_reminder(update.effective_user.id, gid),
            chat_id=update.effective_chat.id,
            data={"user_id": update.effective_user.id, "gid": gid},
        )

        await update.message.reply_text(
            f"{emoji} '*{label}*’ scheduled for"
            f"\n\t{dt.strftime('%a, %d %b %Y at %H:%M %Z')}"
            f"\n\n(Reminders every {snooze_min}m. To stop: /done {gid})"
        )

    return handler