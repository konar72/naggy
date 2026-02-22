from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes
from common.config import TASK_CONFIG
from domains.reminders.render import render_reminder_section
from domains.reminders.handlers import make_reminder_handler
from common.state import ensure_user_bucket, alloc_gid

text = make_reminder_handler("text", "Text {name}")

async def text_summary(update, context):
    ensure_user_bucket(context.user_data)
    tz = context.user_data.get("tz")
    if not tz:
        return await update.message.reply_text("Set tz: /timezone <Region/City>")
    section = render_reminder_section(context.user_data["items"], "text", tz, "Text reminders")
    return await update.message.reply_text(section or "No active text reminders.", parse_mode="Markdown")
